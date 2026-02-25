"""Unit tests for the MQExecutionAgent."""

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_council.core.models import Subtask, AgentResponse, SelfAssessment, TaskType, RiskLevel, Priority
from ai_council.execution.mq_agent import MQExecutionAgent

@pytest.fixture
def mock_subtask():
    return Subtask(
        id="test-subtask-123",
        parent_task_id="parent-123",
        content="Test content",
        task_type=TaskType.REASONING,
        priority=Priority.HIGH,
        risk_level=RiskLevel.MEDIUM,
    )

@pytest.fixture
def mock_model():
    model = MagicMock()
    model.get_model_id.return_value = "test-model-v1"
    return model

@pytest.fixture
def mock_redis():
    with patch("ai_council.execution.mq_agent.redis.from_url") as mock_from_url:
        redis_client = AsyncMock()
        mock_from_url.return_value = redis_client
        yield redis_client

@pytest.mark.asyncio
async def test_mq_agent_execute_success(mock_subtask, mock_model, mock_redis):
    # Setup the MQ Agent
    agent = MQExecutionAgent(redis_url="redis://dummy")
    
    # Mock the worker response
    worker_response = {
        "subtask_id": mock_subtask.id,
        "model_used": "test-model-v1",
        "content": "This is the result from the worker",
        "success": True,
        "self_assessment": {
            "confidence_score": 0.95,
            "risk_level": "low",
            "execution_time": 1.2
        }
    }
    
    mock_redis.blpop.return_value = ("ai_council:results:test-subtask-123", json.dumps(worker_response))
    
    # Execute the agent
    response = await agent.execute(mock_subtask, mock_model)
    
    # Assertions
    assert response.success is True
    assert response.subtask_id == mock_subtask.id
    assert response.content == "This is the result from the worker"
    assert response.self_assessment.confidence_score == 0.95
    
    # Verify Redis communication
    mock_redis.rpush.assert_called_once()
    args, _ = mock_redis.rpush.call_args
    assert args[0] == "ai_council:tasks"
    
    payload = json.loads(args[1])
    assert payload["subtask_id"] == mock_subtask.id
    assert payload["content"] == "Test content"
    
    mock_redis.blpop.assert_called_once_with(f"ai_council:results:{mock_subtask.id}", timeout=120)

@pytest.mark.asyncio
async def test_mq_agent_execute_timeout(mock_subtask, mock_model, mock_redis):
    agent = MQExecutionAgent(redis_url="redis://dummy", timeout_seconds=1)
    
    # Simulate a timeout (blpop returns None)
    mock_redis.blpop.return_value = None
    
    response = await agent.execute(mock_subtask, mock_model)
    
    # Assertions (Should fail gracefully per the design decision)
    assert response.success is False
    assert "Worker did not respond" in response.error_message
    assert response.self_assessment.risk_level == RiskLevel.CRITICAL
