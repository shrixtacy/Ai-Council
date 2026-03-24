import pytest
from ai_council.synthesis.layer import SynthesisLayerImpl, NoOpSynthesisLayer
from ai_council.core.models import AgentResponse, SelfAssessment, RiskLevel, FinalResponse
from ai_council.core.interfaces import ExecutionMetadata

@pytest.fixture
def synthesis_layer():
    return SynthesisLayerImpl()

@pytest.fixture
def noop_synthesis_layer():
    return NoOpSynthesisLayer()

@pytest.mark.asyncio
async def test_synthesize_no_responses(synthesis_layer):
    result = await synthesis_layer.synthesize([])
    assert result.success is False
    assert "No validated responses" in result.error_message

@pytest.mark.asyncio
async def test_synthesize_all_failed_responses(synthesis_layer):
    resp = AgentResponse(
        subtask_id="t1",
        model_used="m1",
        content="fail",
        success=False,
        error_message="Error"
    )
    result = await synthesis_layer.synthesize([resp])
    assert result.success is False
    assert "No successful responses" in result.error_message

@pytest.mark.asyncio
async def test_remove_redundancy(synthesis_layer):
    # Overlapping content
    contents = [
        "This is a test message for synthesis",
        "This is a test message for synthesis", # Identical
        "Something completely different here"
    ]
    deduplicated = synthesis_layer._remove_redundancy(contents)
    assert len(deduplicated) == 2
    assert deduplicated[0] == contents[0]
    assert deduplicated[1] == contents[2]

@pytest.mark.asyncio
async def test_synthesize_content_combination(synthesis_layer):
    contents = [
        "The primary goal is stability.",
        "The primary goal is stability. We also need performance."
    ]
    # sorted_contents[0] will be the second one (longer)
    synthesized = synthesis_layer._synthesize_content(contents)
    assert synthesized == contents[1]
    
    contents2 = [
        "Stability is key.",
        "Performance is also important."
    ]
    synthesized2 = synthesis_layer._synthesize_content(contents2)
    assert "Stability is key" in synthesized2
    assert "Performance is also important" in synthesized2
    assert "Additionally," in synthesized2

@pytest.mark.asyncio
async def test_normalize_output_formatting(synthesis_layer):
    raw = "  hello world  \n\n\n  new line  "
    normalized = await synthesis_layer.normalize_output(raw)
    assert normalized == "hello world. new line."
    
    # Tone normalization
    raw_tone = "In conclusion, it is important to note that the system is stable."
    normalized_tone = await synthesis_layer.normalize_output(raw_tone)
    assert "In conclusion" not in normalized_tone
    assert "it is important to note that" not in normalized_tone
    assert normalized_tone == "the system is stable."

@pytest.mark.asyncio
async def test_calculate_overall_confidence(synthesis_layer):
    resps = [
        AgentResponse(
            subtask_id="t1", model_used="m1", content="c1", success=True,
            self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW)
        ),
        AgentResponse(
            subtask_id="t1", model_used="m2", content="c2", success=True,
            self_assessment=SelfAssessment(confidence_score=0.7, risk_level=RiskLevel.HIGH)
        )
    ]
    # Weights: Low=1.0, High=0.6
    # (0.9 * 1.0 + 0.7 * 0.6) / (1.0 + 0.6) = (0.9 + 0.42) / 1.6 = 1.32 / 1.6 = 0.825
    # Penalty for 2 responses: min(0.1, (2-1)*0.02) = 0.02
    # 0.825 - 0.02 = 0.805
    conf = synthesis_layer._calculate_overall_confidence(resps)
    assert 0.8 < conf < 0.81

@pytest.mark.asyncio
async def test_synthesize_full_pipeline(synthesis_layer):
    resps = [
        AgentResponse(
            subtask_id="t1", model_used="gpt-4", content="First part of the answer.", success=True,
            self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, estimated_cost=0.02, token_usage=100)
        ),
        AgentResponse(
            subtask_id="t1", model_used="claude-3", content="Second part. Unique info here.", success=True,
            self_assessment=SelfAssessment(confidence_score=0.8, risk_level=RiskLevel.MEDIUM, estimated_cost=0.01, token_usage=50)
        )
    ]
    final = await synthesis_layer.synthesize(resps)
    assert final.success is True
    assert "First part" in final.content
    assert "Unique info" in final.content
    assert final.overall_confidence > 0
    assert final.cost_breakdown.total_cost == 0.03
    assert "gpt-4" in final.models_used
    assert "claude-3" in final.models_used

@pytest.mark.asyncio
async def test_noop_synthesis(noop_synthesis_layer):
    resps = [
        AgentResponse(
            subtask_id="t1", model_used="m1", content="First", success=True,
            self_assessment=SelfAssessment(confidence_score=0.9, estimated_cost=0.01)
        ),
        AgentResponse(
            subtask_id="t1", model_used="m2", content="Second", success=True
        )
    ]
    final = await noop_synthesis_layer.synthesize(resps)
    assert final.content == "First"
    assert final.overall_confidence == 0.9
    assert final.models_used == ["m1"]
    
    # Test empty
    final_empty = await noop_synthesis_layer.synthesize([])
    assert final_empty.success is False
    
    # Test all failed
    final_failed = await noop_synthesis_layer.synthesize([
        AgentResponse(subtask_id="t1", model_used="m1", success=False, error_message="X")
    ])
    assert final_failed.success is False

@pytest.mark.asyncio
async def test_attach_metadata(synthesis_layer):
    final = FinalResponse(content="test", overall_confidence=0.9, success=True)
    meta = ExecutionMetadata()
    meta.execution_path = ["p1"]
    attached = await synthesis_layer.attach_metadata(final, meta)
    assert attached.execution_metadata.execution_path == ["p1"]
    assert attached.content == "test"
