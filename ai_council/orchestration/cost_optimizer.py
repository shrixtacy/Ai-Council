"""Cost optimization logic for AI Council execution modes and model selection."""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from ..core.interfaces import ModelRegistry, ModelSelection
from ..core.models import (
    Subtask, ExecutionMode, TaskType, RiskLevel, Priority,
    ModelCapabilities, CostProfile, PerformanceMetrics
)
from ..core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class CostOptimizationResult:
    """Result of cost optimization analysis."""
    recommended_model: str
    estimated_cost: float
    estimated_time: float
    quality_score: float
    reasoning: str
    confidence: float


class OptimizationStrategy(Enum):
    """Different optimization strategies based on execution mode."""
    MINIMIZE_COST = "minimize_cost"
    MINIMIZE_TIME = "minimize_time"
    MAXIMIZE_QUALITY = "maximize_quality"
    BALANCED = "balanced"


class CostOptimizer:
    """
    Cost optimization engine that makes intelligent model selection decisions
    based on execution mode, task requirements, and performance vs cost trade-offs.
    
    This component implements:
    - Execution mode-based routing decisions
    - Cost-aware model selection
    - Performance vs cost trade-off analysis
    - Dynamic pricing and quality optimization
    """
    
    def __init__(self, model_registry: ModelRegistry):
        """
        Initialize the cost optimizer.
        
        Args:
            model_registry: Registry of available models with capabilities and costs
        """
        self.model_registry = model_registry
        self._optimization_cache: Dict[str, CostOptimizationResult] = {}
        self._performance_history: Dict[str, List[float]] = {}
        
        # Optimization weights for different execution modes
        self._mode_weights = self._build_mode_weights()
        
        logger.info("CostOptimizer initialized")
    
    def optimize_model_selection(
        self, 
        subtask: Subtask, 
        execution_mode: ExecutionMode,
        available_models: List[str]
    ) -> CostOptimizationResult:
        """
        Optimize model selection based on execution mode and task requirements.
        
        Args:
            subtask: The subtask requiring model selection
            execution_mode: Current execution mode (fast, balanced, best_quality)
            available_models: List of available model IDs
            
        Returns:
            CostOptimizationResult: Optimized model selection with reasoning
        """
        # Create cache key
        cache_key = self._create_cache_key(subtask, execution_mode, available_models)
        
        # Check cache first
        if cache_key in self._optimization_cache:
            logger.debug("Using cached optimization result", extra={"cache_key": cache_key})
            return self._optimization_cache[cache_key]
        
        # Get optimization strategy based on execution mode
        strategy = self._get_optimization_strategy(execution_mode)
        
        # Score all available models
        model_scores = []
        for model_id in available_models:
            try:
                score_result = self._score_model_for_optimization(
                    model_id, subtask, strategy
                )
                model_scores.append((model_id, score_result))
            except Exception as e:
                logger.warning("Failed to score model", extra={"model_id": model_id, "error": str(e)})
                continue
        
        if not model_scores:
            raise ValueError("No models could be scored for optimization")
        
        # Select best model based on strategy
        best_model_id, best_score = self._select_optimal_model(
            model_scores, strategy, subtask
        )
        
        # Create optimization result
        result = CostOptimizationResult(
            recommended_model=best_model_id,
            estimated_cost=best_score['cost'],
            estimated_time=best_score['time'],
            quality_score=best_score['quality'],
            reasoning=self._generate_optimization_reasoning(
                best_model_id, best_score, strategy
            ),
            confidence=best_score['confidence']
        )
        
        # Cache the result
        self._optimization_cache[cache_key] = result
        
        logger.info("Optimized model selection", extra={"model_id": best_model_id, "strategy": strategy.value})
        return result
    
    def estimate_execution_cost(
        self, 
        subtasks: List[Subtask], 
        execution_mode: ExecutionMode
    ) -> Dict[str, float]:
        """
        Estimate total execution cost for a list of subtasks.
        
        Args:
            subtasks: List of subtasks to estimate
            execution_mode: Execution mode affecting cost calculations
            
        Returns:
            Dict[str, float]: Cost breakdown by category
        """
        total_cost = 0.0
        model_costs = {}
        time_costs = {}
        
        for subtask in subtasks:
            try:
                # Get available models for this task type
                available_models = [
                    m.get_model_id() 
                    for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                ]
                
                if not available_models:
                    continue
                
                # Optimize model selection
                optimization = self.optimize_model_selection(
                    subtask, execution_mode, available_models
                )
                
                # Accumulate costs
                total_cost += optimization.estimated_cost
                
                model_id = optimization.recommended_model
                if model_id in model_costs:
                    model_costs[model_id] += optimization.estimated_cost
                else:
                    model_costs[model_id] = optimization.estimated_cost
                
                # Estimate time-based costs (if applicable)
                time_cost = optimization.estimated_time * 0.001  # $0.001 per second
                if model_id in time_costs:
                    time_costs[model_id] += time_cost
                else:
                    time_costs[model_id] = time_cost
                
            except Exception as e:
                logger.warning("Failed to estimate cost for subtask", extra={"subtask_id": subtask.id, "error": str(e)})
                # Add default cost estimate
                total_cost += 0.01
        
        return {
            'total_cost': total_cost,
            'model_costs': model_costs,
            'time_costs': time_costs,
            'estimated_savings': self._calculate_savings(execution_mode, total_cost)
        }
    
    def analyze_cost_vs_quality_tradeoff(
        self, 
        subtask: Subtask, 
        model_options: List[str]
    ) -> List[Dict[str, float]]:
        """
        Analyze cost vs quality trade-offs for different model options.
        
        Args:
            subtask: The subtask to analyze
            model_options: List of model IDs to compare
            
        Returns:
            List[Dict[str, float]]: Trade-off analysis for each model
        """
        tradeoff_analysis = []
        
        for model_id in model_options:
            try:
                capabilities = self.model_registry.get_model_capabilities(model_id)
                cost_profile = self.model_registry.get_model_cost_profile(model_id)
                performance = self.model_registry.get_model_performance(model_id)
                
                # Calculate metrics
                estimated_cost = self._calculate_model_cost(subtask, cost_profile)
                quality_score = performance.average_quality_score
                efficiency_ratio = quality_score / max(estimated_cost, 0.001)  # Quality per dollar
                
                tradeoff_analysis.append({
                    'model_id': model_id,
                    'estimated_cost': estimated_cost,
                    'quality_score': quality_score,
                    'efficiency_ratio': efficiency_ratio,
                    'reliability_score': capabilities.reliability_score,
                    'average_latency': capabilities.average_latency
                })
                
            except Exception as e:
                logger.warning("Failed to analyze model", extra={"model_id": model_id, "error": str(e)})
                continue
        
        # Sort by efficiency ratio (descending)
        tradeoff_analysis.sort(key=lambda x: x['efficiency_ratio'], reverse=True)
        
        return tradeoff_analysis
    
    def update_performance_history(self, model_id: str, actual_cost: float, quality_score: float):
        """
        Update performance history for model cost optimization.
        
        Args:
            model_id: The model that was used
            actual_cost: Actual cost incurred
            quality_score: Achieved quality score
        """
        efficiency = quality_score / max(actual_cost, 0.001)
        
        if model_id not in self._performance_history:
            self._performance_history[model_id] = []
        
        self._performance_history[model_id].append(efficiency)
        
        # Keep only recent history (last 100 entries)
        if len(self._performance_history[model_id]) > 100:
            self._performance_history[model_id] = self._performance_history[model_id][-100:]
        
        logger.debug("Updated performance history", extra={"model_id": model_id, "efficiency": efficiency})
    
    def _get_optimization_strategy(self, execution_mode: ExecutionMode) -> OptimizationStrategy:
        """Get optimization strategy based on execution mode."""
        strategy_map = {
            ExecutionMode.FAST: OptimizationStrategy.MINIMIZE_TIME,
            ExecutionMode.BALANCED: OptimizationStrategy.BALANCED,
            ExecutionMode.BEST_QUALITY: OptimizationStrategy.MAXIMIZE_QUALITY
        }
        return strategy_map.get(execution_mode, OptimizationStrategy.BALANCED)
    
    def _score_model_for_optimization(
        self, 
        model_id: str, 
        subtask: Subtask, 
        strategy: OptimizationStrategy
    ) -> Dict[str, float]:
        """Score a model for optimization based on strategy."""
        try:
            capabilities = self.model_registry.get_model_capabilities(model_id)
            cost_profile = self.model_registry.get_model_cost_profile(model_id)
            performance = self.model_registry.get_model_performance(model_id)
        except KeyError as e:
            raise ValueError(f"Model data not found for {model_id}: {str(e)}")
        
        # Calculate base metrics
        estimated_cost = self._calculate_model_cost(subtask, cost_profile)
        estimated_time = capabilities.average_latency
        quality_score = performance.average_quality_score
        reliability_score = capabilities.reliability_score
        
        # Apply strategy-specific scoring
        weights = self._mode_weights[strategy]
        
        # Normalize scores (0-1 range)
        cost_score = max(0, 1.0 - (estimated_cost / 0.10))  # Normalize against $0.10
        time_score = max(0, 1.0 - (estimated_time / 30.0))  # Normalize against 30 seconds
        
        # Calculate composite score
        composite_score = (
            cost_score * weights['cost_weight'] +
            time_score * weights['time_weight'] +
            quality_score * weights['quality_weight'] +
            reliability_score * weights['reliability_weight']
        )
        
        # Apply task-specific adjustments
        composite_score = self._apply_task_adjustments(
            composite_score, subtask, capabilities
        )
        
        # Include performance history if available
        if model_id in self._performance_history:
            history = self._performance_history[model_id]
            avg_efficiency = sum(history) / len(history)
            composite_score *= (1.0 + min(avg_efficiency * 0.1, 0.2))  # Up to 20% bonus
        
        return {
            'composite_score': composite_score,
            'cost': estimated_cost,
            'time': estimated_time,
            'quality': quality_score,
            'reliability': reliability_score,
            'confidence': min(composite_score, 1.0)
        }
    
    def _select_optimal_model(
        self, 
        model_scores: List[Tuple[str, Dict[str, float]]], 
        strategy: OptimizationStrategy,
        subtask: Subtask
    ) -> Tuple[str, Dict[str, float]]:
        """Select the optimal model based on scores and strategy."""
        if not model_scores:
            raise ValueError("No model scores provided")
        
        # Sort by composite score (descending)
        sorted_scores = sorted(
            model_scores, 
            key=lambda x: x[1]['composite_score'], 
            reverse=True
        )
        
        # Apply strategy-specific selection logic
        if strategy == OptimizationStrategy.MINIMIZE_COST:
            # Among top 3 models, choose the cheapest
            top_models = sorted_scores[:3]
            return min(top_models, key=lambda x: x[1]['cost'])
        
        elif strategy == OptimizationStrategy.MINIMIZE_TIME:
            # Among top 3 models, choose the fastest
            top_models = sorted_scores[:3]
            return min(top_models, key=lambda x: x[1]['time'])
        
        elif strategy == OptimizationStrategy.MAXIMIZE_QUALITY:
            # Among top 3 models, choose the highest quality
            top_models = sorted_scores[:3]
            return max(top_models, key=lambda x: x[1]['quality'])
        
        else:  # BALANCED
            # Choose the model with highest composite score
            return sorted_scores[0]
    
    def _calculate_model_cost(self, subtask: Subtask, cost_profile: CostProfile) -> float:
        """Calculate estimated cost for a subtask with a specific model."""
        # Estimate tokens based on content length and task type
        content_length = len(subtask.content)
        
        # Base token estimation
        estimated_input_tokens = content_length * 0.75  # ~0.75 tokens per character
        
        # Adjust based on task type
        task_multipliers = {
            TaskType.CODE_GENERATION: 1.5,
            TaskType.CREATIVE_OUTPUT: 1.3,
            TaskType.RESEARCH: 1.2,
            TaskType.REASONING: 1.1,
            TaskType.FACT_CHECKING: 1.0,
            TaskType.VERIFICATION: 0.9,
            TaskType.DEBUGGING: 1.4
        }
        
        multiplier = task_multipliers.get(subtask.task_type, 1.0)
        estimated_input_tokens *= multiplier
        
        # Estimate output tokens (typically 30-70% of input)
        estimated_output_tokens = estimated_input_tokens * 0.5
        
        # Calculate total cost
        total_cost = (
            estimated_input_tokens * cost_profile.cost_per_input_token +
            estimated_output_tokens * cost_profile.cost_per_output_token
        )
        
        return max(total_cost, cost_profile.minimum_cost)
    
    def _apply_task_adjustments(
        self, 
        base_score: float, 
        subtask: Subtask, 
        capabilities: ModelCapabilities
    ) -> float:
        """Apply task-specific adjustments to the base score."""
        adjusted_score = base_score
        
        # Task type compatibility bonus
        if subtask.task_type in capabilities.task_types:
            adjusted_score *= 1.1  # 10% bonus for task type match
        
        # Risk level adjustments
        if subtask.risk_level == RiskLevel.CRITICAL:
            # For critical tasks, heavily weight reliability
            adjusted_score = adjusted_score * 0.7 + capabilities.reliability_score * 0.3
        elif subtask.risk_level == RiskLevel.LOW:
            # For low risk tasks, weight cost more heavily
            adjusted_score *= 1.05  # Small bonus for cost efficiency
        
        # Priority adjustments
        if subtask.priority == Priority.CRITICAL:
            # For critical priority, prefer faster models
            if capabilities.average_latency < 2.0:
                adjusted_score *= 1.1
        
        # Accuracy requirement adjustments
        if subtask.accuracy_requirement > 0.9:
            # High accuracy requirement - weight quality more
            quality_bonus = min(0.2, (subtask.accuracy_requirement - 0.9) * 2)
            adjusted_score *= (1.0 + quality_bonus)
        
        return adjusted_score
    
    def _generate_optimization_reasoning(
        self, 
        model_id: str, 
        score_data: Dict[str, float], 
        strategy: OptimizationStrategy
    ) -> str:
        """Generate human-readable reasoning for the optimization decision."""
        reasons = []
        
        if strategy == OptimizationStrategy.MINIMIZE_COST:
            reasons.append(f"optimized for cost (${score_data['cost']:.4f})")
        elif strategy == OptimizationStrategy.MINIMIZE_TIME:
            reasons.append(f"optimized for speed ({score_data['time']:.1f}s)")
        elif strategy == OptimizationStrategy.MAXIMIZE_QUALITY:
            reasons.append(f"optimized for quality ({score_data['quality']:.2f})")
        else:
            reasons.append("balanced optimization")
        
        if score_data['reliability'] > 0.9:
            reasons.append("high reliability")
        
        if score_data['composite_score'] > 0.8:
            reasons.append("excellent overall score")
        
        reason_text = ", ".join(reasons)
        return f"Selected {model_id} for {reason_text} (score: {score_data['composite_score']:.2f})"
    
    def _calculate_savings(self, execution_mode: ExecutionMode, total_cost: float) -> float:
        """Calculate estimated savings compared to premium execution."""
        if execution_mode == ExecutionMode.FAST:
            return total_cost * 0.3  # 30% savings in fast mode
        elif execution_mode == ExecutionMode.BALANCED:
            return total_cost * 0.1  # 10% savings in balanced mode
        else:
            return 0.0  # No savings in best quality mode
    
    def _create_cache_key(
        self, 
        subtask: Subtask, 
        execution_mode: ExecutionMode, 
        available_models: List[str]
    ) -> str:
        """Create a cache key for optimization results."""
        models_hash = hash(tuple(sorted(available_models)))
        return f"{subtask.task_type}_{execution_mode.value}_{subtask.priority.value}_{subtask.risk_level.value}_{models_hash}"
    
    def _build_mode_weights(self) -> Dict[OptimizationStrategy, Dict[str, float]]:
        """Build optimization weights for different strategies."""
        return {
            OptimizationStrategy.MINIMIZE_COST: {
                'cost_weight': 0.5,
                'time_weight': 0.2,
                'quality_weight': 0.2,
                'reliability_weight': 0.1
            },
            OptimizationStrategy.MINIMIZE_TIME: {
                'cost_weight': 0.2,
                'time_weight': 0.5,
                'quality_weight': 0.2,
                'reliability_weight': 0.1
            },
            OptimizationStrategy.MAXIMIZE_QUALITY: {
                'cost_weight': 0.1,
                'time_weight': 0.1,
                'quality_weight': 0.5,
                'reliability_weight': 0.3
            },
            OptimizationStrategy.BALANCED: {
                'cost_weight': 0.25,
                'time_weight': 0.25,
                'quality_weight': 0.3,
                'reliability_weight': 0.2
            }
        }
    
    def clear_cache(self):
        """Clear the optimization cache."""
        self._optimization_cache.clear()
        logger.info("Optimization cache cleared")
    
    def get_optimization_stats(self) -> Dict[str, int]:
        """Get optimization statistics."""
        return {
            'cached_optimizations': len(self._optimization_cache),
            'models_with_history': len(self._performance_history),
            'total_history_entries': sum(len(history) for history in self._performance_history.values())
        }