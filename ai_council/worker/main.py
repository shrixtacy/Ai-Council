"""Worker node entry point for AI Council."""

import os
import json
import time
import asyncio
import logging
from typing import Dict, Any

import redis.asyncio as redis

from ai_council.utils.config import load_config
from ai_council.utils.logging import configure_logging, get_logger
from ai_council.factory import AICouncilFactory
from ai_council.core.models import Subtask, AgentResponse, SelfAssessment, RiskLevel, Priority, TaskType

# Suppress overly verbose logs from some libraries
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = get_logger("ai_council.worker")


class CouncilWorker:
    """Worker node that listens to Redis for tasks and executes them."""

    def __init__(self, config_path: str = None):
        """Initialize the worker and setup dependencies."""
        self.config = load_config(config_path)
        configure_logging(self.config.logging)
        
        self.redis_url = self.config.execution.redis_url
        self.redis_client = None
        self.task_queue = "ai_council:tasks"
        
        # We need the real BaseExecutionAgent to execute things
        logger.info("Initializing worker factory and dependencies...")
        self.factory = AICouncilFactory(self.config)
        self.model_registry = self.factory.model_registry
        
        # Create models manually or fetch from registry
        self.models = self.factory.create_models_from_config()
        for name, model in self.models.items():
            logger.info(f"Worker loaded model: {name}")

        # The actual execution engine
        from ai_council.execution.agent import BaseExecutionAgent
        self.execution_agent = BaseExecutionAgent()
        
        self.running = False

    async def _deserialize_task(self, data: Dict[str, Any]) -> tuple[Subtask, str]:
        """Deserialize incoming JSON into a Subtask object and get the required model ID."""
        task_type_val = data.get("task_type")
        priority_val = data.get("priority", Priority.MEDIUM.value)
        risk_level_val = data.get("risk_level", RiskLevel.LOW.value)

        subtask = Subtask(
            id=data.get("subtask_id", ""),
            parent_task_id=data.get("parent_task_id", ""),
            content=data.get("content", ""),
            task_type=TaskType(task_type_val) if task_type_val else None,
            priority=Priority(priority_val) if priority_val else Priority.MEDIUM,
            risk_level=RiskLevel(risk_level_val) if risk_level_val else RiskLevel.LOW,
            accuracy_requirement=data.get("accuracy_requirement", 0.8),
            estimated_cost=data.get("estimated_cost", 0.0),
            metadata=data.get("metadata", {})
        )
        return subtask, data.get("model_id", "")

    def _serialize_response(self, response: AgentResponse) -> str:
        """Serialize the AgentResponse to JSON for the MQ."""
        
        sa_dict = {}
        if response.self_assessment:
            sa = response.self_assessment
            sa_dict = {
                "confidence_score": sa.confidence_score,
                "assumptions": sa.assumptions,
                "risk_level": sa.risk_level.value,
                "estimated_cost": sa.estimated_cost,
                "token_usage": sa.token_usage,
                "execution_time": sa.execution_time,
                "model_used": sa.model_used,
            }

        payload = {
            "subtask_id": response.subtask_id,
            "model_used": response.model_used,
            "content": response.content,
            "success": response.success,
            "error_message": response.error_message,
            "metadata": response.metadata,
            "self_assessment": sa_dict
        }
        return json.dumps(payload)

    async def process_task(self, payload_json: str):
        """Process a single task from the queue."""
        start_time = time.time()
        subtask_id = "unknown"
        response_key = "unknown"
        
        try:
            data = json.loads(payload_json)
            subtask_id = data.get("subtask_id", "unknown")
            response_key = f"ai_council:results:{subtask_id}"
            
            logger.info(f"Worker processing subtask: {subtask_id}")
            
            subtask, model_id = await self._deserialize_task(data)
            
            # Fetch model from registry
            model = self.models.get(model_id)
            if not model:
                model = self.model_registry.get_model(model_id)
            
            if not model:
                raise ValueError(f"Model {model_id} not found in worker registry")
            
            # Execute standard logic
            response: AgentResponse = await self.execution_agent.execute(subtask, model)
            
            # Send result back
            serialized_response = self._serialize_response(response)
            await self.redis_client.rpush(response_key, serialized_response)
            
            # Set a TTL on the response key to avoid memory leaks if orchestrator died
            await self.redis_client.expire(response_key, 300)
            
            logger.info(f"Worker completed subtask {subtask_id} in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Worker failed processing subtask {subtask_id}: {str(e)}", exc_info=True)
            
            # Send error response back
            if response_key != "unknown":
                error_resp = AgentResponse(
                    subtask_id=subtask_id,
                    model_used="unknown",
                    content="",
                    success=False,
                    error_message=str(e),
                    self_assessment=SelfAssessment(
                        confidence_score=0.0,
                        risk_level=RiskLevel.CRITICAL,
                        execution_time=time.time() - start_time
                    )
                )
                try:
                    await self.redis_client.rpush(response_key, self._serialize_response(error_resp))
                    await self.redis_client.expire(response_key, 300)
                except Exception as pub_e:
                    logger.critical(f"Worker failed to publish error for {subtask_id}: {str(pub_e)}")

    async def run(self):
        """Main loop: connect to Redis and block-pop tasks."""
        self.running = True
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        logger.info(f"Worker started. Listening on Redis: {self.redis_url}, queue: {self.task_queue}")
        
        try:
            while self.running:
                logger.debug("Waiting for next task...")
                # Block with a 5s timeout to allow clean shutdown checks
                result = await self.redis_client.blpop(self.task_queue, timeout=5)
                
                if result:
                    _, payload = result
                    # Disabling complete async dispatch here to avoid overwhelming 
                    # worker resources. If needed, we can wrap this in asyncio.create_task 
                    # with a concurrency limit (e.g. Semaphore).
                    await self.process_task(payload)
                    
        except asyncio.CancelledError:
            logger.info("Worker shutdown requested.")
        except Exception as e:
            logger.error(f"Worker encountered fatal error: {str(e)}", exc_info=True)
        finally:
            self.running = False
            if self.redis_client:
                await self.redis_client.close()
            logger.info("Worker stopped.")

def main():
    """CLI entry point for the worker node."""
    worker = CouncilWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user, shutting down...")

if __name__ == "__main__":
    main()
