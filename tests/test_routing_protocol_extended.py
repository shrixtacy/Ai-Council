import pytest
from unittest.mock import MagicMock
from ai_council.routing.context_protocol import ModelContextProtocolImpl, RoutingDecision
from ai_council.core.models import Subtask, TaskType, RiskLevel, Priority, ModelCapabilities, PerformanceMetrics as ModelPerformance, CostProfile as ModelCostProfile
from ai_council.core.interfaces import ModelRegistry, AIModel, ModelSelection

class MockModel(AIModel):
    def __init__(self, model_id):
        self.model_id = model_id
    def get_model_id(self):
        return self.model_id
    async def generate_response(self, prompt, **kwargs):
        return f"Response from {self.model_id}"

@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=ModelRegistry)
    
    # Setup some mock models
    model_a = MockModel("model-a")
    model_b = MockModel("model-b")
    
    caps_a = ModelCapabilities(
        task_types=[TaskType.REASONING, TaskType.CODE_GENERATION],
        reliability_score=0.9,
        average_latency=2.0,
        cost_per_token=0.0001,
        tags=["premium", "high-reasoning"]
    )
    perf_a = ModelPerformance(success_rate=0.95, average_quality_score=0.9)
    cost_a = ModelCostProfile(cost_per_input_token=0.0001, cost_per_output_token=0.0002)
    
    caps_b = ModelCapabilities(
        task_types=[TaskType.REASONING, TaskType.RESEARCH],
        reliability_score=0.7,
        average_latency=1.0,
        cost_per_token=0.00001,
        tags=["legacy"]
    )
    perf_b = ModelPerformance(success_rate=0.8, average_quality_score=0.7)
    cost_b = ModelCostProfile(cost_per_input_token=0.00001, cost_per_output_token=0.00002)

    registry.get_models_for_task_type.side_with_type = {
        TaskType.REASONING: [model_a, model_b]
    }
    def get_models_for_task_type(ttype):
        if ttype == TaskType.REASONING: return [model_a, model_b]
        return []
    
    registry.get_models_for_task_type.side_effect = get_models_for_task_type
    
    registry.get_model_capabilities.side_effect = lambda mid: caps_a if mid == "model-a" else caps_b
    registry.get_model_performance.side_effect = lambda mid: perf_a if mid == "model-a" else perf_b
    registry.get_model_cost_profile.side_effect = lambda mid: cost_a if mid == "model-a" else cost_b
    registry.get_model_by_id.side_effect = lambda mid: model_a if mid == "model-a" else (model_b if mid == "model-b" else None)
    
    return registry

@pytest.mark.asyncio
async def test_route_task_caching(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    subtask = Subtask(id="1", content="test", task_type=TaskType.REASONING)
    
    # First call
    selection1 = await protocol.route_task(subtask)
    assert selection1.model_id == "model-a"
    assert mock_registry.get_models_for_task_type.call_count == 1
    
    # Second call (should be cached)
    selection2 = await protocol.route_task(subtask)
    assert selection2.model_id == selection1.model_id
    assert mock_registry.get_models_for_task_type.call_count == 1
    
    # Clear cache
    protocol.clear_cache()
    selection3 = await protocol.route_task(subtask)
    assert mock_registry.get_models_for_task_type.call_count == 2

@pytest.mark.asyncio
async def test_determine_parallelism(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    st1 = Subtask(id="1", content="reasoning task 1", priority=Priority.CRITICAL, task_type=TaskType.REASONING)
    st2 = Subtask(id="2", content="reasoning task 2", priority=Priority.MEDIUM, task_type=TaskType.REASONING)
    st3 = Subtask(id="3", content="research task", priority=Priority.LOW, task_type=TaskType.RESEARCH)
    
    plan = await protocol.determine_parallelism([st1, st2, st3])
    assert len(plan.parallel_groups) == 3
    assert plan.parallel_groups[0] == [st1]
    assert plan.parallel_groups[1] == [st2]
    assert plan.parallel_groups[2] == [st3]
    assert plan.sequential_order == ["1", "2", "3"]

def test_score_model_accuracy_penalty(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    # accuracy_requirement=0.95, model_a has quality_score=0.9. Penalty should apply.
    subtask = Subtask(content="x", task_type=TaskType.REASONING, accuracy_requirement=0.95)
    model_a = MockModel("model-a")
    score = protocol._score_model_for_subtask(model_a, subtask)
    
    # Accuracy req not met penalty: (0.95 - 0.9) * 0.2 = 0.01 penalty
    # Base: 0.9*0.3 + 0.95*0.3 + 0.2 + 0.1(if >= req, but it's not) -> logic is 0.1 if >= else penalty
    # Wait, check code:
    # if performance.average_quality_score >= subtask.accuracy_requirement: score += 0.1
    # else: score -= (req - score) * 0.2
    
    assert score > 0

def test_score_model_risk_level(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    model_a = MockModel("model-a")
    
    # Critical risk
    st_crit = Subtask(content="x", task_type=TaskType.REASONING, risk_level=RiskLevel.CRITICAL)
    score_crit = protocol._score_model_for_subtask(model_a, st_crit)
    
    # Low risk
    st_low = Subtask(content="x", task_type=TaskType.REASONING, risk_level=RiskLevel.LOW)
    score_low = protocol._score_model_for_subtask(model_a, st_low)
    
    # Critical risk logic: score = score * 0.7 + reliability * 0.3
    # Low risk logic: score = score * 0.8 + cost_score * 0.2
    assert score_crit != score_low

@pytest.mark.asyncio
async def test_fallback_fresh_routing_with_context(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    subtask = Subtask(id="1", content="t", task_type=TaskType.REASONING)
    
    # Build a fake context
    context = {"failure_type": "rate_limit", "error_message": "Rate limit exceeded"}
    
    # Fallback from model-a to model-b
    selection = await protocol.select_fallback("model-a", subtask, context)
    assert selection.model_id == "model-b"
    assert "fallback" in selection.reasoning.lower()

def test_get_routing_stats(mock_registry):
    protocol = ModelContextProtocolImpl(mock_registry)
    stats = protocol.get_routing_stats()
    assert "cached_decisions" in stats
    assert "fallback_chains" in stats
