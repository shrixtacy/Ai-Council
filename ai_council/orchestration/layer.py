"""Implementation of the OrchestrationLayer for main request processing pipeline."""

import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime

from ..core.interfaces import (
    OrchestrationLayer, AnalysisEngine, TaskDecomposer, ModelContextProtocol,
    ExecutionAgent, ArbitrationLayer, SynthesisLayer, ModelRegistry,
    CostEstimate, ExecutionFailure, FallbackStrategy
)
from ..core.models import (
    Task, Subtask, AgentResponse, FinalResponse, ExecutionMode, 
    ComplexityLevel, ExecutionMetadata, CostBreakdown
)
from ..core.failure_handling import (
    FailureEvent, FailureType, resilience_manager, create_failure_event,
    CircuitBreakerConfig
)
from ..core.timeout_handler import (
    timeout_handler, adaptive_timeout_manager, with_adaptive_timeout, TimeoutError
)
from ..core.exceptions import (
    AICouncilError, ConfigurationError, ModelTimeoutError, 
    AuthenticationError, RateLimitError, ProviderError, 
    ValidationError, OrchestrationError
)
from .cost_optimizer import CostOptimizer


logger = logging.getLogger(__name__)


class ConcreteOrchestrationLayer(OrchestrationLayer):
    """
    Concrete implementation of OrchestrationLayer that coordinates the entire
    AI Council pipeline from user input to final response.
    
    This implementation manages:
    - Request processing through the complete pipeline
    - Cost estimation and execution mode handling
    - Failure recovery and graceful degradation
    - Resource optimization based on execution modes
    """
    
    def __init__(
        self,
        analysis_engine: AnalysisEngine,
        task_decomposer: TaskDecomposer,
        model_context_protocol: ModelContextProtocol,
        execution_agent: ExecutionAgent,
        arbitration_layer: ArbitrationLayer,
        synthesis_layer: SynthesisLayer,
        model_registry: ModelRegistry,
        max_retries: int = 3,
        timeout_seconds: float = 300.0
    ):
        """
        Initialize the orchestration layer with all required components.
        
        Args:
            analysis_engine: Engine for analyzing user input
            task_decomposer: Component for breaking down complex tasks
            model_context_protocol: Protocol for intelligent model routing
            execution_agent: Agent for executing subtasks
            arbitration_layer: Layer for resolving conflicts
            synthesis_layer: Layer for final response synthesis
            model_registry: Registry of available AI models
            max_retries: Maximum retry attempts for failed operations
            timeout_seconds: Maximum time allowed for request processing
        """
        self.analysis_engine = analysis_engine
        self.task_decomposer = task_decomposer
        self.model_context_protocol = model_context_protocol
        self.execution_agent = execution_agent
        self.arbitration_layer = arbitration_layer
        self.synthesis_layer = synthesis_layer
        self.model_registry = model_registry
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        
        # Initialize cost optimizer
        self.cost_optimizer = CostOptimizer(model_registry)
        
        # Execution mode configurations
        self._execution_configs = self._build_execution_configs()
        
        # Initialize circuit breakers for orchestration components
        self._initialize_circuit_breakers()
        
        # Track partial failures for graceful degradation
        self.partial_failure_threshold = 0.5  # 50% success rate minimum
        
        logger.info("OrchestrationLayer initialized with comprehensive failure handling")
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for different components."""
        # Analysis engine circuit breaker
        analysis_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )
        self.analysis_cb = resilience_manager.create_circuit_breaker(
            "analysis_engine", analysis_config
        )
        
        # Task decomposer circuit breaker
        decomposer_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=45.0,
            success_threshold=2
        )
        self.decomposer_cb = resilience_manager.create_circuit_breaker(
            "task_decomposer", decomposer_config
        )
        
        # Arbitration layer circuit breaker
        arbitration_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3
        )
        self.arbitration_cb = resilience_manager.create_circuit_breaker(
            "arbitration_layer", arbitration_config
        )
        
        # Synthesis layer circuit breaker
        synthesis_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )
        self.synthesis_cb = resilience_manager.create_circuit_breaker(
            "synthesis_layer", synthesis_config
        )
    
    @with_adaptive_timeout("request_processing", "orchestration_layer")
    def process_request(self, user_input: str, execution_mode: ExecutionMode) -> FinalResponse:
        """
        Process a user request through the entire pipeline with comprehensive failure handling.
        
        This method coordinates all pipeline stages with resilience mechanisms:
        1. Analysis and task decomposition (with circuit breakers)
        2. Model routing and execution planning
        3. Parallel/sequential execution of subtasks (with partial failure handling)
        4. Arbitration of conflicting responses (with degradation)
        5. Synthesis of final response (with fallback)
        
        Args:
            user_input: Raw user input to process
            execution_mode: The execution mode (fast, balanced, best_quality)
            
        Returns:
            FinalResponse: The final processed response
        """
        start_time = time.time()
        execution_metadata = ExecutionMetadata()
        
        try:
            logger.info(f"Processing request in {execution_mode.value} mode: {user_input[:100]}...")
            
            # Stage 1: Analysis and Task Creation (with circuit breaker protection)
            try:
                task = self._create_task_from_input_protected(user_input, execution_mode)
                execution_metadata.execution_path.append("task_creation")
            except Exception as e:
                logger.error(f"Task creation failed: {str(e)}")
                if isinstance(e, AICouncilError):
                    raise
                raise ValidationError(f"Failed to analyze input: {str(e)}", original_error=e)
            
            # Stage 2: Cost Estimation (if required by execution mode)
            if execution_mode != ExecutionMode.FAST:
                try:
                    cost_estimate = self.estimate_cost_and_time(task)
                    logger.info(f"Estimated cost: ${cost_estimate.estimated_cost:.4f}, time: {cost_estimate.estimated_time:.1f}s")
                except Exception as e:
                    logger.warning(f"Cost estimation failed: {str(e)}")
                    # Continue without cost estimation
            
            # Stage 3: Task Decomposition (with circuit breaker protection)
            try:
                subtasks = self._decompose_task_protected(task)
                execution_metadata.execution_path.append("task_decomposition")
                logger.info(f"Decomposed into {len(subtasks)} subtasks")
            except Exception as e:
                logger.error(f"Task decomposition failed: {str(e)}")
                # Fallback to single subtask
                subtasks = [self._create_fallback_subtask(task)]
                execution_metadata.execution_path.append("fallback_decomposition")
            
            # Stage 4: Execution Planning
            try:
                execution_plan = self.model_context_protocol.determine_parallelism(subtasks)
                execution_metadata.parallel_executions = len(execution_plan.parallel_groups)
                execution_metadata.execution_path.append("execution_planning")
            except Exception as e:
                logger.warning(f"Execution planning failed: {str(e)}")
                # Fallback to sequential execution
                execution_plan = self._create_sequential_plan(subtasks)
                execution_metadata.execution_path.append("sequential_fallback")
            
            # Stage 5: Execute Subtasks (with partial failure handling)
            agent_responses = self._execute_subtasks_with_resilience(
                subtasks, execution_plan, execution_mode
            )
            execution_metadata.execution_path.append("subtask_execution")
            execution_metadata.models_used = list(set(resp.model_used for resp in agent_responses if resp.success))
            
            # Check for partial failure
            success_rate = sum(1 for resp in agent_responses if resp.success) / len(agent_responses)
            if success_rate < self.partial_failure_threshold:
                logger.warning(f"Partial failure detected: {success_rate:.1%} success rate")
                
                # Record partial failure event
                failure_event = create_failure_event(
                    failure_type=FailureType.PARTIAL_FAILURE,
                    component="orchestration_layer",
                    error_message=f"Only {success_rate:.1%} of subtasks succeeded",
                    context={
                        "success_rate": success_rate,
                        "total_subtasks": len(agent_responses),
                        "successful_subtasks": sum(1 for resp in agent_responses if resp.success)
                    }
                )
                
                recovery_action = resilience_manager.handle_failure(failure_event)
                if recovery_action.action_type == "continue_degraded":
                    execution_metadata.execution_path.append("partial_failure_degraded")
                else:
                    # Too many failures, return error response
                    return self._create_degraded_response(
                        "Too many subtask failures", execution_metadata, start_time,
                        f"Success rate {success_rate:.1%} below threshold"
                    )
            
            # Filter successful responses
            successful_responses = [resp for resp in agent_responses if resp.success]
            if not successful_responses:
                return self._create_degraded_response(
                    "All subtasks failed", execution_metadata, start_time,
                    "No successful subtask executions"
                )
            
            # Stage 6: Arbitration (if multiple responses, with circuit breaker)
            if len(successful_responses) > 1:
                try:
                    arbitration_result = self._arbitrate_with_protection(successful_responses)
                    validated_responses = arbitration_result.validated_responses
                    execution_metadata.arbitration_decisions = [
                        f"{res.chosen_response_id}: {res.reasoning}" 
                        for res in arbitration_result.conflicts_resolved
                    ]
                    execution_metadata.execution_path.append("arbitration")
                    logger.info(f"Arbitration resolved {len(arbitration_result.conflicts_resolved)} conflicts")
                except Exception as e:
                    logger.warning(f"Arbitration failed: {str(e)}")
                    # Fallback: use first successful response
                    validated_responses = successful_responses[:1]
                    execution_metadata.execution_path.append("arbitration_fallback")
            else:
                validated_responses = successful_responses
            
            # Stage 7: Synthesis (with circuit breaker protection)
            try:
                final_response = self._synthesize_with_protection(validated_responses)
                execution_metadata.execution_path.append("synthesis")
            except Exception as e:
                logger.error(f"Synthesis failed: {str(e)}")
                # Fallback: return first validated response as final response
                first_response = validated_responses[0]
                final_response = FinalResponse(
                    content=first_response.content,
                    overall_confidence=first_response.self_assessment.confidence_score if first_response.self_assessment else 0.5,
                    models_used=[first_response.model_used],
                    success=True
                )
                execution_metadata.execution_path.append("synthesis_fallback")
            
            # Stage 8: Attach Metadata
            execution_metadata.total_execution_time = time.time() - start_time
            final_response = self.synthesis_layer.attach_metadata(final_response, execution_metadata)
            
            logger.info(f"Request processed successfully in {execution_metadata.total_execution_time:.2f}s")
            return final_response
            
        except TimeoutError as e:
            logger.error(f"Request processing timed out: {str(e)}")
            raise ModelTimeoutError(f"Request processing timed out: {str(e)}", original_error=e)
            
        except Exception as e:
            if isinstance(e, AICouncilError):
                raise
            
            logger.error(f"Request processing failed: {str(e)}")
            execution_time = time.time() - start_time
            
            # Record system failure
            failure_event = create_failure_event(
                failure_type=FailureType.SYSTEM_OVERLOAD,
                component="orchestration_layer",
                error_message=str(e),
                context={"execution_time": execution_time}
            )
            resilience_manager.handle_failure(failure_event)
            
            return FinalResponse(
                content="",
                overall_confidence=0.0,
                execution_metadata=execution_metadata,
                success=False,
                error_message=f"Processing failed: {str(e)}",
                cost_breakdown=CostBreakdown(execution_time=execution_time)
            )
    
    def estimate_cost_and_time(self, task: Task) -> CostEstimate:
        """
        Estimate the cost and time for executing a task using cost optimization.
        
        Args:
            task: The task to estimate
            
        Returns:
            CostEstimate: Cost and time estimates with confidence
        """
        try:
            # Decompose task to get subtasks for estimation
            subtasks = self.task_decomposer.decompose(task)
            
            # Use cost optimizer for comprehensive cost analysis
            cost_breakdown = self.cost_optimizer.estimate_execution_cost(
                subtasks, task.execution_mode
            )
            
            total_cost = cost_breakdown['total_cost']
            
            # Estimate total time based on subtasks and execution mode
            total_time = 0.0
            confidence_scores = []
            
            for subtask in subtasks:
                # Get available models for cost-optimized selection
                available_models = [
                    m.get_model_id() 
                    for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                ]
                
                if available_models:
                    # Get optimized model selection
                    optimization = self.cost_optimizer.optimize_model_selection(
                        subtask, task.execution_mode, available_models
                    )
                    
                    total_time += optimization.estimated_time
                    confidence_scores.append(optimization.confidence)
            
            # Apply execution mode adjustments
            mode_config = self._execution_configs[task.execution_mode]
            total_cost *= mode_config['cost_multiplier']
            total_time *= mode_config['time_multiplier']
            
            # Calculate overall confidence
            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
            
            # Apply savings from cost optimization
            estimated_savings = cost_breakdown.get('estimated_savings', 0.0)
            total_cost = max(0.01, total_cost - estimated_savings)
            
            logger.info(f"Cost estimate: ${total_cost:.4f}, time: {total_time:.1f}s, savings: ${estimated_savings:.4f}")
            
            return CostEstimate(
                estimated_cost=total_cost,
                estimated_time=total_time,
                confidence=overall_confidence
            )
            
        except Exception as e:
            logger.warning(f"Cost estimation failed: {str(e)}")
            # Return conservative estimates
            return CostEstimate(
                estimated_cost=0.10,  # Default estimate
                estimated_time=30.0,  # Default 30 seconds
                confidence=0.3
            )
    
    def handle_failure(self, failure: ExecutionFailure) -> FallbackStrategy:
        """
        Handle execution failures with appropriate fallback strategies.
        
        Args:
            failure: The execution failure that occurred
            
        Returns:
            FallbackStrategy: The recommended fallback strategy
        """
        logger.warning(f"Handling failure: {failure.failure_type} - {failure.error_message}")
        
        # Determine fallback strategy based on failure type
        if failure.failure_type == "model_unavailable":
            # Try to find alternative model
            try:
                # Get subtask to find alternative model
                subtask = self._get_subtask_by_id(failure.subtask_id)
                if subtask:
                    fallback_selection = self.model_context_protocol.select_fallback(
                        failure.model_id, subtask
                    )
                    return FallbackStrategy(
                        strategy_type="alternative_model",
                        alternative_model=fallback_selection.model_id,
                        retry_count=1
                    )
            except Exception as e:
                logger.error(f"Failed to find alternative model: {str(e)}")
        
        elif failure.failure_type == "timeout":
            # Reduce complexity and retry
            return FallbackStrategy(
                strategy_type="reduce_complexity",
                retry_count=2
            )
        
        elif failure.failure_type == "rate_limit":
            # Wait and retry
            return FallbackStrategy(
                strategy_type="wait_and_retry",
                retry_count=3
            )
        
        elif failure.failure_type == "quality_failure":
            # Try with higher quality model
            return FallbackStrategy(
                strategy_type="upgrade_model",
                retry_count=1
            )
        
        else:
            # Generic retry strategy
            return FallbackStrategy(
                strategy_type="generic_retry",
                retry_count=1
            )
    
    def _create_task_from_input_protected(self, user_input: str, execution_mode: ExecutionMode) -> Task:
        """Create a Task object from user input with circuit breaker protection."""
        def protected_analysis():
            # Analyze the input
            intent = self.analysis_engine.analyze_intent(user_input)
            complexity = self.analysis_engine.determine_complexity(user_input)
            
            return Task(
                content=user_input,
                intent=intent,
                complexity=complexity,
                execution_mode=execution_mode
            )
        
        try:
            return self.analysis_cb.call(protected_analysis)
        except Exception as e:
            if isinstance(e, AICouncilError):
                raise
            raise OrchestrationError(f"Analysis engine failure: {str(e)}", original_error=e)
    
    def _decompose_task_protected(self, task: Task) -> List[Subtask]:
        """Decompose task into subtasks with circuit breaker protection."""
        def protected_decomposition():
            subtasks = self.task_decomposer.decompose(task)
            
            # Validate decomposition
            if not self.task_decomposer.validate_decomposition(subtasks):
                logger.warning("Task decomposition validation failed")
                raise ValueError("Invalid task decomposition")
            
            return subtasks
        
        try:
            return self.decomposer_cb.call(protected_decomposition)
        except Exception as e:
            if isinstance(e, AICouncilError):
                raise
            raise OrchestrationError(f"Task decomposer failure: {str(e)}", original_error=e)
    
    def _arbitrate_with_protection(self, responses: List[AgentResponse]):
        """Arbitrate responses with circuit breaker protection."""
        def protected_arbitration():
            return self.arbitration_layer.arbitrate(responses)
        
        try:
            return self.arbitration_cb.call(protected_arbitration)
        except Exception as e:
            if isinstance(e, AICouncilError):
                raise
            raise OrchestrationError(f"Arbitration layer failure: {str(e)}", original_error=e)
    
    def _synthesize_with_protection(self, validated_responses: List[AgentResponse]) -> FinalResponse:
        """Synthesize final response with circuit breaker protection."""
        def protected_synthesis():
            return self.synthesis_layer.synthesize(validated_responses)
        
        try:
            return self.synthesis_cb.call(protected_synthesis)
        except Exception as e:
            if isinstance(e, AICouncilError):
                raise
            raise OrchestrationError(f"Synthesis layer failure: {str(e)}", original_error=e)
    
    def _create_fallback_subtask(self, task: Task) -> Subtask:
        """Create a fallback subtask when decomposition fails."""
        task_types = []
        try:
            task_types = self.analysis_engine.classify_task_type(task.content)
        except Exception:
            from ..core.models import TaskType
            task_types = [TaskType.REASONING]  # Default fallback
        
        return Subtask(
            parent_task_id=task.id,
            content=task.content,
            task_type=task_types[0] if task_types else None
        )
    
    def _create_sequential_plan(self, subtasks: List[Subtask]):
        """Create a sequential execution plan as fallback."""
        from ..core.interfaces import ExecutionPlan
        
        # Simple sequential plan - each subtask in its own group
        parallel_groups = [[subtask] for subtask in subtasks]
        sequential_order = [subtask.id for subtask in subtasks]
        
        return ExecutionPlan(parallel_groups, sequential_order)
    
    def _execute_subtasks_with_resilience(
        self, 
        subtasks: List[Subtask], 
        execution_plan, 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute subtasks with comprehensive resilience handling."""
        all_responses = []
        failed_groups = 0
        total_groups = len(execution_plan.parallel_groups)
        
        # Execute parallel groups sequentially, but tasks within groups in parallel
        for group_index, group in enumerate(execution_plan.parallel_groups):
            try:
                group_responses = self._execute_parallel_group_resilient(group, execution_mode)
                all_responses.extend(group_responses)
                
                # Check group success rate
                group_success_rate = sum(1 for resp in group_responses if resp.success) / len(group_responses)
                if group_success_rate < 0.5:  # Less than 50% success
                    failed_groups += 1
                    logger.warning(f"Group {group_index} had low success rate: {group_success_rate:.1%}")
                
                # Check if we should continue or fail fast
                if failed_groups / (group_index + 1) > 0.5 and execution_mode == ExecutionMode.FAST:
                    logger.warning("Too many group failures in FAST mode, stopping execution")
                    break
                    
            except Exception as e:
                logger.error(f"Group {group_index} execution failed: {str(e)}")
                failed_groups += 1
                
                # Create failure responses for all subtasks in the group
                for subtask in group:
                    failure_response = AgentResponse(
                        subtask_id=subtask.id,
                        model_used="unknown",
                        content="",
                        success=False,
                        error_message=f"Group execution failed: {str(e)}"
                    )
                    all_responses.append(failure_response)
        
        return all_responses
    
    def _execute_parallel_group_resilient(
        self, 
        subtasks: List[Subtask], 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute a group of subtasks with resilience mechanisms."""
        responses = []
        
        for subtask in subtasks:
            try:
                # Check system health before execution
                health = resilience_manager.health_check()
                if health["overall_health"] == "degraded" and execution_mode == ExecutionMode.FAST:
                    # Skip non-critical subtasks in degraded mode
                    if subtask.priority.value in ["low", "medium"]:
                        logger.info(f"Skipping subtask {subtask.id} due to degraded system health")
                        skip_response = AgentResponse(
                            subtask_id=subtask.id,
                            model_used="skipped",
                            content="",
                            success=False,
                            error_message="Skipped due to system degradation",
                            metadata={"skipped": True, "reason": "system_degraded"}
                        )
                        responses.append(skip_response)
                        continue
                
                # Get available models for this task type
                available_models = [
                    m.get_model_id() 
                    for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                ]
                
                if not available_models:
                    logger.error(f"No models available for task type {subtask.task_type}")
                    failure_response = AgentResponse(
                        subtask_id=subtask.id,
                        model_used="none_available",
                        content="",
                        success=False,
                        error_message=f"No models available for task type {subtask.task_type}"
                    )
                    responses.append(failure_response)
                    continue
                
                # Use cost optimizer for model selection
                optimization = self.cost_optimizer.optimize_model_selection(
                    subtask, execution_mode, available_models
                )
                
                logger.info(f"Cost-optimized selection: {optimization.reasoning}")
                
                # Get the actual model instance
                models = self.model_registry.get_models_for_task_type(subtask.task_type)
                selected_model = next(
                    (m for m in models if m.get_model_id() == optimization.recommended_model),
                    None
                )
                
                if not selected_model:
                    logger.error(f"Optimized model {optimization.recommended_model} not found")
                    failure_response = AgentResponse(
                        subtask_id=subtask.id,
                        model_used=optimization.recommended_model,
                        content="",
                        success=False,
                        error_message=f"Selected model {optimization.recommended_model} not available"
                    )
                    responses.append(failure_response)
                    continue
                
                # Execute subtask with timeout protection
                response = timeout_handler.execute_with_timeout(
                    self.execution_agent.execute,
                    adaptive_timeout_manager.get_adaptive_timeout("subtask_execution"),
                    "subtask_execution",
                    "orchestration_layer",
                    subtask.id,
                    selected_model.get_model_id(),
                    subtask,
                    selected_model
                )
                
                # Update cost optimizer with actual performance
                if response.success and response.self_assessment:
                    actual_cost = response.self_assessment.estimated_cost
                    quality_score = response.self_assessment.confidence_score
                    self.cost_optimizer.update_performance_history(
                        optimization.recommended_model, actual_cost, quality_score
                    )
                
                responses.append(response)
                
            except TimeoutError as e:
                logger.warning(f"Subtask {subtask.id} timed out: {str(e)}")
                timeout_response = AgentResponse(
                    subtask_id=subtask.id,
                    model_used="timeout",
                    content="",
                    success=False,
                    error_message=f"Execution timed out: {str(e)}",
                    metadata={"timeout": True, "timeout_duration": e.timeout_duration}
                )
                responses.append(timeout_response)
                
            except Exception as e:
                logger.error(f"Failed to execute subtask {subtask.id}: {str(e)}")
                # Create failure response
                failure_response = AgentResponse(
                    subtask_id=subtask.id,
                    model_used="unknown",
                    content="",
                    success=False,
                    error_message=str(e)
                )
                responses.append(failure_response)
        
        return responses
    
    def _create_degraded_response(
        self, 
        message: str, 
        execution_metadata: ExecutionMetadata, 
        start_time: float,
        error_details: str = ""
    ) -> FinalResponse:
        """Create a degraded response when partial functionality is available."""
        execution_time = time.time() - start_time
        execution_metadata.total_execution_time = execution_time
        
        return FinalResponse(
            content=f"System operating in degraded mode: {message}",
            overall_confidence=0.2,
            execution_metadata=execution_metadata,
            success=False,
            error_message=f"Degraded operation: {error_details}" if error_details else message,
            cost_breakdown=CostBreakdown(execution_time=execution_time),
            models_used=[]
        )
    
    def _create_timeout_response(
        self, 
        execution_metadata: ExecutionMetadata, 
        start_time: float,
        timeout_details: str
    ) -> FinalResponse:
        """Create a timeout response."""
        execution_time = time.time() - start_time
        execution_metadata.total_execution_time = execution_time
        
        return FinalResponse(
            content="",
            overall_confidence=0.0,
            execution_metadata=execution_metadata,
            success=False,
            error_message=f"Request timed out: {timeout_details}",
            cost_breakdown=CostBreakdown(execution_time=execution_time),
            models_used=[]
        )
    
    def _decompose_task(self, task: Task) -> List[Subtask]:
        """Decompose task into subtasks."""
        subtasks = self.task_decomposer.decompose(task)
        
        # Validate decomposition
        if not self.task_decomposer.validate_decomposition(subtasks):
            logger.warning("Task decomposition validation failed, using single subtask")
            # Fallback to single subtask
            return [Subtask(
                parent_task_id=task.id,
                content=task.content,
                task_type=self.analysis_engine.classify_task_type(task.content)[0]
            )]
        
        return subtasks
    
    def _execute_subtasks(
        self, 
        subtasks: List[Subtask], 
        execution_plan, 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute subtasks according to the execution plan."""
        all_responses = []
        
        # Execute parallel groups sequentially, but tasks within groups in parallel
        for group in execution_plan.parallel_groups:
            group_responses = self._execute_parallel_group(group, execution_mode)
            all_responses.extend(group_responses)
        
        return all_responses
    
    def _execute_parallel_group(
        self, 
        subtasks: List[Subtask], 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute a group of subtasks that can run in parallel with cost optimization."""
        responses = []
        
        for subtask in subtasks:
            try:
                # Get available models for this task type
                available_models = [
                    m.get_model_id() 
                    for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                ]
                
                if not available_models:
                    logger.error(f"No models available for task type {subtask.task_type}")
                    continue
                
                # Use cost optimizer for model selection
                optimization = self.cost_optimizer.optimize_model_selection(
                    subtask, execution_mode, available_models
                )
                
                logger.info(f"Cost-optimized selection: {optimization.reasoning}")
                
                # Get the actual model instance
                models = self.model_registry.get_models_for_task_type(subtask.task_type)
                selected_model = next(
                    (m for m in models if m.get_model_id() == optimization.recommended_model),
                    None
                )
                
                if not selected_model:
                    logger.error(f"Optimized model {optimization.recommended_model} not found")
                    continue
                
                # Execute subtask
                response = self.execution_agent.execute(subtask, selected_model)
                
                # Update cost optimizer with actual performance
                if response.success and response.self_assessment:
                    actual_cost = response.self_assessment.estimated_cost
                    quality_score = response.self_assessment.confidence_score
                    self.cost_optimizer.update_performance_history(
                        optimization.recommended_model, actual_cost, quality_score
                    )
                
                responses.append(response)
                
            except Exception as e:
                logger.error(f"Failed to execute subtask {subtask.id}: {str(e)}")
                # Create failure response
                failure_response = AgentResponse(
                    subtask_id=subtask.id,
                    model_used="unknown",
                    content="",
                    success=False,
                    error_message=str(e)
                )
                responses.append(failure_response)
        
        return responses
    
    def _estimate_subtask_cost(self, subtask: Subtask, model) -> float:
        """Estimate cost for a single subtask with a specific model."""
        try:
            cost_profile = self.model_registry.get_model_cost_profile(model.get_model_id())
            
            # Estimate tokens based on content length
            estimated_input_tokens = len(subtask.content.split()) * 1.3
            estimated_output_tokens = estimated_input_tokens * 0.5  # Assume 50% output ratio
            
            cost = (estimated_input_tokens * cost_profile.cost_per_input_token + 
                   estimated_output_tokens * cost_profile.cost_per_output_token)
            
            return max(cost, cost_profile.minimum_cost)
            
        except Exception:
            return 0.01  # Default cost estimate
    
    def _estimate_subtask_time(self, subtask: Subtask, model) -> float:
        """Estimate execution time for a single subtask with a specific model."""
        try:
            capabilities = self.model_registry.get_model_capabilities(model.get_model_id())
            base_time = capabilities.average_latency
            
            # Adjust based on content complexity
            content_length = len(subtask.content)
            if content_length > 1000:
                base_time *= 1.5
            elif content_length > 500:
                base_time *= 1.2
            
            return base_time
            
        except Exception:
            return 5.0  # Default time estimate
    
    def _get_subtask_by_id(self, subtask_id: str) -> Optional[Subtask]:
        """Get subtask by ID - simplified implementation."""
        # In a real implementation, this would maintain a registry of active subtasks
        return None
    
    def analyze_cost_quality_tradeoffs(self, task: Task) -> Dict[str, Any]:
        """
        Analyze cost vs quality trade-offs for a task across different execution modes.
        
        Args:
            task: The task to analyze
            
        Returns:
            Dict[str, Any]: Analysis results including recommendations
        """
        try:
            subtasks = self.task_decomposer.decompose(task)
            analysis_results = {}
            
            # Analyze each execution mode
            for mode in ExecutionMode:
                mode_analysis = {
                    'total_cost': 0.0,
                    'total_time': 0.0,
                    'average_quality': 0.0,
                    'model_selections': [],
                    'trade_off_score': 0.0
                }
                
                quality_scores = []
                
                for subtask in subtasks:
                    available_models = [
                        m.get_model_id() 
                        for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                    ]
                    
                    if available_models:
                        # Get cost-optimized selection for this mode
                        optimization = self.cost_optimizer.optimize_model_selection(
                            subtask, mode, available_models
                        )
                        
                        mode_analysis['total_cost'] += optimization.estimated_cost
                        mode_analysis['total_time'] += optimization.estimated_time
                        quality_scores.append(optimization.quality_score)
                        
                        mode_analysis['model_selections'].append({
                            'subtask_id': subtask.id,
                            'model': optimization.recommended_model,
                            'cost': optimization.estimated_cost,
                            'quality': optimization.quality_score,
                            'reasoning': optimization.reasoning
                        })
                
                # Calculate averages and trade-off score
                if quality_scores:
                    mode_analysis['average_quality'] = sum(quality_scores) / len(quality_scores)
                    # Trade-off score: quality per dollar
                    mode_analysis['trade_off_score'] = (
                        mode_analysis['average_quality'] / max(mode_analysis['total_cost'], 0.001)
                    )
                
                analysis_results[mode.value] = mode_analysis
            
            # Add recommendations
            analysis_results['recommendations'] = self._generate_mode_recommendations(analysis_results)
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Cost-quality analysis failed: {str(e)}")
            return {'error': str(e)}
    
    def _generate_mode_recommendations(self, analysis_results: Dict[str, Any]) -> Dict[str, str]:
        """Generate recommendations based on cost-quality analysis."""
        recommendations = {}
        
        # Find best mode for different criteria
        modes_data = {k: v for k, v in analysis_results.items() if k != 'recommendations'}
        
        if modes_data:
            # Best cost efficiency
            best_cost = min(modes_data.items(), key=lambda x: x[1]['total_cost'])
            recommendations['lowest_cost'] = f"{best_cost[0]} (${best_cost[1]['total_cost']:.4f})"
            
            # Best quality
            best_quality = max(modes_data.items(), key=lambda x: x[1]['average_quality'])
            recommendations['highest_quality'] = f"{best_quality[0]} ({best_quality[1]['average_quality']:.2f})"
            
            # Best trade-off
            best_tradeoff = max(modes_data.items(), key=lambda x: x[1]['trade_off_score'])
            recommendations['best_value'] = f"{best_tradeoff[0]} (score: {best_tradeoff[1]['trade_off_score']:.2f})"
            
            # Fastest execution
            fastest = min(modes_data.items(), key=lambda x: x[1]['total_time'])
            recommendations['fastest'] = f"{fastest[0]} ({fastest[1]['total_time']:.1f}s)"
        
        return recommendations
    
    def _build_execution_configs(self) -> Dict[ExecutionMode, Dict[str, float]]:
        """Build configuration multipliers for different execution modes."""
        return {
            ExecutionMode.FAST: {
                'cost_multiplier': 0.7,  # Use cheaper models
                'time_multiplier': 0.5,  # Prioritize speed
                'quality_threshold': 0.6,  # Lower quality threshold
                'parallelism_factor': 1.5  # More aggressive parallelism
            },
            ExecutionMode.BALANCED: {
                'cost_multiplier': 1.0,  # Standard cost
                'time_multiplier': 1.0,  # Standard time
                'quality_threshold': 0.8,  # Standard quality
                'parallelism_factor': 1.0  # Standard parallelism
            },
            ExecutionMode.BEST_QUALITY: {
                'cost_multiplier': 1.5,  # Use premium models
                'time_multiplier': 1.8,  # Allow more time
                'quality_threshold': 0.95,  # High quality threshold
                'parallelism_factor': 0.8  # Less parallelism for quality
            }
        }