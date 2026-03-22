import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

from ai_council.core.models import Subtask, TaskType, Priority, RiskLevel
from ai_council.execution.mq_agent import MQExecutionAgent

class MockRedis:
    def __init__(self):
        self.queues = {}
        
    async def rpush(self, key, value):
        if key not in self.queues:
            self.queues[key] = asyncio.Queue()
        await self.queues[key].put(value)
        
    async def blpop(self, keys, timeout=0):
        if isinstance(keys, str):
            keys = [keys]
            
        key = keys[0]
        if key not in self.queues:
            self.queues[key] = asyncio.Queue()
            
        try:
            val = await asyncio.wait_for(self.queues[key].get(), timeout)
            return (key, val)
        except asyncio.TimeoutError:
            return None

@pytest.fixture
def mock_subtask():
    return Subtask(
        id="test-subtask-integration",
        parent_task_id="parent-123",
        content="Test content for integration",
        task_type=TaskType.REASONING,
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
    )

@pytest.fixture
def mock_model():
    model = MagicMock()
    model.get_model_id.return_value = "test-model-integration"
    return model

@pytest.mark.asyncio
async def test_mq_worker_producer_integration(mock_subtask, mock_model):
    mock_redis = MockRedis()
    
    with patch("ai_council.execution.mq_agent.redis.from_url", return_value=mock_redis):
        agent = MQExecutionAgent(redis_url="redis://dummy", timeout_seconds=2)
        
        async def mock_worker():
            result = await mock_redis.blpop("ai_council:tasks", timeout=1)
            if not result:
                return
            
            queue_name, payload = result
            task_data = json.loads(payload)
            subtask_id = task_data["subtask_id"]
            
            await asyncio.sleep(0.1)
            
            worker_response = {
                "subtask_id": subtask_id,
                "model_used": task_data["model_id"],
                "content": "Integration test response",
                "success": True,
                "self_assessment": {
                    "confidence_score": 0.99,
                    "risk_level": "low",
                    "execution_time": 0.1
                }
            }
            await mock_redis.rpush(f"ai_council:results:{subtask_id}", json.dumps(worker_response))
            
        worker_task = asyncio.create_task(mock_worker())
        
        response = await agent.execute(mock_subtask, mock_model)
        
        await worker_task
        
        assert response.success is True
        assert response.subtask_id == mock_subtask.id
        assert response.content == "Integration test response"
        assert response.self_assessment.confidence_score == 0.99
