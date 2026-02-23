"""Model context protocol implementation for intelligent task routing."""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from ..core.interfaces import ModelContextProtocol, ModelSelection, ExecutionPlan, ModelRegistry
from ..core.models import (
    Subtask, TaskType, ExecutionMode, RiskLevel, Priority
)


@dataclass
class RoutingDecision:
    """Represents a routing decision with reasoning."""
    model_id: str
    confidence: float
    reasoning: str
    cost_estimate: float
    time_estimate: float


class ModelContextProtocolImpl(ModelContextProtocol):
    """Implementation of ModelContextProtocol for intelligent task routing."""
    
    def __init__(self, model_registry: ModelRegistry):
        """Initialize the model context protocol.
        
        Args:
            model_registry: The model registry to use for model selection
        """
        self.model_registry = model_registry
        self._routing_cache: Dict[str, RoutingDecision] = {}
        self._fallback_chains: Dict[str, List[str]] = {}
    
    async def route_task(self, subtask: Subtask) -> ModelSelection:
        """Route a subtask to the most appropriate model.
        
        Args:
            subtask: The subtask to route
            
        Returns:
            ModelSelection: The selected model and routing decision
        """
        # Create cache key based on subtask characteristics
        cache_key = self._create_cache_key(subtask)
        
        # Check cache first
        if cache_key in self._routing_cache:
            cached_decision = self._routing_cache[cache_key]
            return ModelSelection(
                model_id=cached_decision.model_id,
                confidence=cached_decision.confidence,
                reasoning=cached_decision.reasoning
            )
        
        # Get candidate models for the task type
        if not subtask.task_type:
            raise ValueError("Subtask must have a task type for routing")
        
        candidate_models = self.model_registry.get_models_for_task_type(subtask.task_type)
        
        if not candidate_models:
            raise ValueError(f"No models available for task type {subtask.task_type}")
        
        # Score and rank models based on subtask requirements
        scored_models = []
        for model in candidate_models:
            score = self._score_model_for_subtask(model, subtask)
            scored_models.append((model, score))
        
        # Sort by score (descending)
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        # Select the best model
        best_model, best_score = scored_models[0]
        model_id = best_model.get_model_id()
        
        # Generate reasoning
        reasoning = self._generate_routing_reasoning(best_model, subtask, best_score)
        
        # Create routing decision
        decision = RoutingDecision(
            model_id=model_id,
            confidence=min(best_score, 1.0),
            reasoning=reasoning,
            cost_estimate=self._estimate_cost(best_model, subtask),
            time_estimate=self._estimate_time(best_model, subtask)
        )
        
        # Cache the decision
        self._routing_cache[cache_key] = decision
        
        # Build fallback chain
        self._build_fallback_chain(model_id, [m[0] for m in scored_models[1:3]])
        
        return ModelSelection(
            model_id=decision.model_id,
            confidence=decision.confidence,
            reasoning=decision.reasoning
        )
    
    async def select_fallback(self, failed_model: str, subtask: Subtask) -> ModelSelection:
        """Select a fallback model when the primary model fails.
        
        Args:
            failed_model: ID of the model that failed
            subtask: The subtask that needs a fallback model
            
        Returns:
            ModelSelection: The fallback model selection
        """
        # Check if we have a pre-built fallback chain
        if failed_model in self._fallback_chains:
            fallback_candidates = self._fallback_chains[failed_model]
            
            # Try each fallback in order
            for fallback_id in fallback_candidates:
                fallback_model = self.model_registry.get_model_by_id(fallback_id)
                if fallback_model:
                    return ModelSelection(
                        model_id=fallback_id,
                        confidence=0.7,  # Lower confidence for fallback
                        reasoning=f"Fallback selection after {failed_model} failed"
                    )
        
        # If no pre-built chain, do fresh routing excluding the failed model
        if not subtask.task_type:
            raise ValueError("Subtask must have a task type for fallback routing")
        
        candidate_models = self.model_registry.get_models_for_task_type(subtask.task_type)
        
        # Filter out the failed model
        available_models = [m for m in candidate_models if m.get_model_id() != failed_model]
        
        if not available_models:
            raise ValueError(f"No fallback models available for task type {subtask.task_type}")
        
        # Score remaining models
        scored_models = []
        for model in available_models:
            score = self._score_model_for_subtask(model, subtask)
            scored_models.append((model, score))
        
        # Sort by score and select best
        scored_models.sort(key=lambda x: x[1], reverse=True)
        best_model, best_score = scored_models[0]
        
        return ModelSelection(
            model_id=best_model.get_model_id(),
            confidence=min(best_score * 0.8, 1.0),  # Reduced confidence for fallback
            reasoning=f"Fallback selection after {failed_model} failed, chose based on score {best_score:.2f}"
        )
    
    async def determine_parallelism(self, subtasks: List[Subtask]) -> ExecutionPlan:
        """Determine which subtasks can be executed in parallel.
        
        Args:
            subtasks: List of subtasks to analyze for parallelism
            
        Returns:
            ExecutionPlan: Plan for parallel and sequential execution
        """
        if not subtasks:
            return ExecutionPlan(parallel_groups=[], sequential_order=[])
        
        # Group subtasks by dependencies and priority
        high_priority = [st for st in subtasks if st.priority == Priority.CRITICAL]
        medium_priority = [st for st in subtasks if st.priority in [Priority.HIGH, Priority.MEDIUM]]
        low_priority = [st for st in subtasks if st.priority == Priority.LOW]
        
        parallel_groups = []
        sequential_order = []
        
        # Critical tasks run first, potentially in parallel if independent
        if high_priority:
            parallel_groups.append(high_priority)
            sequential_order.extend([st.id for st in high_priority])
        
        # Medium priority tasks can run in parallel after critical tasks
        if medium_priority:
            # Group by task type for better parallelism
            task_type_groups = self._group_by_task_type(medium_priority)
            for group in task_type_groups:
                parallel_groups.append(group)
                sequential_order.extend([st.id for st in group])
        
        # Low priority tasks run last
        if low_priority:
            # Can run all low priority tasks in parallel
            parallel_groups.append(low_priority)
            sequential_order.extend([st.id for st in low_priority])
        
        return ExecutionPlan(
            parallel_groups=parallel_groups,
            sequential_order=sequential_order
        )
    
    def _create_cache_key(self, subtask: Subtask) -> str:
        """Create a cache key for routing decisions."""
        return f"{subtask.task_type}_{subtask.priority}_{subtask.risk_level}_{subtask.accuracy_requirement}"
    
    def _score_model_for_subtask(self, model, subtask: Subtask) -> float:
        """Score a model's suitability for a subtask.
        
        Args:
            model: The AI model to score
            subtask: The subtask to score against
            
        Returns:
            float: Score between 0.0 and 1.0
        """
        try:
            capabilities = self.model_registry.get_model_capabilities(model.get_model_id())
            performance = self.model_registry.get_model_performance(model.get_model_id())
        except KeyError:
            return 0.0
        
        score = 0.0
        
        # Base score from reliability
        score += capabilities.reliability_score * 0.3
        
        # Performance score
        score += performance.success_rate * 0.3
        
        # Task type match score
        if subtask.task_type in capabilities.task_types:
            score += 0.2
        
        # Accuracy requirement match
        if performance.average_quality_score >= subtask.accuracy_requirement:
            score += 0.1
        else:
            # Penalize if model doesn't meet accuracy requirement
            score -= (subtask.accuracy_requirement - performance.average_quality_score) * 0.2
        
        # Risk level consideration
        if subtask.risk_level == RiskLevel.CRITICAL:
            # For critical tasks, heavily weight reliability
            score = score * 0.7 + capabilities.reliability_score * 0.3
        elif subtask.risk_level == RiskLevel.LOW:
            # For low risk tasks, consider cost more heavily
            cost_score = max(0, 1.0 - capabilities.cost_per_token * 1000)  # Normalize cost
            score = score * 0.8 + cost_score * 0.2
        
        # Priority consideration
        if subtask.priority == Priority.CRITICAL:
            # For critical priority, prefer faster models
            latency_score = max(0, 1.0 - capabilities.average_latency / 10.0)  # Normalize latency
            score = score * 0.8 + latency_score * 0.2
        
        return max(0.0, min(1.0, score))
    
    def _generate_routing_reasoning(self, model, subtask: Subtask, score: float) -> str:
        """Generate human-readable reasoning for routing decision."""
        model_id = model.get_model_id()
        
        try:
            capabilities = self.model_registry.get_model_capabilities(model_id)
            performance = self.model_registry.get_model_performance(model_id)
        except KeyError:
            return f"Selected {model_id} (score: {score:.2f})"
        
        reasons = []
        
        if capabilities.reliability_score > 0.8:
            reasons.append("high reliability")
        
        if performance.success_rate > 0.9:
            reasons.append("excellent success rate")
        
        if subtask.task_type in capabilities.task_types:
            reasons.append(f"specialized for {subtask.task_type.value}")
        
        if capabilities.cost_per_token < 0.001:
            reasons.append("cost-effective")
        
        if capabilities.average_latency < 2.0:
            reasons.append("fast response time")
        
        reason_text = ", ".join(reasons) if reasons else "best available option"
        
        return f"Selected {model_id} (score: {score:.2f}) due to {reason_text}"
    
    def _estimate_cost(self, model, subtask: Subtask) -> float:
        """Estimate cost for executing subtask with model."""
        try:
            cost_profile = self.model_registry.get_model_cost_profile(model.get_model_id())
            # Simple estimation based on content length
            estimated_tokens = len(subtask.content.split()) * 1.3  # Rough token estimation
            return estimated_tokens * cost_profile.cost_per_input_token
        except KeyError:
            return 0.01  # Default estimate
    
    def _estimate_time(self, model, subtask: Subtask) -> float:
        """Estimate execution time for subtask with model."""
        try:
            capabilities = self.model_registry.get_model_capabilities(model.get_model_id())
            return capabilities.average_latency
        except KeyError:
            return 5.0  # Default estimate in seconds
    
    def _build_fallback_chain(self, primary_model_id: str, fallback_models: List) -> None:
        """Build a fallback chain for a primary model."""
        fallback_ids = [m.get_model_id() for m in fallback_models]
        self._fallback_chains[primary_model_id] = fallback_ids
    
    def _group_by_task_type(self, subtasks: List[Subtask]) -> List[List[Subtask]]:
        """Group subtasks by task type for parallel execution."""
        task_type_groups: Dict[TaskType, List[Subtask]] = {}
        
        for subtask in subtasks:
            if subtask.task_type:
                if subtask.task_type not in task_type_groups:
                    task_type_groups[subtask.task_type] = []
                task_type_groups[subtask.task_type].append(subtask)
        
        return list(task_type_groups.values())
    
    def clear_cache(self) -> None:
        """Clear the routing cache."""
        self._routing_cache.clear()
    
    def get_routing_stats(self) -> Dict[str, int]:
        """Get routing statistics."""
        return {
            "cached_decisions": len(self._routing_cache),
            "fallback_chains": len(self._fallback_chains)
        }