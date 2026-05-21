from ai_council.core.models import ExecutionMode


def register(context):
    """Register example plugin hooks."""
    # Routing rules are declared through the manifest. Hooks are registered separately.
    return None


def pre_execution(user_input: str, execution_mode: ExecutionMode):
    """Example pre-execution hook."""
    # Plugins may inspect or log the request before orchestration begins.
    return None


def post_arbitration(validated_responses, explanation):
    """Example post-arbitration hook."""
    return None


def post_synthesis(final_response):
    """Example post-synthesis hook."""
    return None
