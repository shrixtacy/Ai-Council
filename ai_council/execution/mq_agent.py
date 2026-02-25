"""Message Queue Execution Agent for distributed task execution."""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional

import redis.asyncio as redis

from ..core.interfaces import ExecutionAgent, AIModel, ModelError, FailureResponse
from ..core.models import Subtask, AgentResponse, SelfAssessment, RiskLevel, Priority, TaskType
from ..core.failure_handling import FailureType, create_failure_event, resilience_manager

logger = logging.getLogger(__name__)

class MQExecutionAgent(ExecutionAgent):
    """
    Execution Agent that acts as a producer to a Message Queue (Redis).
    Instead of executing tasks locally, it pushes them to a queue and waits
    for a worker node to process and return the result.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", timeout_seconds: int = 120):
        self.redis_url = redis_url
        self.timeout_seconds = timeout_seconds
        self.redis_client = None
        self.task_queue = "ai_council:tasks"
        self._ensure_connection()

    def _ensure_connection(self):
        """Create a Redis connection pool if not already established."""
        if not self.redis_client:
            from urllib.parse import urlparse
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            parsed_url = urlparse(self.redis_url)
            sanitized_netloc = f"***:***@{parsed_url.hostname}:{parsed_url.port}" if parsed_url.password else f"{parsed_url.hostname}:{parsed_url.port}"
            sanitized_url = parsed_url._replace(netloc=sanitized_netloc).geturl()
            logger.info(f"MQExecutionAgent initialized with Redis at {sanitized_url}")

    async def execute(self, subtask: Subtask, model: AIModel) -> AgentResponse:
        start_time = time.time()
        
        try:
            model_id = model.get_model_id()
            response_key = f"ai_council:results:{subtask.id}"
            payload = self._serialize_task(subtask, model_id)
            
            self._ensure_connection()
            
            logger.info(f"Pushing subtask {subtask.id} to MQ for model {model_id}")
            await self.redis_client.rpush(self.task_queue, json.dumps(payload))
            
            logger.debug(f"Waiting for response on {response_key}")
            result = await self.redis_client.blpop(response_key, timeout=self.timeout_seconds)
            
            if not result:
                raise TimeoutError(f"Worker did not respond within {self.timeout_seconds} seconds")
            
            _, response_json = result
            return self._deserialize_response(response_json, start_time)
            
        except Exception as e:
            failed_model_id = model_id if 'model_id' in locals() else "unknown"
            logger.error(f"MQ Execution failed for subtask {subtask.id}: {str(e)}")
            
            failure_event = create_failure_event(
                failure_type=FailureType.TIMEOUT if isinstance(e, TimeoutError) else FailureType.API_FAILURE,
                component="mq_execution_agent",
                error_message=str(e),
                subtask_id=subtask.id,
                model_id=failed_model_id,
                severity=RiskLevel.HIGH
            )
            resilience_manager.handle_failure(failure_event)
            
            return AgentResponse(
                subtask_id=subtask.id,
                model_used=failed_model_id,
                content="",
                success=False,
                error_message=f"MQ Execution failed: {str(e)}",
                self_assessment=SelfAssessment(
                    confidence_score=0.0,
                    risk_level=RiskLevel.CRITICAL,
                    model_used=failed_model_id,
                    execution_time=time.time() - start_time
                )
            )

    def _serialize_task(self, subtask: Subtask, model_id: str) -> Dict[str, Any]:
        return {
            "subtask_id": subtask.id,
            "parent_task_id": subtask.parent_task_id,
            "content": subtask.content,
            "task_type": subtask.task_type.value if subtask.task_type else None,
            "priority": subtask.priority.value if subtask.priority else Priority.MEDIUM.value,
            "risk_level": subtask.risk_level.value if subtask.risk_level else RiskLevel.LOW.value,
            "accuracy_requirement": subtask.accuracy_requirement,
            "estimated_cost": subtask.estimated_cost,
            "metadata": subtask.metadata,
            "model_id": model_id
        }

    def _deserialize_response(self, response_json: str, start_time: float) -> AgentResponse:
        try:
            data = json.loads(response_json)
            sa_data = data.get("self_assessment", {})
            risk_level_str = sa_data.get("risk_level", RiskLevel.LOW.value)
            
            try:
                risk_level = RiskLevel(risk_level_str) if isinstance(risk_level_str, str) else risk_level_str
            except ValueError:
                risk_level = RiskLevel.LOW
                
            self_assessment = SelfAssessment(
                confidence_score=sa_data.get("confidence_score", 0.0),
                assumptions=sa_data.get("assumptions", []),
                risk_level=risk_level,
                estimated_cost=sa_data.get("estimated_cost", 0.0),
                token_usage=sa_data.get("token_usage", 0),
                execution_time=sa_data.get("execution_time", time.time() - start_time),
                model_used=sa_data.get("model_used", ""),
            )
            
            return AgentResponse(
                subtask_id=data.get("subtask_id", "") or "unknown_subtask",
                model_used=data.get("model_used", "") or "unknown_model",
                content=data.get("content", ""),
                self_assessment=self_assessment,
                success=data.get("success", True),
                error_message=data.get("error_message"),
                metadata=data.get("metadata", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to deserialize worker response: {str(e)}")
            raise

    async def generate_self_assessment(self, response: str, subtask: Subtask) -> SelfAssessment:
        return SelfAssessment()

    async def handle_model_failure(self, error: ModelError) -> FailureResponse:
        return FailureResponse(
            error_type="mq_error",
            error_message=str(error),
            retry_suggested=True
        )

    async def close(self):
        if self.redis_client:
            await self.redis_client.close()
