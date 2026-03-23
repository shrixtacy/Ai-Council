import pytest
import asyncio
from ai_council.main import AICouncil
from ai_council.utils.config import AICouncilConfig
from ai_council.core.models import FinalResponse, ExecutionMode, TaskIntent

@pytest.mark.asyncio
async def test_full_pipeline_integration(temp_config_file):
    """
    Test the full 5-layer pipeline integration:
    Analysis -> Decomposition -> Routing -> Execution -> Arbitration -> Synthesis
    
    This verifies that data flows correctly between all components.
    """
    # 1. Setup AI Council with temporary config path
    council = AICouncil(config_path=temp_config_file)
    
    # 2. Define a complex task that requires all layers
    task_content = "Analyze the impact of quantum computing on modern cryptography."
    
    # 3. Process the request
    # This calls process_request which goes through all stages in ConcreteOrchestrationLayer
    response = await council.process_request(
        user_input=task_content,
        execution_mode=ExecutionMode.BALANCED
    )
    
    # 4. Verifications
    assert response is not None
    assert isinstance(response, FinalResponse)
    assert response.success is True
    assert len(response.content) > 0
    assert response.overall_confidence > 0
    
    # Check execution metadata to verify it went through the expected path
    metadata = response.execution_metadata
    assert "analysis" in metadata.execution_path
    assert "decomposition" in metadata.execution_path
    # Note: Depending on the implementation, 'execution' or 'synthesis' might be logged differently
    
    # Check that models were used
    assert len(response.models_used) >= 1
    
    # Check cost breakdown
    assert response.cost_breakdown.total_cost >= 0
    assert len(response.cost_breakdown.model_costs) > 0
    assert response.cost_breakdown.currency == "USD"

@pytest.mark.asyncio
async def test_pipeline_fast_mode(temp_config_file):
    """Test pipeline in FAST mode which should use fewer resources."""
    council = AICouncil(config_path=temp_config_file)
    
    response = await council.process_request(
        user_input="What is 2+2?",
        execution_mode=ExecutionMode.FAST
    )
    
    assert response.success is True
    assert len(response.content) > 0
    # In FAST mode, we expect at least one model used
    assert len(response.models_used) >= 1

@pytest.mark.asyncio
async def test_pipeline_with_orchestration_layer_directly(temp_config_file):
    """Test using the OrchestrationLayer directly instead of the AICouncil wrapper."""
    from ai_council.factory import AICouncilFactory
    
    config = AICouncilConfig.from_file(temp_config_file)
    factory = AICouncilFactory(config)
    orchestrator = factory.create_orchestration_layer()
    
    response = await orchestrator.process_request(
        user_input="Summarize the benefits of modular software design.",
        execution_mode=ExecutionMode.BALANCED
    )
    
    assert response.success is True
    assert "analysis" in response.execution_metadata.execution_path
