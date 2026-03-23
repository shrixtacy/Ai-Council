import pytest
import asyncio
import time
from unittest.mock import AsyncMock
from ai_council.core.models import Subtask, TaskType, ModelCapabilities, AgentResponse, SelfAssessment, RiskLevel
from ai_council.core.interfaces import AIModel
from ai_council.routing.registry import ModelRegistryImpl
from ai_council.execution.agent import BaseExecutionAgent
from ai_council.core.failure_handling import RecoveryAction

class MockFailingModel(AIModel):
    def __init__(self, model_id, fallback_model_id=None):
        self.model_id = model_id
        self.fallback_model_id = fallback_model_id

    async def generate_response(self, prompt, **kwargs):
        raise Exception(f"Failure in {self.model_id}")

    def get_model_id(self):
        return self.model_id

class MockSuccessModel(AIModel):
    def __init__(self, model_id):
        self.model_id = model_id
        
    async def generate_response(self, prompt, **kwargs):
        return f"Successful response from {self.model_id}"

    def get_model_id(self):
        return self.model_id

@pytest.mark.asyncio
async def test_recursive_fallback_success():
    # Setup registry
    registry = ModelRegistryImpl()
    
    # Chain: Model A (fails) -> Model B (fails) -> Model C (succeeds)
    model_a = MockFailingModel("model-a", "model-b")
    model_b = MockFailingModel("model-b", "model-c")
    model_c = MockSuccessModel("model-c")
    
    registry.register_model(model_a, ModelCapabilities(task_types=[TaskType.REASONING]))
    registry.register_model(model_b, ModelCapabilities(task_types=[TaskType.REASONING]))
    registry.register_model(model_c, ModelCapabilities(task_types=[TaskType.REASONING]))
    
    # Setup agent
    agent = BaseExecutionAgent(model_registry=registry, max_retries=0)
    
    # Mock resilience manager to return fallback actions
    from ai_council.core.failure_handling import resilience_manager
    original_handle_failure = resilience_manager.handle_failure
    
    def mocked_handle_failure(event):
        if event.model_id == "model-a":
            return RecoveryAction(action_type="fallback", fallback_model="model-b")
        if event.model_id == "model-b":
            return RecoveryAction(action_type="fallback", fallback_model="model-c")
        return RecoveryAction(action_type="fail")
        
    resilience_manager.handle_failure = mocked_handle_failure
    
    try:
        subtask = Subtask(content="Test task", task_type=TaskType.REASONING)
        print("\nStarting execution with model_a")
        response = await agent.execute(subtask, model_a)
        print(f"Final response metadata: {response.metadata}")
        
        assert response.success is True
        assert response.model_used == "model-c"
        assert "Successful response from model-c" in response.content
        assert response.metadata.get("fallback_depth") == 2
        assert response.metadata.get("is_fallback") is True
    finally:
        resilience_manager.handle_failure = original_handle_failure

@pytest.mark.asyncio
async def test_recursive_fallback_max_depth():
    # Setup registry
    registry = ModelRegistryImpl()
    
    # Create a loop or long chain to test depth limit
    models = [MockFailingModel(f"model-{i}", f"model-{i+1}") for i in range(5)]
    for i, model in enumerate(models):
        registry.register_model(model, ModelCapabilities(task_types=[TaskType.REASONING]))
        
    agent = BaseExecutionAgent(model_registry=registry, max_retries=0)
    
    from ai_council.core.failure_handling import resilience_manager
    original_handle_failure = resilience_manager.handle_failure
    
    def mocked_handle_failure(event):
        model_index = int(event.model_id.split("-")[1])
        return RecoveryAction(action_type="fallback", fallback_model=f"model-{model_index + 1}")
        
    resilience_manager.handle_failure = mocked_handle_failure
    
    try:
        subtask = Subtask(content="Test task", task_type=TaskType.REASONING)
        response = await agent.execute(subtask, models[0])
        
        assert response.success is False
        assert "Maximum fallback depth" in response.error_message
    finally:
        resilience_manager.handle_failure = original_handle_failure

@pytest.mark.asyncio
async def test_fallback_chain_iteration():
    # Setup registry
    registry = ModelRegistryImpl()
    
    # Models
    model_primary = MockFailingModel("model-primary")
    model_fallback_1 = MockFailingModel("model-fallback-1")
    model_fallback_2 = MockFailingModel("model-fallback-2")
    model_fallback_3 = MockSuccessModel("model-fallback-3")
    
    for m in [model_primary, model_fallback_1, model_fallback_2, model_fallback_3]:
        registry.register_model(m, ModelCapabilities(task_types=[TaskType.REASONING]))
        
    agent = BaseExecutionAgent(model_registry=registry, max_retries=0)
    
    from ai_council.core.failure_handling import resilience_manager, RecoveryAction, CircuitBreakerState
    
    # Reset circuit breaker to avoid test pollution
    cb = resilience_manager.get_circuit_breaker("model_api")
    if cb:
        cb.state = CircuitBreakerState.CLOSED
        cb.store.reset_failure_count("model_api")
        cb.store.clear_failure_times("model_api")
    
    original_handle_failure = resilience_manager.handle_failure
    
    def mocked_handle_failure(event):
        # We simulate that the primary model fails and returns the full chain in metadata
        if event.model_id == "model-primary":
            return RecoveryAction(
                action_type="unhandled_failure", 
                should_retry=False, 
                metadata={"fallback_models": ["model-fallback-1", "model-fallback-2", "model-fallback-3"]}
            )
        # For the fallbacks, they just fail normally
        return RecoveryAction(action_type="fail")
        
    resilience_manager.handle_failure = mocked_handle_failure
    
    try:
        subtask = Subtask(content="Test task", task_type=TaskType.REASONING)
        response = await agent.execute(subtask, model_primary)
        
        assert response.success is True
        assert response.model_used == "model-fallback-3"
        assert "Successful response from model-fallback-3" in response.content
        # Check that fallback failures are tracked
        assert "fallback_failures" in response.metadata
        assert len(response.metadata["fallback_failures"]) == 2
        assert response.metadata["fallback_failures"][0]["model_id"] == "model-fallback-1"
        assert response.metadata["fallback_failures"][1]["model_id"] == "model-fallback-2"
    finally:
        resilience_manager.handle_failure = original_handle_failure
