import pytest
from ai_council.synthesis.layer import SynthesisLayerImpl, NoOpSynthesisLayer
from ai_council.core.models import AgentResponse, SelfAssessment, RiskLevel, FinalResponse, CostBreakdown
from ai_council.core.interfaces import ExecutionMetadata

@pytest.fixture
def synthesis_layer():
    return SynthesisLayerImpl()

@pytest.mark.asyncio
async def test_synthesize_empty_responses(synthesis_layer):
    result = await synthesis_layer.synthesize([])
    assert isinstance(result, FinalResponse)
    assert result.success is False
    assert "No validated responses" in result.error_message

@pytest.mark.asyncio
async def test_synthesize_no_successful_responses(synthesis_layer):
    resp = AgentResponse(
        subtask_id="1", model_used="m1", content="err", success=False, error_message="fail"
    )
    result = await synthesis_layer.synthesize([resp])
    assert result.success is False
    assert "No successful responses" in result.error_message

@pytest.mark.asyncio
async def test_synthesize_single_response(synthesis_layer, sample_agent_response):
    result = await synthesis_layer.synthesize([sample_agent_response])
    assert result.success is True
    assert result.content == sample_agent_response.content
    assert result.overall_confidence == sample_agent_response.self_assessment.confidence_score
    assert result.models_used == [sample_agent_response.model_used]

@pytest.mark.asyncio
async def test_synthesize_multiple_responses_redundancy(synthesis_layer, sample_subtask):
    resp1 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-a",
        content="This is the core information about renewable energy.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, estimated_cost=0.01, token_usage=100, execution_time=1.0, model_used="a")
    )
    # Very similar to resp1
    resp2 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-b",
        content="This is the CORE information about RENEWABLE energy.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.85, risk_level=RiskLevel.LOW, estimated_cost=0.01, token_usage=100, execution_time=1.1, model_used="b")
    )
    # Unique additional info
    resp3 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-c",
        content="Solar power is a major part of it.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.8, risk_level=RiskLevel.LOW, estimated_cost=0.01, token_usage=100, execution_time=1.2, model_used="c")
    )
    
    result = await synthesis_layer.synthesize([resp1, resp2, resp3])
    assert result.success is True
    # Should contain resp1 and unique parts of resp3, but not resp2 (redundant)
    assert "core information" in result.content
    assert "Solar power" in result.content
    # Explicitly check for redundancy removal: "core information" should only appear once
    assert result.content.count("core information") == 1
    # Note: the specific synthesis logic might add "Additionally, ..."
    assert result.overall_confidence > 0.7  # Weighted avg with multiple response penalty

@pytest.mark.asyncio
async def test_normalize_output(synthesis_layer):
    raw_content = "  Too   many   spaces. Missing punctuation\n\n\n\nDouble break. "
    normalized = await synthesis_layer.normalize_output(raw_content)
    assert "  " not in normalized
    assert "Too many spaces." in normalized
    assert "Missing punctuation." in normalized
    assert "\n\n\n" not in normalized

@pytest.mark.asyncio
async def test_normalize_tone(synthesis_layer):
    content = "In conclusion, the project is good. Please note that it is important to note that it works."
    normalized = await synthesis_layer.normalize_output(content)
    normalized_lower = normalized.lower()
    assert "in conclusion" not in normalized_lower
    assert "please note that" not in normalized_lower
    assert "it is important to note that" not in normalized_lower

@pytest.mark.asyncio
async def test_calculate_overall_confidence_risk_weighting(synthesis_layer):
    resp_low = AgentResponse(
        subtask_id="1", model_used="a", content="c", success=True,
        self_assessment=SelfAssessment(confidence_score=1.0, risk_level=RiskLevel.LOW)
    )
    resp_high = AgentResponse(
        subtask_id="1", model_used="b", content="c2", success=True,
        self_assessment=SelfAssessment(confidence_score=1.0, risk_level=RiskLevel.HIGH)
    )
    
    # Final = 0.98
    result = await synthesis_layer.synthesize([resp_low, resp_high])
    assert result.overall_confidence == pytest.approx(0.98)

@pytest.mark.asyncio
async def test_noop_synthesis_layer_success():
    layer = NoOpSynthesisLayer()
    resp = AgentResponse(
        subtask_id="1", model_used="m", content="Content", success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, estimated_cost=0.1, execution_time=1.0)
    )
    
    result = await layer.synthesize([resp])
    assert result.success is True
    assert result.content == "Content"
    assert result.overall_confidence == pytest.approx(0.9)
    assert result.cost_breakdown.total_cost == pytest.approx(0.1)

@pytest.mark.asyncio
async def test_noop_synthesis_layer_empty_input():
    layer = NoOpSynthesisLayer()
    result_empty = await layer.synthesize([])
    assert result_empty.success is False

@pytest.mark.asyncio
async def test_noop_synthesis_layer_failure():
    layer = NoOpSynthesisLayer()
    resp_fail = AgentResponse(subtask_id="1", model_used="m", content="", success=False, error_message="e")
    result_fail = await layer.synthesize([resp_fail])
    assert result_fail.success is False

@pytest.mark.asyncio
async def test_attach_metadata(synthesis_layer):
    resp = FinalResponse(content="c", overall_confidence=0.9, success=True)
    meta = ExecutionMetadata()
    meta.models_used = ["m1"]
    
    updated = await synthesis_layer.attach_metadata(resp, meta)
    assert updated.execution_metadata == meta
    assert updated.content == "c"
