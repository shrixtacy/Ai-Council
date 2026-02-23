"""
Rate Limiting Usage Examples

This file demonstrates how to use AI Council's rate limiting features
in various scenarios.
"""

import time
from ai_council.core.timeout_handler import rate_limit_manager, with_rate_limit
from ai_council.core.models import ExecutionMode

# Example 1: Basic Rate Limiting
def basic_rate_limiting():
    """Demonstrate basic rate limiting setup and usage."""
    
    # Configure rate limits for different APIs
    rate_limit_manager.set_rate_limit("openai_gpt4", 60, burst_limit=10)
    rate_limit_manager.set_rate_limit("anthropic_claude", 50, burst_limit=8)
    rate_limit_manager.set_rate_limit("google_gemini", 100, burst_limit=20)
    
    # Check rate limit before making API call
    resource = "openai_gpt4"
    allowed, wait_time = rate_limit_manager.check_rate_limit(resource)
    
    if not allowed:
        print(f"Rate limit exceeded for {resource}, waiting {wait_time:.1f}s")
        time.sleep(wait_time)
    
    # Make your API call here
    print(f"Making API call to {resource}")
    
    # Get current status
    status = rate_limit_manager.get_rate_limit_status(resource)
    print(f"Rate limit status: {status}")


# Example 2: Using Rate Limit Decorator
@with_rate_limit("openai_gpt4", "model_executor")
def call_openai_api(prompt: str) -> str:
    """Example function with rate limiting decorator."""
    # This function will automatically check rate limits
    # and wait if necessary before executing
    
    # Simulate API call
    time.sleep(0.5)  # Simulate network latency
    
    return f"Response to: {prompt}"


# Example 3: Handling External Rate Limits
def handle_external_rate_limits():
    """Demonstrate handling rate limits from external services."""
    
    try:
        # Simulate external API call that might be rate limited
        response = make_external_api_call()
        return response
        
    except Exception as e:
        if "rate limit" in str(e).lower():
            # Record the rate limit hit
            reset_time = extract_reset_time_from_error(e)
            rate_limit_manager.record_rate_limit_hit(
                resource="external_api",
                reset_time=reset_time,
                component="api_client"
            )
            
            # Wait and retry
            wait_time = reset_time - time.time() if reset_time else 60
            print(f"External rate limit hit, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            
            # Retry the call
            return make_external_api_call()
        else:
            raise


# Example 4: Rate Limiting with Different Execution Modes
def rate_limit_by_execution_mode():
    """Configure different rate limits based on execution mode."""
    
    mode_limits = {
        ExecutionMode.FAST: {"requests_per_minute": 120, "burst": 20},
        ExecutionMode.BALANCED: {"requests_per_minute": 60, "burst": 10},
        ExecutionMode.BEST_QUALITY: {"requests_per_minute": 30, "burst": 5}
    }
    
    for mode, limits in mode_limits.items():
        resource = f"ai_council_{mode.value}"
        rate_limit_manager.set_rate_limit(
            resource=resource,
            requests_per_minute=limits["requests_per_minute"],
            burst_limit=limits["burst"]
        )
        print(f"Set rate limit for {mode}: {limits['requests_per_minute']}/min")


# Example 5: Monitoring Rate Limit Usage
def monitor_rate_limits():
    """Monitor and report rate limit usage."""
    
    resources = ["openai_gpt4", "anthropic_claude", "google_gemini"]
    
    print("Rate Limit Status Report:")
    print("-" * 50)
    
    for resource in resources:
        status = rate_limit_manager.get_rate_limit_status(resource)
        if status["configured"]:
            print(f"{resource}:")
            print(f"  Limit: {status['requests_per_minute']}/min")
            print(f"  Used: {status['current_count']}")
            print(f"  Reset in: {status['time_until_reset']:.1f}s")
        else:
            print(f"{resource}: Not configured")


# Example 6: Custom Rate Limit Strategy
class CustomRateLimiter:
    """Custom rate limiter with advanced features."""
    
    def __init__(self):
        self.request_times = {}
        self.limits = {}
    
    def set_limit(self, resource: str, requests_per_minute: int):
        """Set custom rate limit for a resource."""
        self.limits[resource] = requests_per_minute
        self.request_times[resource] = []
    
    def check_limit(self, resource: str) -> tuple[bool, float]:
        """Check if request is allowed with custom logic."""
        if resource not in self.limits:
            return True, 0.0
        
        current_time = time.time()
        window_start = current_time - 60.0  # 1 minute window
        
        # Remove old requests
        self.request_times[resource] = [
            req_time for req_time in self.request_times[resource]
            if req_time > window_start
        ]
        
        # Check if under limit
        if len(self.request_times[resource]) < self.limits[resource]:
            self.request_times[resource].append(current_time)
            return True, 0.0
        
        # Calculate wait time
        oldest_request = min(self.request_times[resource])
        wait_time = oldest_request + 60.0 - current_time
        return False, max(0.0, wait_time)


# Example 7: Rate Limiting in Production
def production_rate_limiting():
    """Production-ready rate limiting configuration."""
    
    # Configure conservative limits for production
    production_limits = {
        "openai_gpt4": {"rpm": 40, "burst": 8},  # Conservative
        "anthropic_claude": {"rpm": 30, "burst": 6},
        "google_gemini": {"rpm": 80, "burst": 16},
        "internal_api": {"rpm": 200, "burst": 40}
    }
    
    for resource, config in production_limits.items():
        rate_limit_manager.set_rate_limit(
            resource=resource,
            requests_per_minute=config["rpm"],
            burst_limit=config["burst"]
        )
    
    print("Production rate limits configured")


# Helper functions for examples
def make_external_api_call():
    """Simulate external API call."""
    # This would be your actual API call
    return "API response"


def extract_reset_time_from_error(error):
    """Extract reset time from rate limit error."""
    # Parse error to get reset time
    return time.time() + 60  # Default to 1 minute from now


if __name__ == "__main__":
    # Run examples
    print("Running Rate Limiting Examples")
    print("=" * 40)
    
    basic_rate_limiting()
    print()
    
    rate_limit_by_execution_mode()
    print()
    
    monitor_rate_limits()
    print()
    
    production_rate_limiting()
