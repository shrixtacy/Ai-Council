"""Worker node entry point for AI Council."""

import os
import json
import time
import asyncio
import logging
import uuid
from typing import Dict, Any, Tuple, Union
from pathlib import Path

import redis.asyncio as redis

from ai_council.utils.config import load_config
from ai_council.utils.logging import configure_logging, get_logger
from ai_council.factory import AICouncilFactory
from ai_council.core.models import Subtask, AgentResponse, SelfAssessment, RiskLevel, Priority, TaskType

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = get_logger("ai_council.worker")

class CouncilWorker:
    def __init__(self, config_path: Union[str, Path, None] = None):
        if isinstance(config_path, str):
            config_path = Path(config_path)
            
        self.config = load_config(config_path)
        configure_logging(
            level=self.config.logging.level,
            format_json=self.config.logging.format_json,
            include_timestamp=self.config.logging.include_timestamp,
            include_caller=self.config.logging.include_caller,
        )
        
        self.worker_id = uuid.uuid4().hex
        self.redis_url = self.config.execution.redis_url
        self.redis_client = None
        self.task_queue = "ai_council:tasks"
        self.processing_queue = f"{self.task_queue}:processing:{self.worker_id}"
        
        logger.info("Initializing worker factory and dependencies...")
        self.factory = AICouncilFactory(self.config)
        self.model_registry = self.factory.model_registry
        
        self.models = self.factory.create_models_from_config()
        for name, model in self.models.items():
            logger.info(f"Worker loaded model: {name}")

        from ai_council.execution.agent import BaseExecutionAgent
        self.execution_agent = BaseExecutionAgent()
        self.running = False

    async def _deserialize_task(self, data: Dict[str, Any]) -> Tuple[Subtask, str]:
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
        sa_dict = {}
        if response.self_assessment:
            sa = response.self_assessment
            sa_dict = {
                "confidence_score": sa.confidence_score,
                "assumptions": sa.assumptions,
                "risk_level": sa.risk_level.value if isinstance(sa.risk_level, RiskLevel) else str(sa.risk_level),
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

    async def process_task(self, payload_json: str) -> bool:
        if not self.redis_client:
            logger.error("Redis client is not initialized. Cannot process task.")
            return False

        start_time = time.time()
        subtask_id = "unknown"
        response_key = "unknown"
        
        try:
            data = json.loads(payload_json)
            subtask_id = data.get("subtask_id", "unknown")
            response_key = f"ai_council:results:{subtask_id}"
            
            logger.info(f"Worker processing subtask: {subtask_id}")
            
            subtask, model_id = await self._deserialize_task(data)
            
            model = self.models.get(model_id)
            if not model:
                model = self.model_registry.get_model(model_id)
            
            if not model:
                raise ValueError(f"Model {model_id} not found in worker registry")
            
            response: AgentResponse = await self.execution_agent.execute(subtask, model)
            
            serialized_response = self._serialize_response(response)
            await self.redis_client.rpush(response_key, serialized_response)
            await self.redis_client.expire(response_key, 300)
            
            logger.info(f"Worker completed subtask {subtask_id} in {time.time() - start_time:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Worker failed processing subtask {subtask_id}: {str(e)}", exc_info=True)
            
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
                    return True
                except Exception as pub_e:
                    logger.critical(f"Worker failed to publish error for {subtask_id}: {str(pub_e)}")
                    return False
            return False

    async def _heartbeat_loop(self):
        heartbeat_key = f"ai_council:worker:heartbeat:{self.worker_id}"
        try:
            while self.running:
                if self.redis_client:
                    await self.redis_client.set(heartbeat_key, "1", ex=60)
                await asyncio.sleep(20)
        except asyncio.CancelledError:
            pass
        finally:
            if self.redis_client:
                await self.redis_client.delete(heartbeat_key)

    async def _recover_stale_tasks(self):
        """Move tasks from orphaned processing_queues back to task_queue."""
        logger.info("Checking for stale tasks from dead workers...")
        try:
            keys = await self.redis_client.keys(f"{self.task_queue}:processing:*")
            for key in keys:
                worker_id = key.split(":")[-1]
                heartbeat_key = f"ai_council:worker:heartbeat:{worker_id}"
                
                is_alive = await self.redis_client.exists(heartbeat_key)
                if not is_alive:
                    logger.info(f"Recovering tasks from dead worker {worker_id}")
                    while True:
                        payload = await self.redis_client.lmove(key, self.task_queue, src="RIGHT", dest="LEFT")
                        if not payload:
                            break
                        logger.info("Recovered a stale task.")
        except Exception as e:
            logger.error(f"Failed to recover stale tasks: {str(e)}")

    async def run(self):
        self.running = True
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        
        from urllib.parse import urlparse
        parsed_url = urlparse(self.redis_url)
        sanitized_netloc = f"***:***@{parsed_url.hostname}:{parsed_url.port}" if parsed_url.password else f"{parsed_url.hostname}:{parsed_url.port}"
        sanitized_url = parsed_url._replace(netloc=sanitized_netloc).geturl()
        
        logger.info(f"Worker {self.worker_id} started. Listening on Redis: {sanitized_url}, queue: {self.task_queue}")
        
        await self._recover_stale_tasks()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        try:
            while self.running:
                logger.debug("Waiting for next task...")
                payload = await self.redis_client.blmove(
                    self.task_queue, 
                    self.processing_queue, 
                    timeout=5,
                    src="RIGHT",
                    dest="LEFT"
                )
                
                if payload:
                    success = await self.process_task(payload)
                    if success:
                        await self.redis_client.lrem(self.processing_queue, 1, payload)
                    else:
                        logger.warning(f"Task processing failed to publish, leaving in queue: {payload}")
                    
        except asyncio.CancelledError:
            logger.info("Worker shutdown requested.")
        except Exception as e:
            logger.error(f"Worker encountered fatal error: {str(e)}", exc_info=True)
        finally:
            self.running = False
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            if self.redis_client:
                await self.redis_client.close()
            logger.info("Worker stopped.")

def main():
    worker = CouncilWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user, shutting down...")

if __name__ == "__main__":
    main()
