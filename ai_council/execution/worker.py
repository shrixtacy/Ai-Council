"""Async worker node for distributed model execution using Redis."""

import asyncio
import json
import time
import uuid
import os
import sys

# Append the project root directory when running via script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_council.core.logger import get_logger
from ai_council.core.models import Subtask, RiskLevel, Priority, TaskType
from ai_council.execution.agent import BaseExecutionAgent
from ai_council.utils.config import load_config
from ai_council.factory import AICouncilFactory
from ai_council.core.tracing import setup_tracing, get_tracer
from opentelemetry.propagate import extract
import redis.asyncio as redis

logger = get_logger(__name__)

class WorkerNode:
    """Distributed execution worker listening to Redis task queues."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.task_queue = "ai_council:tasks"
        self.redis_client = None
        
        # Load core configurations and factory for BaseExecutionAgent
        self.config = load_config()
        self.factory = AICouncilFactory(self.config)
        self.model_registry = self.factory.model_registry
        self.execution_agent = BaseExecutionAgent(model_registry=self.model_registry)
        
        # OpenTelemetry Setup
        setup_tracing("ai_council_worker")
        self.tracer = get_tracer("worker_node")

    async def _ensure_connection(self):
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Worker connected to Redis: {self.redis_url}")

    def _deserialize_subtask(self, data: dict) -> Subtask:
        task_type_str = data.get("task_type")
        task_type = TaskType(task_type_str) if task_type_str else None
        
        priority_str = data.get("priority")
        priority = Priority(priority_str) if priority_str else Priority.MEDIUM
        
        risk_level_str = data.get("risk_level")
        risk_level = RiskLevel(risk_level_str) if risk_level_str else RiskLevel.LOW
        
        return Subtask(
            id=data.get("subtask_id", str(uuid.uuid4())),
            parent_task_id=data.get("parent_task_id", ""),
            content=data.get("content", ""),
            task_type=task_type,
            priority=priority,
            risk_level=risk_level,
            accuracy_requirement=data.get("accuracy_requirement", 0.8),
            metadata=data.get("metadata", {})
        )

    async def process_task(self, payload: str):
        try:
            data = json.loads(payload)
            subtask = self._deserialize_subtask(data)
            model_id = data.get("model_id", "default")
            
            response_key = f"ai_council:results:{subtask.id}"
            progress_channel = f"ai_council:progress:{subtask.id}"

            # OpenTelemetry - Context Extraction to link spans
            carrier = data.get("trace_context", {})
            ctx = extract(carrier)
            
            with self.tracer.start_as_current_span(
                "worker_process_task", 
                context=ctx,
                attributes={"subtask_id": subtask.id, "model_id": model_id}
            ) as current_span:
                logger.info(f"Worker processing subtask {subtask.id} via model {model_id}")
                
                model = self.model_registry.get_model_by_id(model_id)
                if not model:
                    raise ValueError(f"Model ID {model_id} not found in model registry")
                
                # Execute the actual model (locally to the worker)
                async def progress_callback(prog_data: dict):
                    await self.redis_client.publish(progress_channel, json.dumps(prog_data))

                response = await self.execution_agent.execute(subtask, model, progress_callback=progress_callback)
                
                # Setup resulting JSON payload
                sa = response.self_assessment
                result_payload = {
                    "subtask_id": response.subtask_id,
                    "model_used": response.model_used,
                    "content": response.content,
                    "success": response.success,
                    "error_message": response.error_message,
                    "metadata": response.metadata,
                    "self_assessment": {
                        "confidence_score": sa.confidence_score if sa else 0.0,
                        "assumptions": sa.assumptions if sa else [],
                        "risk_level": sa.risk_level.value if sa and sa.risk_level else "low",
                        "estimated_cost": sa.estimated_cost if sa else 0.0,
                        "token_usage": sa.token_usage if sa else 0,
                        "execution_time": sa.execution_time if sa else 0.0,
                        "model_used": sa.model_used if sa else ""
                    } if sa else {}
                }
                
                # Publish the final result
                await self.redis_client.rpush(response_key, json.dumps(result_payload))
                logger.info(f"Worker completed subtask {subtask.id} successfully")
                current_span.set_attribute("success", True)

        except Exception as e:
            logger.error(f"Worker error processing payload: {str(e)}")
            # Attempt to reply with failure if we have the response_key
            try:
                data = json.loads(payload)
                subtask_id = data.get("subtask_id")
                model_id = data.get("model_id", "unknown_model")
                if subtask_id:
                    failure_payload = {
                        "subtask_id": subtask_id,
                        "model_used": model_id,
                        "content": "",
                        "success": False,
                        "error_message": f"Worker error: {str(e)}",
                        "metadata": {},
                        "self_assessment": {
                            "confidence_score": 0.0,
                            "risk_level": "critical",
                            "model_used": model_id,
                        }
                    }
                    await self.redis_client.rpush(f"ai_council:results:{subtask_id}", json.dumps(failure_payload))
            except Exception as nested_e:
                logger.error(f"Could not return failure payload: {nested_e}")

    async def start(self):
        """Start the worker node listening loop."""
        await self._ensure_connection()
        logger.info(f"Worker node starting. Listening on {self.task_queue}...")
        
        try:
            while True:
                # BLPOP from the queue (blocks until a message arrives)
                result = await self.redis_client.blpop(self.task_queue, timeout=0)
                if result:
                    _, payload = result
                    # Spawn a concurrent task so worker isn't blocked by one request
                    asyncio.create_task(self.process_task(payload))
        except asyncio.CancelledError:
            logger.info("Worker node shutting down.")
        finally:
            if self.redis_client:
                await self.redis_client.aclose()


if __name__ == "__main__":
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    worker = WorkerNode(redis_url)
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user.")
