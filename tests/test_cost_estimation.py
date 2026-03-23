import pytest
from unittest.mock import MagicMock
from ai_council.execution.agent import BaseExecutionAgent
from ai_council.core.models import Subtask, CostProfile, TaskType
from ai_council.core.interfaces import ModelRegistry

class TestCostEstimation:
    @pytest.fixture
    def mock_registry(self):
        registry = MagicMock(spec=ModelRegistry)
        return registry

    @pytest.fixture
    def agent(self, mock_registry):
        return BaseExecutionAgent(model_registry=mock_registry)

    @pytest.fixture
    def sample_subtask(self):
        return Subtask(
            parent_task_id="task-123",
            content="Test content",
            task_type=TaskType.REASONING
        )

    def test_estimate_token_usage_split(self, agent, sample_subtask):
        response = "This is a test response."
        agent._build_prompt = MagicMock(return_value="Prompt content")
        
        # Mock _count_tokens to return predictable values
        agent._count_tokens = MagicMock(side_effect=lambda x: 3 if "Prompt" in x else 6)
        
        usage = agent._estimate_token_usage(response, sample_subtask)
        
        assert usage["input"] == 3
        assert usage["output"] == 6
        assert usage["total"] == 9

    def test_estimate_cost_with_registry(self, agent, mock_registry, sample_subtask):
        model_id = "test-model"
        response = "Response"
        agent._build_prompt = MagicMock(return_value="Prompt")
        
        # Mock _count_tokens
        agent._count_tokens = MagicMock(side_effect=lambda x: 1 if "Prompt" in x else 2)
        
        # Mock cost profile: $0.01 per input, $0.02 per output, $0.005 min
        profile = CostProfile(
            cost_per_input_token=0.01,
            cost_per_output_token=0.02,
            minimum_cost=0.005
        )
        mock_registry.get_model_cost_profile.return_value = profile
        
        # Input tokens: 1
        # Output tokens: 2
        cost = agent._estimate_cost(response, sample_subtask, model_id)
        
        # expected_cost = (1 * 0.01) + (2 * 0.02) = 0.01 + 0.04 = 0.05
        assert cost == pytest.approx(0.05)
        mock_registry.get_model_cost_profile.assert_called_with(model_id)

    def test_estimate_cost_minimum(self, agent, mock_registry, sample_subtask):
        model_id = "test-model"
        response = "R"
        agent._build_prompt = MagicMock(return_value="P")
        
        agent._count_tokens = MagicMock(return_value=1)
        
        # High minimum cost
        profile = CostProfile(
            cost_per_input_token=0.000001,
            cost_per_output_token=0.000001,
            minimum_cost=0.10
        )
        mock_registry.get_model_cost_profile.return_value = profile
        
        cost = agent._estimate_cost(response, sample_subtask, model_id)
        
        # calculated cost would be 0.000002, but minimum is 0.10
        assert cost == 0.10

    def test_estimate_cost_fallback(self, agent, mock_registry, sample_subtask):
        # Case where model is not in registry
        model_id = "unknown-model"
        mock_registry.get_model_cost_profile.side_effect = KeyError("Model not found")
        
        agent._count_tokens = MagicMock(side_effect=lambda x: 1 if "Prompt" in x else 2)
        agent._build_prompt = MagicMock(return_value="Prompt")
        response = "Response"
        
        cost = agent._estimate_cost(response, sample_subtask, model_id)
        
        # Fallback uses 0.00002 per token
        # total tokens = 3
        # expected = 3 * 0.00002 = 0.00006
        assert cost == pytest.approx(0.00006)

    @pytest.mark.asyncio
    async def test_generate_self_assessment_calls_accurate_cost(self, agent, mock_registry, sample_subtask):
        model_id = "test-model"
        response = "Test response content"
        agent._build_prompt = MagicMock(return_value="Prompt content")
        
        agent._count_tokens = MagicMock(side_effect=lambda x: 3 if "Prompt" in x else 5)
        
        profile = CostProfile(
            cost_per_input_token=0.1,
            cost_per_output_token=0.2
        )
        mock_registry.get_model_cost_profile.return_value = profile
        
        assessment = await agent.generate_self_assessment(response, sample_subtask, model_id)
        
        # Input: 3 tokens. Output: 5 tokens.
        # Cost: 3*0.1 + 5*0.2 = 0.3 + 1.0 = 1.3
        assert assessment.estimated_cost == pytest.approx(1.3)
        assert assessment.token_usage == 8

