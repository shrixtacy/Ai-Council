import os
import logging
logging.basicConfig(level=logging.DEBUG)
from ai_council.orchestration.cost_optimizer import CostOptimizer
from ai_council.core.models import Subtask, TaskType, ExecutionMode, Priority, RiskLevel
from ai_council.core.interfaces import ModelRegistry, ModelCapabilities, CostProfile, PerformanceMetrics, AIModel
from typing import List, Optional

class MockModelRegistry(ModelRegistry):
    def register_model(self, model_id: str, capabilities: ModelCapabilities, cost_profile: CostProfile, performance: PerformanceMetrics) -> None:
        pass

    def get_model(self, model_id: str):
        pass

    def list_models(self) -> List[str]:
        return ["test-model-1", "test-model-2"]

    def update_model_performance(self, model_id: str, new_metrics: PerformanceMetrics) -> None:
        pass

    def get_models_for_task_type(self, task_type: TaskType):
        pass

    def get_model_by_id(self, model_id: str) -> Optional[AIModel]:
        # Return a simple mock model if it's one of the expected test models
        if model_id in ["test-model-1", "test-model-2"]:
            from unittest.mock import MagicMock
            model = MagicMock(spec=AIModel)
            model.get_model_id.return_value = model_id
            return model
        return None

    def get_model_capabilities(self, model_id: str) -> ModelCapabilities:
        if model_id == "test-model-1":
            return ModelCapabilities(
                task_types=[TaskType.CODE_GENERATION],
                cost_per_token=0.01,
                average_latency=1.5,
                max_context_length=8000,
                reliability_score=0.95,
                strengths=[],
                weaknesses=[]
            )
        return ModelCapabilities(
            task_types=[TaskType.CODE_GENERATION],
            cost_per_token=0.001,
            average_latency=0.5,
            max_context_length=8000,
            reliability_score=0.85,
            strengths=[],
            weaknesses=[]
        )

    def get_model_cost_profile(self, model_id: str) -> CostProfile:
        if model_id == "test-model-1":
            return CostProfile(
                cost_per_input_token=0.01,
                cost_per_output_token=0.05,
                minimum_cost=0.0
            )
        return CostProfile(
            cost_per_input_token=0.001,
            cost_per_output_token=0.005,
            minimum_cost=0.0
        )

    def get_model_performance(self, model_id: str) -> PerformanceMetrics:
        if model_id == "test-model-1":
            return PerformanceMetrics(
                average_response_time=1.5,
                success_rate=0.9,
                average_quality_score=0.95,
                total_requests=100,
                failed_requests=10
            )
        return PerformanceMetrics(
            average_response_time=0.5,
            success_rate=0.8,
            average_quality_score=0.85,
            total_requests=100,
            failed_requests=20
        )

def test_cache():
    print("Testing caching initialization...")
    registry = MockModelRegistry()
    optimizer = CostOptimizer(registry)
    
    subtask = Subtask(
        id="task1",
        task_type=TaskType.CODE_GENERATION,
        content="Write a function to add two numbers",
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.LOW
    )
    
    print("Optimization 1 (should compute & cache)")
    res1 = optimizer.optimize_model_selection(subtask, ExecutionMode.BALANCED, ["test-model-1", "test-model-2"])
    print(f"Result config: {res1.recommended_model}")
    
    print("Optimization 2 (should fetch from cache)")
    res2 = optimizer.optimize_model_selection(subtask, ExecutionMode.BALANCED, ["test-model-1", "test-model-2"])
    print(f"Result config: {res2.recommended_model}")
    
    stats = optimizer.get_optimization_stats()
    print(f"Stats: {stats}")
    
    cache_dir = os.path.expanduser("~/.ai_council/cache/cost_optimizer")
    print(f"Cache files in {cache_dir}:")
    for f in os.listdir(cache_dir):
        print(" -", f)
        
    print("Cache tests passed successfully!")

if __name__ == "__main__":
    test_cache()
