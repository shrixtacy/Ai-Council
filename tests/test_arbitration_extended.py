import pytest
from unittest.mock import MagicMock

from ai_council.arbitration.layer import ConcreteArbitrationLayer
from ai_council.core.models import AgentResponse, SelfAssessment, RiskLevel
from ai_council.core.interfaces import Conflict, Resolution

@pytest.fixture
def arbitration_layer():
    return ConcreteArbitrationLayer(confidence_threshold=0.7)

@pytest.mark.asyncio
async def test_arbitrate_multiple_responses_with_conflicts(arbitration_layer):
    # Setup subtask responses with content contradiction
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="The answer is YES. It is correct.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.5)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="The answer is NO. It is incorrect and invalid.",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.8, risk_level=RiskLevel.MEDIUM, assumptions=["maybe"], execution_time=0.6)
    )
    
    result = await arbitration_layer.arbitrate([resp1, resp2])
    
    assert len(result.conflicts_resolved) > 0
    assert len(result.validated_responses) >= 1
    # Check that it resolved based on highest confidence/quality (simplified in current implementation)
    # The current implementation chooses the first one for content contradiction
    assert result.validated_responses[0].model_used == "model_a"

@pytest.mark.asyncio
async def test_detect_conflicts_single_response_in_group(arbitration_layer):
    # Coverage for line 101 - continue if len < 2
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="Single response",
        success=True,
        self_assessment=SelfAssessment(execution_time=0.1)
    )
    conflicts = await arbitration_layer.detect_conflicts([resp1])
    assert len(conflicts) == 0

@pytest.mark.asyncio
async def test_detect_content_contradiction_short_returns(arbitration_layer):
    # Coverage for line 151 - return if len(contents) < 2
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="success",
        success=True,
        self_assessment=SelfAssessment(execution_time=0.1)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="",
        success=False, # Not successful, should be filtered out
        error_message="Simulated error",
        self_assessment=SelfAssessment(execution_time=0.1)
    )
    conflicts = arbitration_layer._detect_content_contradictions([resp1, resp2])
    assert len(conflicts) == 0

@pytest.mark.asyncio
async def test_detect_confidence_conflicts_short_returns(arbitration_layer):
    # Coverage for line 198
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="test",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.1)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="test",
        success=True,
        self_assessment=None # No assessment
    )
    conflicts = arbitration_layer._detect_confidence_conflicts([resp1, resp2])
    assert len(conflicts) == 0

@pytest.mark.asyncio
async def test_detect_quality_conflicts_short_returns(arbitration_layer):
    # Coverage for line 230
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="test",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.1)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="test",
        success=True,
        self_assessment=None
    )
    conflicts = arbitration_layer._detect_quality_conflicts([resp1, resp2])
    assert len(conflicts) == 0

def test_calculate_quality_score_no_assessment(arbitration_layer):
    # Coverage for line 279
    resp = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="test",
        success=True,
        self_assessment=None
    )
    score = arbitration_layer._calculate_quality_score(resp)
    assert score == 0.0

@pytest.mark.asyncio
async def test_arbitrate_content_length_contradiction(arbitration_layer):
    # Coverage for line 158
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="Short content",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.5)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="Very long content " * 100, # Much longer
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.8, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.6)
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "content_contradiction" for c in conflicts)

@pytest.mark.asyncio
async def test_arbitrate_confidence_disparity(arbitration_layer):
    # Coverage for line 204
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="Content",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.95, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.5)
    )
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="Content",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.5, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.6)
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "confidence_conflict" for c in conflicts)

@pytest.mark.asyncio
async def test_resolve_unknown_conflict_type(arbitration_layer):
    # Coverage for line 127
    conflict = Conflict(
        response_ids=["id1", "id2"],
        conflict_type="unknown_type",
        description="Testing unknown type"
    )
    resolution = await arbitration_layer.resolve_contradiction(conflict)
    assert resolution.chosen_response_id == "id1"
    assert "Unknown conflict type" in resolution.reasoning

@pytest.mark.asyncio
async def test_build_validated_responses_with_no_conflicts(arbitration_layer):
    # Coverage for line 325
    resp = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="Validated",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.1)
    )
    validated = arbitration_layer._build_validated_responses([resp], [], [])
    assert len(validated) == 1

@pytest.mark.asyncio
async def test_arbitrate_quality_disparity(arbitration_layer):
    # Coverage for quality disparity
    resp1 = AgentResponse(
        subtask_id="task1",
        model_used="model_a",
        content="Good content",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.9, risk_level=RiskLevel.LOW, assumptions=[], execution_time=0.5)
    )
    # Poor quality due to high risk and low confidence
    resp2 = AgentResponse(
        subtask_id="task1",
        model_used="model_b",
        content="Bad",
        success=True,
        self_assessment=SelfAssessment(confidence_score=0.4, risk_level=RiskLevel.CRITICAL, assumptions=["a"]*10, execution_time=0.6)
    )
    
    conflicts = await arbitration_layer.detect_conflicts([resp1, resp2])
    assert any(c.conflict_type == "quality_conflict" for c in conflicts)
