"""Implementation of the OrchestrationLayer for main request processing pipeline."""

import logging
import time
from typing import List, Dict, Optional, Any, Callable
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
from ..core.error_handling import create_error_response
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
    
    # =========================================================================
    # PIPELINE STAGE METHODS - Extracted for better readability
    # =========================================================================
    
    def _stage_analyze_and_create_task(
        self, 
        user_input: str, 
        execution_mode: ExecutionMode
    ) -> Task:
        """
        Stage 1: Analyze user input and create a Task.
        
        Args:
            user_input: Raw user input
            execution_mode: The execution mode
            
        Returns:
            Task: Created task object
        """
        return self._create_task_from_input_protected(user_input, execution_mode)
    
    def _stage_estimate_cost(self, task: Task) -> Optional[CostEstimate]:
        """
        Stage 2: Estimate cost and time for the task.
        
        Args:
            task: The task to estimate
            
        Returns:
            Optional[CostEstimate]: Cost estimate if available
        """
        try:
            return self.estimate_cost_and_time(task)
        except Exception as e:
            logger.warning(f"Cost estimation failed: {str(e)}")
            return None
    
    def _stage_decompose_task(self, task: Task) -> List[Subtask]:
        """
        Stage 3: Decompose task into subtasks.
        
        Args:
            task: The task to decompose
            
        Returns:
            List[Subtask]: List of subtasks
        """
        try:
            return self._decompose_task_protected(task)
        except Exception as e:
            logger.error(f"Task decomposition failed: {str(e)}")
            # Fallback to single subtask
            return [self._create_fallback_subtask(task)]
    
    def _stage_plan_execution(self, subtasks: List[Subtask]):
        """
        Stage 4: Create execution plan for subtasks.
        
        Args:
            subtasks: List of subtasks to plan
            
        Returns:
            ExecutionPlan: Plan for parallel/sequential execution
        """
        try:
            return self.model_context_protocol.determine_parallelism(subtasks)
        except Exception as e:
            logger.warning(f"Execution planning failed: {str(e)}")
            return self._create_sequential_plan(subtasks)
    
    def _stage_execute_subtasks(
        self, 
        subtasks: List[Subtask], 
        execution_plan, 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """
        Stage 5: Execute all subtasks with resilience handling.
        
        Args:
            subtasks: List of subtasks to execute
            execution_plan: The execution plan
            execution_mode: The execution mode
            
        Returns:
            List[AgentResponse]: Responses from all subtasks
        """
        return self._execute_subtasks_with_resilience(
            subtasks, execution_plan, execution_mode
        )
    
    def _stage_check_partial_failure(
        self, 
        agent_responses: List[AgentResponse],
        execution_metadata: ExecutionMetadata
    ) -> Optional[str]:
        """
        Check for partial failure and handle if detected.
        
        Args:
            agent_responses: List of agent responses
            execution_metadata: Execution metadata to update
            
        Returns:
            Optional[str]: Action to take ('continue', 'degraded', 'fail')
        """
        # Guard: Handle empty agent_responses to avoid division by zero
        if not agent_responses:
            logger.debug("No agent responses to check for partial failure")
            return "continue"
        
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
                return "degraded"
            else:
                return "fail"
        
        return "continue"
    
    def _stage_arbitrate(
        self, 
        responses: List[AgentResponse]
    ) -> List[AgentResponse]:
        """
        Stage 6: Arbitrate between multiple responses.
        
        Args:
            responses: List of agent responses to arbitrate
            
        Returns:
            List[AgentResponse]: Validated responses after arbitration
        """
        if len(responses) <= 1:
            return responses
        
        try:
            arbitration_result = self._arbitrate_with_protection(responses)
            return arbitration_result.validated_responses
        except Exception as e:
            logger.warning(f"Arbitration failed: {str(e)}")
            # Fallback: use first successful response
            return responses[:1]
    
    def _stage_synthesize(
        self, 
        validated_responses: List[AgentResponse]
    ) -> FinalResponse:
        """
        Stage 7: Synthesize final response from validated responses.
        
        Args:
            validated_responses: List of validated responses
            
        Returns:
            FinalResponse: Synthesized final response
        """
        try:
            return self._synthesize_with_protection(validated_responses)
        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            # Guard: Handle empty validated_responses to avoid IndexError
            if not validated_responses:
                logger.warning("No validated responses available for synthesis fallback")
                return FinalResponse(
                    content="",
                    overall_confidence=0.5,
                    models_used=[],
                    success=False,
                    error_message="No responses available for synthesis"
                )
            # Fallback: return first validated response as final response
            first_response = validated_responses[0]
            return FinalResponse(
                content=first_response.content,
                overall_confidence=first_response.self_assessment.confidence_score if first_response.self_assessment else 0.5,
                models_used=[first_response.model_used],
                success=True
            )
    
    def _stage_attach_metadata(
        self, 
        response: FinalResponse, 
        execution_metadata: ExecutionMetadata
    ) -> FinalResponse:
        """
        Stage 8: Attach execution metadata to the final response.
        
        Args:
            response: The final response
            execution_metadata: Metadata to attach
            
        Returns:
            FinalResponse: Response with metadata attached
        """
        return self.synthesis_layer.attach_metadata(response, execution_metadata)
    
    # =========================================================================
    # MAIN PROCESS REQUEST - Now uses extracted stage methods
    # =========================================================================
    
    @with_adaptive_timeout("request_processing", "orchestration_layer")
    def process_request(self, user_input: str, execution_mode: ExecutionMode) -> FinalResponse:
        """
        Process a user request through the entire pipeline.
        
        This method coordinates all pipeline stages:
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
            
            # Stage 1: Analysis and Task Creation
            task = self._stage_analyze_and_create_task(user_input, execution_mode)
            execution_metadata.execution_path.append("task_creation")
            
            # Stage 2: Cost Estimation (if required by execution mode)
            if execution_mode != ExecutionMode.FAST:
                cost_estimate = self._stage_estimate_cost(task)
                if cost_estimate:
                    logger.info(f"Estimated cost: ${cost_estimate.estimated_cost:.4f}, time: {cost_estimate.estimated_time:.1f}s")
            
            # Stage 3: Task Decomposition
            subtasks = self._stage_decompose_task(task)
            execution_metadata.execution_path.append("task_decomposition")
            logger.info(f"Decomposed into {len(subtasks)} subtasks")
            
            # Stage 4: Execution Planning
            execution_plan = self._stage_plan_execution(subtasks)
            execution_metadata.parallel_executions = len(execution_plan.parallel_groups)
            execution_metadata.execution_path.append("execution_planning")
            
            # Stage 5: Execute Subtasks
            agent_responses = self._stage_execute_subtasks(
                subtasks, execution_plan, execution_mode
            )
            execution_metadata.execution_path.append("subtask_execution")
            execution_metadata.models_used = list(set(
                resp.model_used for resp in agent_responses if resp.success
            ))
            
            # Check for partial failure
            partial_failure_action = self._stage_check_partial_failure(
                agent_responses, execution_metadata
            )
            
            if partial_failure_action == "fail":
                return self._create_degraded_response(
                    "Too many subtask failures", execution_metadata, start_time,
                    f"Success rate below {self.partial_failure_threshold:.0%} threshold"
                )
            
            # Filter successful responses
            successful_responses = [resp for resp in agent_responses if resp.success]
            if not successful_responses:
                return self._create_degraded_response(
                    "All subtasks failed", execution_metadata, start_time,
                    "No successful subtask executions"
                )
            
            # Stage 6: Arbitration
            validated_responses = self._stage_arbitrate(successful_responses)
            execution_metadata.execution_path.append("arbitration")
            
            # Stage 7: Synthesis
            final_response = self._stage_synthesize(validated_responses)
            execution_metadata.execution_path.append("synthesis")
            
            # Stage 8: Attach Metadata
            execution_metadata.total_execution_time = time.time() - start_time
            final_response = self._stage_attach_metadata(final_response, execution_metadata)
            
            logger.info(f"Request processed successfully in {execution_metadata.total_execution_time:.2f}s")
            return final_response
            
        except TimeoutError as e:
            logger.error(f"Request processing timed out: {str(e)}")
            raise ModelTimeoutError(f"Request processing timed out: {str(e)}", original_error=e)
            
        except AICouncilError:
            # Re-raise AICouncilError exceptions
            raise
            
        except Exception as e:
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
            
            return create_error_response(
                e,
                context={'component': 'orchestration_layer.process_request'}
            )
    
    # =========================================================================
    # PROTECTED METHODS - With circuit breaker protection
    # =========================================================================
    
    def _create_task_from_input_protected(self, user_input: str, execution_mode: ExecutionMode) -> Task:
        """Create a Task object from user input with circuit breaker protection."""
        def protected_analysis():
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
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
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
        
        parallel_groups = [[subtask] for subtask in subtasks]
        sequential_order = [subtask.id for subtask in subtasks]
        
        return ExecutionPlan(parallel_groups, sequential_order)
    
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
    
    # =========================================================================
    # EXECUTION METHODS - Refactored for better organization
    # =========================================================================
    
    def _execute_subtasks_with_resilience(
        self, 
        subtasks: List[Subtask], 
        execution_plan, 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute subtasks with comprehensive resilience handling."""
        all_responses = []
        failed_groups = 0
        
        # Execute parallel groups sequentially
        for group_index, group in enumerate(execution_plan.parallel_groups):
            group_responses = self._execute_parallel_group_resilient(group, execution_mode)
            all_responses.extend(group_responses)
            
            # Check group success rate
            group_success_rate = sum(1 for resp in group_responses if resp.success) / len(group_responses)
            if group_success_rate < 0.5:
                failed_groups += 1
                logger.warning(f"Group {group_index} had low success rate: {group_success_rate:.1%}")
            
            # Check if we should continue or fail fast
            if failed_groups / (group_index + 1) > 0.5 and execution_mode == ExecutionMode.FAST:
                logger.warning("Too many group failures in FAST mode, stopping execution")
                break
                    
        return all_responses
    
    def _execute_parallel_group_resilient(
        self, 
        subtasks: List[Subtask], 
        execution_mode: ExecutionMode
    ) -> List[AgentResponse]:
        """Execute a group of subtasks with resilience mechanisms."""
        responses = []
        
        for subtask in subtasks:
            response = self._execute_single_subtask(subtask, execution_mode)
            responses.append(response)
        
        return responses
    
    def _execute_single_subtask(
        self, 
        subtask: Subtask, 
        execution_mode: ExecutionMode
    ) -> AgentResponse:
        """Execute a single subtask with full error handling."""
        try:
            # Check system health before execution
            health = resilience_manager.health_check()
            if health["overall_health"] == "degraded" and execution_mode == ExecutionMode.FAST:
                if subtask.priority.value in ["low", "medium"]:
                    logger.info(f"Skipping subtask {subtask.id} due to degraded system health")
                    return AgentResponse(
                        subtask_id=subtask.id,
                        model_used="skipped",
                        content="",
                        success=False,
                        error_message="Skipped due to system degradation",
                        metadata={"skipped": True, "reason": "system_degraded"}
                    )
            
            # Get available models
            available_models = [
                m.get_model_id() 
                for m in self.model_registry.get_models_for_task_type(subtask.task_type)
            ]
            
            if not available_models:
                logger.error(f"No models available for task type {subtask.task_type}")
                return AgentResponse(
                    subtask_id=subtask.id,
                    model_used="none_available",
                    content="",
                    success=False,
                    error_message=f"No models available for task type {subtask.task_type}"
                )
            
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
                return AgentResponse(
                    subtask_id=subtask.id,
                    model_used=optimization.recommended_model,
                    content="",
                    success=False,
                    error_message=f"Selected model {optimization.recommended_model} not available"
                )
            
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
                self.cost_optimizer.update_performance_history(
                    optimization.recommended_model,
                    response.self_assessment.estimated_cost,
                    response.self_assessment.confidence_score
                )
            
            return response
            
        except TimeoutError as e:
            logger.warning(f"Subtask {subtask.id} timed out: {str(e)}")
            return AgentResponse(
                subtask_id=subtask.id,
                model_used="timeout",
                content="",
                success=False,
                error_message=f"Execution timed out: {str(e)}",
                metadata={"timeout": True, "timeout_duration": e.timeout_duration}
            )
            
        except Exception as e:
            logger.error(f"Failed to execute subtask {subtask.id}: {str(e)}")
            return AgentResponse(
                subtask_id=subtask.id,
                model_used="unknown",
                content="",
                success=False,
                error_message=str(e)
            )
    
    # =========================================================================
    # PUBLIC METHODS - Required by interface
    # =========================================================================
    
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
                available_models = [
                    m.get_model_id() 
                    for m in self.model_registry.get_models_for_task_type(subtask.task_type)
                ]
                
                if available_models:
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
            return CostEstimate(
                estimated_cost=0.10,
                estimated_time=30.0,
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
            try:
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
            return FallbackStrategy(strategy_type="reduce_complexity", retry_count=2)
        
        elif failure.failure_type == "rate_limit":
            return FallbackStrategy(strategy_type="wait_and_retry", retry_count=3)
        
        elif failure.failure_type == "quality_failure":
            return FallbackStrategy(strategy_type="upgrade_model", retry_count=1)
        
        else:
            return FallbackStrategy(strategy_type="generic_retry", retry_count=1)
    
    def _get_subtask_by_id(self, subtask_id: str) -> Optional[Subtask]:
        """Get subtask by ID - simplified implementation."""
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
                
                if quality_scores:
                    mode_analysis['average_quality'] = sum(quality_scores) / len(quality_scores)
                    mode_analysis['trade_off_score'] = (
                        mode_analysis['average_quality'] / max(mode_analysis['total_cost'], 0.001)
                    )
                
                analysis_results[mode.value] = mode_analysis
            
            analysis_results['recommendations'] = self._generate_mode_recommendations(analysis_results)
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Cost-quality analysis failed: {str(e)}")
            return {'error': str(e)}
    
    def _generate_mode_recommendations(self, analysis_results: Dict[str, Any]) -> Dict[str, str]:
        """Generate recommendations based on cost-quality analysis."""
        recommendations = {}
        
        modes_data = {k: v for k, v in analysis_results.items() if k != 'recommendations'}
        
        if modes_data:
            best_cost = min(modes_data.items(), key=lambda x: x[1]['total_cost'])
            recommendations['lowest_cost'] = f"{best_cost[0]} (${best_cost[1]['total_cost']:.4f})"
            
            best_quality = max(modes_data.items(), key=lambda x: x[1]['average_quality'])
            recommendations['highest_quality'] = f"{best_quality[0]} ({best_quality[1]['average_quality']:.2f})"
            
            best_tradeoff = max(modes_data.items(), key=lambda x: x[1]['trade_off_score'])
            recommendations['best_value'] = f"{best_tradeoff[0]} (score: {best_tradeoff[1]['trade_off_score']:.2f})"
            
            fastest = min(modes_data.items(), key=lambda x: x[1]['total_time'])
            recommendations['fastest'] = f"{fastest[0]} ({fastest[1]['total_time']:.1f}s)"
        
        return recommendations
    
    def _build_execution_configs(self) -> Dict[ExecutionMode, Dict[str, float]]:
        """Build configuration multipliers for different execution modes."""
        return {
            ExecutionMode.FAST: {
                'cost_multiplier': 0.7,
                'time_multiplier': 0.5,
                'quality_threshold': 0.6,
                'parallelism_factor': 1.5
            },
            ExecutionMode.BALANCED: {
                'cost_multiplier': 1.0,
                'time_multiplier': 1.0,
                'quality_threshold': 0.8,
                'parallelism_factor': 1.0
            },
            ExecutionMode.BEST_QUALITY: {
                'cost_multiplier': 1.5,
                'time_multiplier': 1.8,
                'quality_threshold': 0.95,
                'parallelism_factor': 0.8
            }
        }
