"""Execution agent implementation for AI Council."""

import time
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.interfaces import ExecutionAgent, AIModel, ModelError, FailureResponse
from ..core.models import Subtask, AgentResponse, SelfAssessment, RiskLevel
from ..core.failure_handling import (
    FailureEvent, FailureType, resilience_manager, create_failure_event
)
from ..core.timeout_handler import (
    timeout_handler, adaptive_timeout_manager, rate_limit_manager,
    with_adaptive_timeout, with_rate_limit, TimeoutError
)


logger = logging.getLogger(__name__)


class BaseExecutionAgent(ExecutionAgent):
    """Base implementation of ExecutionAgent with comprehensive failure handling."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize the execution agent.
        
        Args:
            max_retries: Maximum number of retry attempts for failed executions
            retry_delay: Base delay in seconds between retry attempts
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._execution_history: Dict[str, Any] = {}
        
        # Initialize circuit breakers for different failure types
        from ..core.failure_handling import CircuitBreakerConfig
        
        # Circuit breaker for model API calls
        api_cb_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3
        )
        self.api_circuit_breaker = resilience_manager.create_circuit_breaker(
            "model_api", api_cb_config
        )
        
        # Set up rate limits for common model providers
        rate_limit_manager.set_rate_limit("openai", 60)  # 60 requests per minute
        rate_limit_manager.set_rate_limit("anthropic", 50)  # 50 requests per minute
        rate_limit_manager.set_rate_limit("default", 30)  # Default rate limit
    
    async def execute(self, subtask: Subtask, model: AIModel) -> AgentResponse:
        """Execute a subtask using the specified AI model with comprehensive failure handling.
        
        Args:
            subtask: The subtask to execute
            model: The AI model to use for execution
            
        Returns:
            AgentResponse: The response including content and self-assessment
        """
        start_time = time.time()
        model_id = model.get_model_id()
        
        logger.info(f"Executing subtask {subtask.id} with model {model_id}")
        
        # Track execution attempt
        execution_key = f"{subtask.id}_{model_id}"
        self._execution_history[execution_key] = {
            "attempts": 0,
            "start_time": start_time,
            "subtask_id": subtask.id,
            "model_id": model_id
        }
        
        # Check if component is isolated
        if resilience_manager.failure_isolator.is_isolated(f"model_{model_id}"):
            logger.warning(f"Model {model_id} is isolated, skipping execution")
            return self._create_failure_response(
                subtask, model_id, "Model is temporarily isolated", start_time
            )
        
        last_error = None
        recovery_action = None
        
        for attempt in range(self.max_retries + 1):
            try:
                self._execution_history[execution_key]["attempts"] = attempt + 1
                
                # Apply rate limiting
                provider = self._get_model_provider(model_id)
                while True:
                    allowed, wait_time = rate_limit_manager.check_rate_limit(provider)
                    if not allowed:
                        logger.info(f"Rate limit hit for {provider}, waiting {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                    else:
                        break
                
                # Execute with circuit breaker and timeout
                response_content = await self._execute_with_protection(subtask, model)
                
                # Generate self-assessment
                self_assessment = self.generate_self_assessment(response_content, subtask)
                self_assessment.model_used = model_id
                self_assessment.execution_time = time.time() - start_time
                
                # Record successful execution time for adaptive timeouts
                execution_time = time.time() - start_time
                adaptive_timeout_manager.record_execution_time("model_execution", execution_time)
                
                # Create successful response
                agent_response = AgentResponse(
                    subtask_id=subtask.id,
                    model_used=model_id,
                    content=response_content,
                    self_assessment=self_assessment,
                    timestamp=datetime.utcnow(),
                    success=True,
                    metadata={
                        "attempts": attempt + 1,
                        "execution_time": execution_time,
                        "prompt_length": len(self._build_prompt(subtask)),
                        "recovery_action": recovery_action.action_type if recovery_action else None
                    }
                )
                
                logger.info(f"Successfully executed subtask {subtask.id} on attempt {attempt + 1}")
                return agent_response
                
            except Exception as e:
                last_error = e
                
                # Create failure event
                failure_event = self._create_failure_event(e, subtask, model_id, attempt)
                
                # Get recovery action from resilience manager
                recovery_action = resilience_manager.handle_failure(failure_event)
                
                logger.warning(
                    f"Attempt {attempt + 1} failed for subtask {subtask.id} "
                    f"with model {model_id}: {str(e)} - Recovery: {recovery_action.action_type}"
                )
                
                # Handle recovery action
                if not recovery_action.should_retry or attempt >= self.max_retries:
                    if recovery_action.fallback_model:
                        # Try fallback model
                        return await self._execute_with_fallback(
                            subtask, recovery_action.fallback_model, start_time
                        )
                    elif recovery_action.skip_subtask:
                        # Skip this subtask
                        return self._create_skip_response(subtask, model_id, start_time)
                    else:
                        # No more retries or recovery options
                        break
                
                # Apply retry delay with jitter
                if attempt < self.max_retries and recovery_action.retry_delay > 0:
                    import random
                    jitter = random.uniform(0.8, 1.2)  # ±20% jitter
                    delay = recovery_action.retry_delay * jitter
                    logger.info(f"Waiting {delay:.1f}s before retry")
                    await asyncio.sleep(delay)
        
        # All attempts failed, return failure response
        return self._create_failure_response(subtask, model_id, str(last_error), start_time)
    
    async def _execute_with_protection(self, subtask: Subtask, model: AIModel) -> str:
        """Execute model call with circuit breaker and timeout protection."""
        async def protected_call():
            # Get adaptive timeout
            timeout_seconds = adaptive_timeout_manager.get_adaptive_timeout("model_execution")
            
            # Execute with timeout
            return await timeout_handler.execute_with_timeout(
                self._call_model,
                timeout_seconds,
                "model_execution",
                "execution_agent",
                subtask.id,
                model.get_model_id(),
                subtask,
                model
            )
        
        # Execute through circuit breaker
        return await self.api_circuit_breaker.async_call(protected_call)
    
    async def _call_model(self, subtask: Subtask, model: AIModel) -> str:
        """Make the actual model API call."""
        return await model.generate_response(
            prompt=self._build_prompt(subtask),
            max_tokens=self._calculate_max_tokens(subtask),
            temperature=self._get_temperature(subtask)
        )
    
    def _create_failure_event(
        self, 
        error: Exception, 
        subtask: Subtask, 
        model_id: str, 
        attempt: int
    ) -> FailureEvent:
        """Create a failure event from an exception."""
        # Classify error type
        error_type_name = type(error).__name__
        
        if "timeout" in error_type_name.lower() or isinstance(error, TimeoutError):
            failure_type = FailureType.TIMEOUT
            severity = RiskLevel.MEDIUM
        elif "rate" in error_type_name.lower() or "limit" in error_type_name.lower():
            failure_type = FailureType.RATE_LIMIT
            severity = RiskLevel.LOW
        elif "auth" in error_type_name.lower() or "permission" in error_type_name.lower():
            failure_type = FailureType.AUTHENTICATION
            severity = RiskLevel.HIGH
        elif "network" in error_type_name.lower() or "connection" in error_type_name.lower():
            failure_type = FailureType.NETWORK_ERROR
            severity = RiskLevel.MEDIUM
        elif "quota" in error_type_name.lower() or "exceeded" in str(error).lower():
            failure_type = FailureType.QUOTA_EXCEEDED
            severity = RiskLevel.MEDIUM
        else:
            failure_type = FailureType.API_FAILURE
            severity = RiskLevel.MEDIUM
        
        return create_failure_event(
            failure_type=failure_type,
            component="execution_agent",
            error_message=str(error),
            subtask_id=subtask.id,
            model_id=model_id,
            severity=severity,
            context={
                "error_type": error_type_name,
                "attempt": attempt + 1,
                "subtask_content_length": len(subtask.content),
                "task_type": subtask.task_type.value if subtask.task_type else None
            }
        )
    
    async def _execute_with_fallback(
        self, 
        subtask: Subtask, 
        fallback_model_id: str, 
        original_start_time: float
    ) -> AgentResponse:
        """Execute subtask with fallback model."""
        logger.info(f"Attempting fallback execution with model {fallback_model_id}")
        
        # TODO: Implement real fallback execution (#113)
        # We need to resolve the fallback model instance from the ModelRegistry
        # and dynamically invoke the normal execution path (e.g., self.execute),
        # instead of returning a hard-coded degraded AgentResponse with 
        # a default SelfAssessment and RiskLevel.

        # This is a simplified implementation - in practice, you'd need to
        # get the actual fallback model instance from a registry
        # For now, return a degraded response
        execution_time = time.time() - original_start_time
        
        return AgentResponse(
            subtask_id=subtask.id,
            model_used=fallback_model_id,
            content="Fallback execution - limited functionality available",
            self_assessment=SelfAssessment(
                confidence_score=0.3,
                risk_level=RiskLevel.HIGH,
                model_used=fallback_model_id,
                execution_time=execution_time,
                assumptions=["Using fallback model with reduced capabilities"]
            ),
            timestamp=datetime.utcnow(),
            success=True,
            metadata={
                "fallback_execution": True,
                "original_failure": True,
                "degraded_mode": True
            }
        )
    
    def _create_skip_response(
        self, 
        subtask: Subtask, 
        model_id: str, 
        start_time: float
    ) -> AgentResponse:
        """Create response for skipped subtask."""
        execution_time = time.time() - start_time
        
        return AgentResponse(
            subtask_id=subtask.id,
            model_used=model_id,
            content="",
            self_assessment=SelfAssessment(
                confidence_score=0.0,
                risk_level=RiskLevel.LOW,
                model_used=model_id,
                execution_time=execution_time,
                assumptions=["Subtask skipped due to system overload"]
            ),
            timestamp=datetime.utcnow(),
            success=False,
            error_message="Subtask skipped due to load shedding",
            metadata={
                "skipped": True,
                "reason": "load_shedding"
            }
        )
    
    def _create_failure_response(
        self, 
        subtask: Subtask, 
        model_id: str, 
        error_message: str, 
        start_time: float
    ) -> AgentResponse:
        """Create failure response."""
        execution_time = time.time() - start_time
        
        return AgentResponse(
            subtask_id=subtask.id,
            model_used=model_id,
            content="",
            self_assessment=SelfAssessment(
                confidence_score=0.0,
                risk_level=RiskLevel.CRITICAL,
                model_used=model_id,
                execution_time=execution_time
            ),
            timestamp=datetime.utcnow(),
            success=False,
            error_message=f"Failed after {self.max_retries + 1} attempts: {error_message}",
            metadata={
                "attempts": self.max_retries + 1,
                "execution_time": execution_time,
                "final_error": error_message
            }
        )
    
    def _get_model_provider(self, model_id: str) -> str:
        """Get provider name from model ID for rate limiting."""
        model_id_lower = model_id.lower()
        
        if "gpt" in model_id_lower or "openai" in model_id_lower:
            return "openai"
        elif "claude" in model_id_lower or "anthropic" in model_id_lower:
            return "anthropic"
        elif "gemini" in model_id_lower or "google" in model_id_lower:
            return "google"
        else:
            return "default"
    
    def generate_self_assessment(self, response: str, subtask: Subtask) -> SelfAssessment:
        """Generate a self-assessment of the agent's performance.
        
        Args:
            response: The generated response content
            subtask: The subtask that was executed
            
        Returns:
            SelfAssessment: Structured self-assessment metadata
        """
        # Calculate confidence based on response quality indicators
        confidence_score = self._calculate_confidence(response, subtask)
        
        # Determine risk level based on task characteristics and confidence
        risk_level = self._assess_risk_level(confidence_score, subtask)
        
        # Extract assumptions from the response
        assumptions = self._extract_assumptions(response, subtask)
        
        # Estimate cost (simplified - would integrate with actual model pricing)
        estimated_cost = self._estimate_cost(response, subtask)
        
        # Estimate token usage (simplified approximation)
        token_usage = self._estimate_token_usage(response, subtask)
        
        return SelfAssessment(
            confidence_score=confidence_score,
            assumptions=assumptions,
            risk_level=risk_level,
            estimated_cost=estimated_cost,
            token_usage=token_usage,
            execution_time=0.0,  # Will be set by execute method
            model_used="",  # Will be set by execute method
            timestamp=datetime.utcnow()
        )
    
    def handle_model_failure(self, error: ModelError) -> FailureResponse:
        """Handle failures from the underlying AI model.
        
        Args:
            error: The model error that occurred
            
        Returns:
            FailureResponse: Information about the failure and suggested actions
        """
        # Categorize error types and determine retry strategy
        retry_suggested = False
        
        if error.error_type in ["TimeoutError", "ConnectionError", "HTTPError"]:
            # Network-related errors - suggest retry
            retry_suggested = True
            error_type = "network_error"
        elif error.error_type in ["RateLimitError", "QuotaExceededError"]:
            # Rate limiting - suggest retry with delay
            retry_suggested = True
            error_type = "rate_limit"
        elif error.error_type in ["AuthenticationError", "PermissionError"]:
            # Authentication issues - don't retry
            retry_suggested = False
            error_type = "authentication_error"
        elif error.error_type in ["ValidationError", "ValueError"]:
            # Input validation errors - don't retry
            retry_suggested = False
            error_type = "validation_error"
        else:
            # Unknown errors - try once more
            retry_suggested = True
            error_type = "unknown_error"
        
        logger.warning(
            f"Model failure handled: {error.model_id} - {error.error_type} - "
            f"Retry suggested: {retry_suggested}"
        )
        
        return FailureResponse(
            error_type=error_type,
            error_message=error.error_message,
            retry_suggested=retry_suggested
        )
    
    def _build_prompt(self, subtask: Subtask) -> str:
        """Build an appropriate prompt for the subtask.
        
        Args:
            subtask: The subtask to build a prompt for
            
        Returns:
            str: The constructed prompt
        """
        # Basic prompt construction - can be enhanced based on task type
        prompt_parts = []
        
        # Add task type specific instructions
        if subtask.task_type:
            task_instructions = self._get_task_type_instructions(subtask.task_type)
            if task_instructions:
                prompt_parts.append(task_instructions)
        
        # Add the main content
        prompt_parts.append(f"Task: {subtask.content}")
        
        # Add quality requirements
        if subtask.accuracy_requirement > 0.8:
            prompt_parts.append("Please provide a high-quality, accurate response.")
        
        # Add risk level considerations
        if subtask.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            prompt_parts.append("This is a high-risk task. Please be extra careful and thorough.")
        
        return "\n\n".join(prompt_parts)
    
    def _get_task_type_instructions(self, task_type) -> Optional[str]:
        """Get specific instructions for different task types.
        
        Args:
            task_type: The type of task
            
        Returns:
            Optional[str]: Task-specific instructions or None
        """
        from ..core.models import TaskType
        
        instructions = {
            TaskType.REASONING: "Please provide comprehensive step-by-step logical reasoning with detailed explanations.",
            TaskType.RESEARCH: "Please provide thorough, well-researched information with detailed explanations and sources when possible.",
            TaskType.CODE_GENERATION: "Please provide clean, well-commented code with detailed explanations and examples.",
            TaskType.DEBUGGING: "Please analyze the issue systematically and provide a detailed solution with explanations.",
            TaskType.CREATIVE_OUTPUT: "Please be creative and provide detailed, engaging content while maintaining quality and coherence.",
            TaskType.FACT_CHECKING: "Please verify information carefully, provide detailed analysis, and cite sources.",
            TaskType.VERIFICATION: "Please thoroughly check all claims and provide detailed evidence and explanations."
        }
        
        return instructions.get(task_type)
    
    def _calculate_max_tokens(self, subtask: Subtask) -> int:
        """Calculate appropriate max tokens for the subtask.
        
        Args:
            subtask: The subtask to calculate tokens for
            
        Returns:
            int: Maximum tokens to request
        """
        # Base token count - increased for more detailed responses
        base_tokens = 2000
        
        # Adjust based on task complexity (inferred from content length)
        content_length = len(subtask.content)
        if content_length > 1000:
            base_tokens = 4000  # Very detailed for complex queries
        elif content_length > 500:
            base_tokens = 3000  # Detailed for medium queries
        elif content_length > 200:
            base_tokens = 2500  # Good detail for normal queries
        
        # Adjust based on accuracy requirements
        if subtask.accuracy_requirement > 0.9:
            base_tokens = int(base_tokens * 1.5)
        
        return min(base_tokens, 4000)  # Cap at reasonable limit
    
    def _get_temperature(self, subtask: Subtask) -> float:
        """Get appropriate temperature setting for the subtask.
        
        Args:
            subtask: The subtask to get temperature for
            
        Returns:
            float: Temperature value between 0.0 and 1.0
        """
        from ..core.models import TaskType
        
        # Default temperature
        temperature = 0.7
        
        # Adjust based on task type
        if subtask.task_type in [TaskType.CREATIVE_OUTPUT]:
            temperature = 0.9
        elif subtask.task_type in [TaskType.FACT_CHECKING, TaskType.VERIFICATION, TaskType.DEBUGGING]:
            temperature = 0.3
        elif subtask.task_type in [TaskType.REASONING, TaskType.CODE_GENERATION]:
            temperature = 0.5
        
        # Adjust based on accuracy requirements
        if subtask.accuracy_requirement > 0.9:
            temperature = max(0.1, temperature - 0.2)
        
        return temperature
    
    def _calculate_confidence(self, response: str, subtask: Subtask) -> float:
        """Calculate confidence score based on response characteristics.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            
        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        confidence = 0.5  # Base confidence
        
        # Adjust based on response length (too short or too long may indicate issues)
        response_length = len(response.strip())
        if 50 <= response_length <= 2000:
            confidence += 0.2
        elif response_length < 10:
            confidence -= 0.3
        
        # Check for uncertainty indicators
        uncertainty_phrases = [
            "i'm not sure", "i think", "maybe", "possibly", "might be",
            "i don't know", "unclear", "uncertain", "not confident"
        ]
        
        response_lower = response.lower()
        uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in response_lower)
        confidence -= min(0.3, uncertainty_count * 0.1)
        
        # Check for confidence indicators
        confidence_phrases = [
            "definitely", "certainly", "clearly", "obviously", "without doubt",
            "confirmed", "verified", "established"
        ]
        
        confidence_count = sum(1 for phrase in confidence_phrases if phrase in response_lower)
        confidence += min(0.2, confidence_count * 0.05)
        
        # Ensure confidence is within bounds
        return max(0.0, min(1.0, confidence))
    
    def _assess_risk_level(self, confidence_score: float, subtask: Subtask) -> RiskLevel:
        """Assess risk level based on confidence and task characteristics.
        
        Args:
            confidence_score: The calculated confidence score
            subtask: The subtask being assessed
            
        Returns:
            RiskLevel: The assessed risk level
        """
        # Start with subtask's inherent risk level
        base_risk = subtask.risk_level
        
        # Adjust based on confidence
        if confidence_score < 0.3:
            if base_risk == RiskLevel.LOW:
                return RiskLevel.MEDIUM
            elif base_risk == RiskLevel.MEDIUM:
                return RiskLevel.HIGH
            else:
                return RiskLevel.CRITICAL
        elif confidence_score < 0.6:
            if base_risk == RiskLevel.LOW:
                return RiskLevel.LOW
            else:
                return RiskLevel.MEDIUM
        
        # High confidence - maintain or reduce risk
        return base_risk
    
    def _extract_assumptions(self, response: str, subtask: Subtask) -> list[str]:
        """Extract assumptions made in the response.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            
        Returns:
            List[str]: List of identified assumptions
        """
        assumptions = []
        
        # Look for assumption indicators
        assumption_patterns = [
            "assuming", "given that", "if we assume", "presuming",
            "taking for granted", "based on the assumption"
        ]
        
        response_lower = response.lower()
        sentences = response.split('.')
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            for pattern in assumption_patterns:
                if pattern in sentence_lower:
                    # Clean up the assumption text
                    assumption = sentence.strip()
                    if assumption and len(assumption) > 10:
                        assumptions.append(assumption)
                    break
        
        # Add default assumptions based on task type
        if subtask.task_type:
            default_assumptions = self._get_default_assumptions(subtask.task_type)
            assumptions.extend(default_assumptions)
        
        return assumptions[:5]  # Limit to top 5 assumptions
    
    def _get_default_assumptions(self, task_type) -> list[str]:
        """Get default assumptions for different task types.
        
        Args:
            task_type: The type of task
            
        Returns:
            List[str]: Default assumptions for the task type
        """
        from ..core.models import TaskType
        
        defaults = {
            TaskType.RESEARCH: ["Information sources are current and reliable"],
            TaskType.CODE_GENERATION: ["Standard coding practices and conventions apply"],
            TaskType.DEBUGGING: ["Error description accurately reflects the actual issue"],
            TaskType.FACT_CHECKING: ["Primary sources are accessible and verifiable"],
            TaskType.REASONING: ["Logical premises are sound and complete"]
        }
        
        return defaults.get(task_type, [])
    
    def _estimate_cost(self, response: str, subtask: Subtask) -> float:
        """Estimate the cost of generating the response.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            
        Returns:
            float: Estimated cost in USD
        """
        # Simplified cost estimation - would integrate with actual model pricing
        # Assume average cost per token
        estimated_tokens = self._estimate_token_usage(response, subtask)
        cost_per_token = 0.00002  # Example: $0.00002 per token
        
        return estimated_tokens * cost_per_token
    
    def _estimate_token_usage(self, response: str, subtask: Subtask) -> int:
        """Estimate token usage for the request and response.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            
        Returns:
            int: Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters for English text
        prompt_chars = len(self._build_prompt(subtask))
        response_chars = len(response)
        
        total_chars = prompt_chars + response_chars
        estimated_tokens = total_chars // 4
        
        return max(1, estimated_tokens)  # Minimum 1 token