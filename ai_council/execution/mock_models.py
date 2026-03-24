"""Mock AI model implementations for testing and development."""

import time
import random
import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum

from ..core.interfaces import AIModel, ModelError


class MockModelBehavior(Enum):
    """Behavior modes for mock models."""
    NORMAL = "normal"
    SLOW = "slow"
    FAST = "fast"
    RANDOM_FAILURE = "random_failure"
    ALWAYS_FAIL = "always_fail"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_ERROR = "authentication_error"
    VALIDATION_ERROR = "validation_error"


class MockAIModel(AIModel):
    """Mock AI model implementation for testing purposes."""
    
    def __init__(
        self,
        model_id: str,
        behavior: MockModelBehavior = MockModelBehavior.NORMAL,
        response_template: Optional[str] = None,
        failure_rate: float = 0.0,
        response_delay: float = 0.1,
        max_tokens: int = 1000
    ):
        """Initialize mock AI model.
        
        Args:
            model_id: Unique identifier for the model
            behavior: Behavior mode for the model
            response_template: Template for generating responses
            failure_rate: Probability of failure (0.0 to 1.0)
            response_delay: Delay in seconds before responding
            max_tokens: Maximum tokens the model can generate
        """
        self.model_id = model_id
        self.behavior = behavior
        self.response_template = response_template or "Mock response to: {prompt}"
        self.failure_rate = max(0.0, min(1.0, failure_rate))
        self.response_delay = max(0.0, response_delay)
        self.max_tokens = max_tokens
        
        # Track usage statistics
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_response_time = 0.0
        
        # Rate limiting simulation
        self._last_request_time = 0.0
        self._request_count_in_window = 0
        self._rate_limit_window = 60.0  # 1 minute window
        self._max_requests_per_window = 100
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the mock AI model.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters (max_tokens, temperature, etc.)
            
        Returns:
            str: The generated response
            
        Raises:
            ModelError: When the model fails based on its behavior configuration
        """
        start_time = time.time()
        self.request_count += 1
        
        try:
            # Check rate limiting
            self._check_rate_limit()
            
            # Apply behavior-specific logic
            await self._apply_behavior_effects(prompt, **kwargs)
            
            # Simulate processing delay
            if self.response_delay > 0:
                await asyncio.sleep(self.response_delay)
            
            # Generate response based on template and parameters
            response = self._generate_mock_response(prompt, **kwargs)
            
            # Track success
            self.success_count += 1
            self.total_response_time += time.time() - start_time
            
            return response
            
        except Exception as e:
            self.failure_count += 1
            self.total_response_time += time.time() - start_time
            raise e
    
    def get_model_id(self) -> str:
        """Get the unique identifier for this model.
        
        Returns:
            str: Model identifier
        """
        return self.model_id
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for the mock model.
        
        Returns:
            Dict[str, Any]: Statistics including request count, success rate, etc.
        """
        success_rate = self.success_count / self.request_count if self.request_count > 0 else 0.0
        avg_response_time = self.total_response_time / self.request_count if self.request_count > 0 else 0.0
        
        return {
            "model_id": self.model_id,
            "behavior": self.behavior.value,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "total_response_time": self.total_response_time
        }
    
    def reset_statistics(self) -> None:
        """Reset usage statistics."""
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_response_time = 0.0
        self._request_count_in_window = 0
    
    def _check_rate_limit(self) -> None:
        """Check if request should be rate limited."""
        current_time = time.time()
        
        # Reset window if needed
        if current_time - self._last_request_time > self._rate_limit_window:
            self._request_count_in_window = 0
        
        self._request_count_in_window += 1
        self._last_request_time = current_time
        
        # Check if rate limited
        if (self.behavior == MockModelBehavior.RATE_LIMITED or 
            self._request_count_in_window > self._max_requests_per_window):
            raise ModelError(
                model_id=self.model_id,
                error_message="Rate limit exceeded. Please try again later.",
                error_type="RateLimitError"
            )
    
    async def _apply_behavior_effects(self, prompt: str, **kwargs) -> None:
        """Apply behavior-specific effects that may cause failures.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters
            
        Raises:
            ModelError: When behavior dictates a failure
        """
        if self.behavior == MockModelBehavior.ALWAYS_FAIL:
            raise ModelError(
                model_id=self.model_id,
                error_message="Mock model configured to always fail",
                error_type="MockFailure"
            )
        
        elif self.behavior == MockModelBehavior.RANDOM_FAILURE:
            if random.random() < self.failure_rate:
                failure_types = [
                    ("NetworkError", "Simulated network failure"),
                    ("TimeoutError", "Request timed out"),
                    ("ValidationError", "Invalid input parameters"),
                    ("InternalError", "Internal model error")
                ]
                error_type, error_message = random.choice(failure_types)
                raise ModelError(
                    model_id=self.model_id,
                    error_message=error_message,
                    error_type=error_type
                )
        
        elif self.behavior == MockModelBehavior.TIMEOUT:
            raise ModelError(
                model_id=self.model_id,
                error_message="Request timed out after 30 seconds",
                error_type="TimeoutError"
            )
        
        elif self.behavior == MockModelBehavior.AUTHENTICATION_ERROR:
            raise ModelError(
                model_id=self.model_id,
                error_message="Invalid API key or authentication failed",
                error_type="AuthenticationError"
            )
        
        elif self.behavior == MockModelBehavior.VALIDATION_ERROR:
            if len(prompt) > 1000:  # Simulate input validation
                raise ModelError(
                    model_id=self.model_id,
                    error_message="Prompt exceeds maximum length of 1000 characters",
                    error_type="ValidationError"
                )
        
        elif self.behavior == MockModelBehavior.SLOW:
            # Add extra delay for slow behavior
            await asyncio.sleep(2.0)
        
        elif self.behavior == MockModelBehavior.FAST:
            # Reduce delay for fast behavior
            pass  # No additional delay
    
    def _generate_mock_response(self, prompt: str, **kwargs) -> str:
        """Generate a mock response based on the prompt and parameters.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional parameters
            
        Returns:
            str: Generated mock response
        """
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        temperature = kwargs.get('temperature', 0.7)
        
        # Generate response based on template
        base_response = self.response_template.format(prompt=prompt[:100])
        
        # Add some variation based on temperature
        if temperature > 0.8:
            variations = [
                " This is a creative response with high temperature.",
                " Here's an imaginative take on your request.",
                " Let me provide a creative and varied response."
            ]
            base_response += random.choice(variations)
        elif temperature < 0.3:
            variations = [
                " This is a precise, low-temperature response.",
                " Here's a focused and deterministic answer.",
                " This response prioritizes accuracy and consistency."
            ]
            base_response += random.choice(variations)
        
        # Add task-specific content based on prompt keywords
        response_parts = [base_response]
        
        prompt_lower = prompt.lower()
        if "code" in prompt_lower or "programming" in prompt_lower:
            response_parts.append("\n\n```python\n# Mock code example\ndef example_function():\n    return 'mock implementation'\n```")
        
        if "analyze" in prompt_lower or "analysis" in prompt_lower:
            response_parts.append("\n\nAnalysis: This is a mock analytical response with structured reasoning.")
        
        if "research" in prompt_lower:
            response_parts.append("\n\nResearch findings: Mock research data and citations would appear here.")
        
        if "debug" in prompt_lower or "error" in prompt_lower:
            response_parts.append("\n\nDebugging steps:\n1. Mock step one\n2. Mock step two\n3. Mock resolution")
        
        # Combine response parts
        full_response = "".join(response_parts)
        
        # Truncate to max_tokens (rough approximation)
        if len(full_response) > max_tokens * 4:  # Assume ~4 chars per token
            full_response = full_response[:max_tokens * 4] + "..."
        
        return full_response


