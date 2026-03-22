"""Execution agent implementation for AI Council."""
import tiktoken
import time
import re
from ai_council.core.logger import get_logger
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.interfaces import ExecutionAgent, AIModel, ModelError, FailureResponse, ModelRegistry
from ..core.models import Subtask, AgentResponse, SelfAssessment, RiskLevel
from ..core.failure_handling import (
    FailureEvent, FailureType, resilience_manager, create_failure_event
)
from ..core.timeout_handler import (
    timeout_handler, adaptive_timeout_manager, rate_limit_manager,
    with_adaptive_timeout, with_rate_limit, TimeoutError
)


logger = get_logger(__name__)


class BaseExecutionAgent(ExecutionAgent):
    """Base implementation of ExecutionAgent with comprehensive failure handling."""
    
    def __init__(self, model_registry: Optional[ModelRegistry] = None, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize the execution agent.
        
        Args:
            model_registry: Registry for resolving AI models
            max_retries: Maximum number of retry attempts for failed executions
            retry_delay: Base delay in seconds between retry attempts
        """
        self.model_registry = model_registry
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._execution_history: Dict[str, Any] = {}
        
        # Initialize circuit breakers for different failure types
        from ..core.failure_handling import CircuitBreakerConfig

        self.encoding = tiktoken.encoding_for_model("gpt-4")

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

    def _count_tokens(self, text: str) -> int:
        """Count tokens accurately using tiktoken."""
        return len(self.encoding.encode(text))
    
    async def execute(self, subtask: Subtask, model: AIModel, depth: int = 0) -> AgentResponse:
        """Execute a subtask using the specified AI model with comprehensive failure handling.
        
        Args:
            subtask: The subtask to execute
            model: The AI model to use for execution
            depth: Current fallback depth
            
        Returns:
            AgentResponse: The response including content and self-assessment
        """
        start_time = time.time()
        model_id = model.get_model_id()
        
        logger.info("Executing subtask", extra={"subtask_id": subtask.id, "model_id": model_id})
        
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
            logger.warning("Model", extra={"model_id": model_id})
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
                        logger.info("Rate limit hit", extra={"provider": provider, "wait_time": wait_time})
                        await asyncio.sleep(wait_time)
                    else:
                        break
                
                # Execute with circuit breaker and timeout
                response_content = await self._execute_with_protection(subtask, model)
                
                # Generate self-assessment
                self_assessment = await self.generate_self_assessment(response_content, subtask, model_id)
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
                
                logger.info("Successfully executed subtask", extra={"subtask_id": subtask.id, "attempt": attempt + 1})
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
                    fallback_models = []
                    if recovery_action.metadata and "fallback_models" in recovery_action.metadata:
                        fallback_models = recovery_action.metadata["fallback_models"]
                    elif recovery_action.fallback_model:
                        fallback_models = [recovery_action.fallback_model]
                        
                    if fallback_models:
                        logger.info("Iterating over fallback chain", extra={
                            "subtask_id": subtask.id, 
                            "original_model": model_id,
                            "fallback_chain": fallback_models
                        })
                        fallback_errors = []
                        for fallback_model_id in fallback_models:
                            # Try fallback model
                            response = await self._execute_with_fallback(
                                subtask, fallback_model_id, start_time, depth
                            )
                            if response.success:
                                # Log transition
                                logger.info("Fallback execution successful", extra={
                                    "subtask_id": subtask.id,
                                    "original_model": model_id,
                                    "successful_fallback": fallback_model_id
                                })
                                # Attach fallback metadata
                                if response.metadata is None:
                                    response.metadata = {}
                                response.metadata["fallback_attempts"] = response.metadata.get("fallback_attempts", 0) + 1
                                response.metadata["fallback_failures"] = fallback_errors
                                return response
                            
                            # Collect error and try the next one
                            fallback_errors.append({
                                "model_id": fallback_model_id,
                                "error": response.error_message
                            })
                            logger.warning(f"Fallback model {fallback_model_id} failed: {response.error_message}")
                            
                        # If all fallbacks failed
                        return self._create_failure_response(
                            subtask, model_id, f"All fallback models failed. Last error: {fallback_errors[-1]['error'] if fallback_errors else str(last_error)}", start_time
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
                    logger.info("Waiting", extra={"delay_seconds": round(delay, 1)})
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
        elif "content" in error_type_name.lower() or "filter" in str(error).lower():
            failure_type = FailureType.VALIDATION_ERROR
            severity = RiskLevel.MEDIUM
        elif "provider" in error_type_name.lower() or "providererror" in error_type_name.lower():
            failure_type = FailureType.API_FAILURE
            severity = RiskLevel.HIGH
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
        original_start_time: float,
        depth: int = 0
    ) -> AgentResponse:
        """Execute subtask with fallback model."""
        MAX_FALLBACK_DEPTH = 3
        
        if depth >= MAX_FALLBACK_DEPTH:
            logger.error(
                "Maximum fallback depth reached", 
                extra={"subtask_id": subtask.id, "depth": depth}
            )
            return self._create_failure_response(
                subtask, fallback_model_id, f"Maximum fallback depth of {MAX_FALLBACK_DEPTH} reached", original_start_time
            )

        logger.info(
            f"Attempting fallback execution (depth {depth + 1})", 
            extra={
                "subtask_id": subtask.id,
                "fallback_model_id": fallback_model_id,
                "depth": depth + 1
            }
        )
        
        if not self.model_registry:
            logger.error("Model registry not available for fallback resolution")
            return self._create_failure_response(
                subtask, fallback_model_id, "Model registry not available", original_start_time
            )

        fallback_model = self.model_registry.get_model_by_id(fallback_model_id)
        if not fallback_model:
            logger.error("Fallback model not found in registry", extra={"model_id": fallback_model_id})
            return self._create_failure_response(
                subtask, fallback_model_id, f"Fallback model {fallback_model_id} not found in registry", original_start_time
            )

        # Recursively call execute with the fallback model
        response = await self.execute(subtask, fallback_model, depth=depth + 1)
        
        # Update metadata to track fallback chain
        if response.metadata is None:
            response.metadata = {}
        
        # Only set if not already present (deepest call sets it first)
        if "fallback_depth" not in response.metadata:
            response.metadata["fallback_depth"] = depth + 1
        
        if "is_fallback" not in response.metadata:
            response.metadata["is_fallback"] = True
            
        if "original_start_time" not in response.metadata:
            response.metadata["original_start_time"] = original_start_time

        return response
    
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
    
    async def generate_self_assessment(self, response: str, subtask: Subtask, model_id: str) -> SelfAssessment:
        """Generate a self-assessment of the agent's performance.
        
        Args:
            response: The generated response content
            subtask: The subtask that was executed
            model_id: Identifier of the LLM model used, required for cost estimation
            
        Returns:
            SelfAssessment: Structured self-assessment metadata
        """
        # Calculate confidence based on response quality indicators
        confidence_score = self._calculate_confidence(response, subtask)
        
        # Determine risk level based on task characteristics and confidence
        risk_level = self._assess_risk_level(confidence_score, subtask)
        
        # Extract assumptions from the response
        assumptions = self._extract_assumptions(response, subtask)
        
        # Estimate token usage (split into input and output)
        token_usage_dict = self._estimate_token_usage(response, subtask)
        token_usage = token_usage_dict["total"]
        
        # Estimate cost based on model-specific pricing
        estimated_cost = self._estimate_cost(response, subtask, model_id)
        
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
            
        response_lower = response.lower()
        
        # Use regex word boundaries and strictly self-referential phrases
        uncertainty_patterns = [
            r"\bi'm not sure\b", r"\bi am not sure\b", 
            r"\bi think\s+(?:but|though|however|but i'm not sure|though i'm not sure)\b", 
            r"\bi don't know\b", r"\bi do not know\b",
            r"\bit is unclear to me\b", r"\bi am uncertain\b", r"\bi'm uncertain\b",
            r"\bi am not confident\b", r"\bi'm not confident\b"
        ]
        
        uncertainty_count = sum(len(re.findall(pattern, response_lower)) for pattern in uncertainty_patterns)
        confidence -= min(0.3, uncertainty_count * 0.1)
        
        # Apply word boundaries to confidence indicators
        confidence_patterns = [
            r"\bdefinitely\b", r"\bcertainly\b", r"\bclearly\b", r"\bobviously\b", 
            r"\bwithout doubt\b", r"\bwithout a doubt\b", r"\bconfirmed\b", 
            r"\bverified\b", r"\bestablished\b"
        ]
        
        confidence_count = sum(len(re.findall(pattern, response_lower)) for pattern in confidence_patterns)
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
        
        # Use regex word boundaries to prevent partial matches
        assumption_patterns = [
            r"\bassuming\b", r"\bgiven that\b", r"\bif we assume\b", 
            r"\bpresuming\b", r"\btaking for granted\b", r"\bbased on the assumption\b"
        ]
        
        # Split by punctuation or newlines, but use negative lookbehinds to protect 
        split_pattern = r'(?<!\d)(?<!\bDr)(?<!\bMr)(?<!\bMs)(?<!\bvs)(?<!\be\.g)(?<!\bi\.e)(?<!\bMrs)(?<!\betc)[.!?]+(?:\s+|\n+)|\n+'
        sentences = re.split(split_pattern, response)
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            for pattern in assumption_patterns:
                if re.search(pattern, sentence_lower):
                    # Clean up the assumption text
                    assumption = sentence.strip()
                    if assumption and len(assumption) > 15:
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
    
    def _estimate_cost(self, response: str, subtask: Subtask, model_id: str) -> float:
        """Estimate the cost of generating the response based on model pricing.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            model_id: The ID of the model used
            
        Returns:
            float: Estimated cost in USD
        """
        token_usage = self._estimate_token_usage(response, subtask)
        
        # Use model registry to get accurate pricing
        if self.model_registry:
            try:
                cost_profile = self.model_registry.get_model_cost_profile(model_id)
                input_cost = token_usage["input"] * cost_profile.cost_per_input_token
                output_cost = token_usage["output"] * cost_profile.cost_per_output_token
                
                total_cost = input_cost + output_cost
                return max(cost_profile.minimum_cost, total_cost)
            except (KeyError, AttributeError):
                # Fallback to a default if model not found or registry fails
                pass
        
        # Fallback to default pricing if registry is unavailable or model not found
        cost_per_token = 0.00002
        return token_usage["total"] * cost_per_token
    
    def _estimate_token_usage(self, response: str, subtask: Subtask) -> Dict[str, int]:
        """Estimate token usage for the request and response.
        
        Args:
            response: The generated response
            subtask: The subtask that was executed
            
        Returns:
            Dict[str, int]: Estimated token counts for input and output
        """

        prompt_text = self._build_prompt(subtask)
        input_tokens = max(1, self._count_tokens(prompt_text))
        output_tokens = max(1, self._count_tokens(response))
        
        return {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens
        }