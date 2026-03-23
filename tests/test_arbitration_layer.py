import pytest
from ai_council.arbitration.layer import ConcreteArbitrationLayer, NoOpArbitrationLayer
from ai_council.core.models import AgentResponse, SelfAssessment, RiskLevel
from ai_council.core.interfaces import ArbitrationResult, Conflict, Resolution

@pytest.fixture
def arbitration_layer():
    return ConcreteArbitrationLayer(confidence_threshold=0.7, quality_weight=0.6)

@pytest.mark.asyncio
async def test_arbitrate_empty_responses(arbitration_layer):
    result = await arbitration_layer.arbitrate([])
    assert isinstance(result, ArbitrationResult)
    assert len(result.validated_responses) == 0
    assert len(result.conflicts_resolved) == 0

@pytest.mark.asyncio
async def test_arbitrate_single_valid_response(arbitration_layer, sample_agent_response):
    result = await arbitration_layer.arbitrate([sample_agent_response])
    assert len(result.validated_responses) == 1
    assert result.validated_responses[0] == sample_agent_response
    assert len(result.conflicts_resolved) == 0

@pytest.mark.asyncio
async def test_arbitrate_single_invalid_response(arbitration_layer, sample_subtask):
    # Low confidence response
    low_confidence_assessment = SelfAssessment(
        confidence_score=0.5,
        assumptions=[],
        risk_level=RiskLevel.LOW,
        estimated_cost=0.01,
        token_usage=100,
        execution_time=1.0,
        model_used="test-model"
    )
    invalid_response = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="test-model",
        content="Poor quality response",
        self_assessment=low_confidence_assessment,
        success=True
    )
    result = await arbitration_layer.arbitrate([invalid_response])
    assert len(result.validated_responses) == 0

@pytest.mark.asyncio
async def test_detect_content_contradiction_length(arbitration_layer, sample_subtask):
    # One short response, one very long response
    resp1 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-a",
        content="Short.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="a")
    )
    resp2 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-b",
        content="This is a much longer response that goes into great detail about many things to ensure it is significantly longer than the first one." * 10,
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="b")
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "content_contradiction" for c in conflicts)

@pytest.mark.asyncio
async def test_detect_content_contradiction_sentiment(arbitration_layer, sample_subtask):
    # One positive, one negative
    resp1 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-a",
        content="The result is true and correct.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="a")
    )
    resp2 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-b",
        content="The result is false and incorrect.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="b")
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "content_contradiction" and "sentiment" in c.description for c in conflicts)

@pytest.mark.asyncio
async def test_detect_confidence_conflict(arbitration_layer, sample_subtask):
    resp1 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-a",
        content="Response A",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.95, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="a")
    )
    resp2 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-b",
        content="Response B",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.4, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="b")
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "confidence_conflict" for c in conflicts)

@pytest.mark.asyncio
async def test_detect_quality_conflict(arbitration_layer, sample_subtask):
    # High quality: high confidence, low risk, no assumptions, good length
    resp1 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-a",
        content="Reasonably long and detailed content " * 10,
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.95, assumptions=[], risk_level=RiskLevel.LOW, estimated_cost=0, token_usage=0, execution_time=0, model_used="a")
    )
    # Low quality: low confidence, high risk, many assumptions, short
    resp2 = AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="model-b",
        content="Short",
        success=True,
        self_assessment=SelfAssessment(
            confidence_score=0.75, 
            assumptions=["a", "b", "c", "d", "e"], 
            risk_level=RiskLevel.HIGH, 
            estimated_cost=0, 
            token_usage=0, 
            execution_time=0, 
            model_used="b"
        )
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "quality_conflict" for c in conflicts)

@pytest.mark.asyncio
async def test_resolve_contradiction_types(arbitration_layer):
    # Mock conflicts
    conflict_content = Conflict(response_ids=["a", "b"], conflict_type="content_contradiction", description="desc")
    conflict_confidence = Conflict(response_ids=["a", "b"], conflict_type="confidence_conflict", description="desc")
    conflict_quality = Conflict(response_ids=["a", "b"], conflict_type="quality_conflict", description="desc")
    conflict_unknown = Conflict(response_ids=["a", "b"], conflict_type="unknown", description="desc")

    res1 = await arbitration_layer.resolve_contradiction(conflict_content)
    assert res1.chosen_response_id == "a"
    assert "content" in res1.reasoning

    res2 = await arbitration_layer.resolve_contradiction(conflict_confidence)
    assert res2.chosen_response_id == "a"
    assert "confidence" in res2.reasoning

    res3 = await arbitration_layer.resolve_contradiction(conflict_quality)
    assert res3.chosen_response_id == "a"
    assert "quality" in res3.reasoning

    res4 = await arbitration_layer.resolve_contradiction(conflict_unknown)
    assert res4.chosen_response_id == "a"
    assert "Unknown" in res4.reasoning

def test_risk_level_to_score(arbitration_layer):
    assert arbitration_layer._risk_level_to_score(RiskLevel.LOW) == 1.0
    assert arbitration_layer._risk_level_to_score(RiskLevel.CRITICAL) == 0.1
    assert arbitration_layer._risk_level_to_score(None) == 0.5

def test_validate_response_quality(arbitration_layer, sample_agent_response):
    assert arbitration_layer._validate_response_quality(sample_agent_response) is True
    
    # Failed response
    sample_agent_response.success = False
    assert arbitration_layer._validate_response_quality(sample_agent_response) is False
    sample_agent_response.success = True
    
    # Empty content
    sample_agent_response.content = " "
    assert arbitration_layer._validate_response_quality(sample_agent_response) is False
    sample_agent_response.content = "Valid content"
    
    # Critical risk
    # Create a new response instance instead of mutating the shared fixture
    high_risk_response = AgentResponse(
        subtask_id=sample_agent_response.subtask_id,
        model_used=sample_agent_response.model_used,
        content=sample_agent_response.content,
        success=sample_agent_response.success,
        self_assessment=SelfAssessment(
            confidence_score=sample_agent_response.self_assessment.confidence_score,
            risk_level=RiskLevel.CRITICAL
        )
    )
    assert arbitration_layer._validate_response_quality(high_risk_response) is False

@pytest.mark.asyncio
async def test_noop_arbitration_layer():
    layer = NoOpArbitrationLayer()
    resp = AgentResponse(subtask_id="1", model_used="m", content="c", success=True, self_assessment=None)
    result = await layer.arbitrate([resp])
    assert len(result.validated_responses) == 1
    assert result.validated_responses[0] == resp
    assert len(result.conflicts_resolved) == 0
    
    conflicts = await layer.detect_conflicts([resp])
    assert conflicts == []
    
    resolution = await layer.resolve_contradiction(Conflict(response_ids=["a"], conflict_type="c", description="d"))
    assert resolution.chosen_response_id == "a"
    assert "no-op" in resolution.reasoning.lower()