class MockModelFactory:
    """Factory for creating various types of mock models."""
    
    @staticmethod
    def create_reliable_model(model_id: str = "reliable-mock") -> MockAIModel:
        """Create a reliable mock model that rarely fails.
        
        Args:
            model_id: Identifier for the model
            
        Returns:
            MockAIModel: Configured reliable model
        """
        return MockAIModel(
            model_id=model_id,
            behavior=MockModelBehavior.NORMAL,
            failure_rate=0.01,  # 1% failure rate
            response_delay=0.1
        )
    
    @staticmethod
    def create_unreliable_model(model_id: str = "unreliable-mock") -> MockAIModel:
        """Create an unreliable mock model that fails frequently.
        
        Args:
            model_id: Identifier for the model
            
        Returns:
            MockAIModel: Configured unreliable model
        """
        return MockAIModel(
            model_id=model_id,
            behavior=MockModelBehavior.RANDOM_FAILURE,
            failure_rate=0.3,  # 30% failure rate
            response_delay=0.2
        )
    
    @staticmethod
    def create_slow_model(model_id: str = "slow-mock") -> MockAIModel:
        """Create a slow mock model with high latency.
        
        Args:
            model_id: Identifier for the model
            
        Returns:
            MockAIModel: Configured slow model
        """
        return MockAIModel(
            model_id=model_id,
            behavior=MockModelBehavior.SLOW,
            failure_rate=0.05,  # 5% failure rate
            response_delay=1.0  # 1 second base delay + 2 seconds from behavior
        )
    
    @staticmethod
    def create_fast_model(model_id: str = "fast-mock") -> MockAIModel:
        """Create a fast mock model with low latency.
        
        Args:
            model_id: Identifier for the model
            
        Returns:
            MockAIModel: Configured fast model
        """
        return MockAIModel(
            model_id=model_id,
            behavior=MockModelBehavior.FAST,
            failure_rate=0.02,  # 2% failure rate
            response_delay=0.05  # Very fast response
        )
    
    @staticmethod
    def create_failing_model(
        model_id: str = "failing-mock",
        failure_type: MockModelBehavior = MockModelBehavior.ALWAYS_FAIL
    ) -> MockAIModel:
        """Create a mock model that demonstrates specific failure modes.
        
        Args:
            model_id: Identifier for the model
            failure_type: Type of failure to simulate
            
        Returns:
            MockAIModel: Configured failing model
        """
        return MockAIModel(
            model_id=model_id,
            behavior=failure_type,
            failure_rate=1.0,  # Always fail for specific failure types
            response_delay=0.1
        )
    
    @staticmethod
    def create_specialized_model(
        model_id: str,
        task_specialty: str,
        quality_level: str = "high"
    ) -> MockAIModel:
        """Create a mock model specialized for specific tasks.
        
        Args:
            model_id: Identifier for the model
            task_specialty: The task type this model specializes in
            quality_level: Quality level (high, medium, low)
            
        Returns:
            MockAIModel: Configured specialized model
        """
        # Customize response template based on specialty
        templates = {
            "reasoning": "Logical analysis of: {prompt}\n\nStep-by-step reasoning:\n1. Mock premise\n2. Mock inference\n3. Mock conclusion",
            "code": "Code solution for: {prompt}\n\n```python\n# Mock implementation\nclass MockSolution:\n    def solve(self):\n        return 'mock result'\n```",
            "research": "Research findings for: {prompt}\n\nSources:\n- Mock Source 1\n- Mock Source 2\n\nFindings: Mock research data and analysis.",
            "creative": "Creative response to: {prompt}\n\nImagine a world where mock creativity flows freely...",
            "debug": "Debug analysis for: {prompt}\n\nIssue identified: Mock error\nSolution: Mock fix\nPrevention: Mock best practices"
        }
        
        template = templates.get(task_specialty, "Specialized response to: {prompt}")
        
        # Adjust failure rate based on quality level
        failure_rates = {
            "high": 0.01,
            "medium": 0.05,
            "low": 0.15
        }
        
        failure_rate = failure_rates.get(quality_level, 0.05)
        
        return MockAIModel(
            model_id=model_id,
            behavior=MockModelBehavior.NORMAL,
            response_template=template,
            failure_rate=failure_rate,
            response_delay=0.1
        )
    
    @staticmethod
    def create_model_suite() -> Dict[str, MockAIModel]:
        """Create a complete suite of mock models for comprehensive testing.
        
        Returns:
            Dict[str, MockAIModel]: Dictionary of model_id -> MockAIModel
        """
        return {
            "reliable": MockModelFactory.create_reliable_model(),
            "unreliable": MockModelFactory.create_unreliable_model(),
            "slow": MockModelFactory.create_slow_model(),
            "fast": MockModelFactory.create_fast_model(),
            "timeout": MockModelFactory.create_failing_model("timeout-mock", MockModelBehavior.TIMEOUT),
            "rate_limited": MockModelFactory.create_failing_model("rate-limited-mock", MockModelBehavior.RATE_LIMITED),
            "auth_error": MockModelFactory.create_failing_model("auth-error-mock", MockModelBehavior.AUTHENTICATION_ERROR),
            "validation_error": MockModelFactory.create_failing_model("validation-error-mock", MockModelBehavior.VALIDATION_ERROR),
            "reasoning_specialist": MockModelFactory.create_specialized_model("reasoning-mock", "reasoning", "high"),
            "code_specialist": MockModelFactory.create_specialized_model("code-mock", "code", "high"),
            "research_specialist": MockModelFactory.create_specialized_model("research-mock", "research", "medium"),
            "creative_specialist": MockModelFactory.create_specialized_model("creative-mock", "creative", "medium"),
            "debug_specialist": MockModelFactory.create_specialized_model("debug-mock", "debug", "high")
        }


# Convenience functions for common testing scenarios
def create_test_models() -> List[MockAIModel]:
    """Create a list of mock models for basic testing.
    
    Returns:
        List[MockAIModel]: List of configured mock models
    """
    return [
        MockModelFactory.create_reliable_model("test-model-1"),
        MockModelFactory.create_reliable_model("test-model-2"),
        MockModelFactory.create_unreliable_model("test-model-unreliable")
    ]


def create_failure_test_models() -> List[MockAIModel]:
    """Create a list of mock models for failure testing.
    
    Returns:
        List[MockAIModel]: List of models with different failure modes
    """
    return [
        MockModelFactory.create_failing_model("timeout-test", MockModelBehavior.TIMEOUT),
        MockModelFactory.create_failing_model("rate-limit-test", MockModelBehavior.RATE_LIMITED),
        MockModelFactory.create_failing_model("auth-test", MockModelBehavior.AUTHENTICATION_ERROR),
        MockModelFactory.create_failing_model("validation-test", MockModelBehavior.VALIDATION_ERROR),
        MockModelFactory.create_unreliable_model("random-fail-test")
    ]