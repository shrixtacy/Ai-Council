import pytest
import os
from ai_council.main import AICouncil
from ai_council.core.models import ExecutionMode

@pytest.mark.asyncio
async def test_council_initialization(temp_config_file):
    # Repro test for council initialization and basic query.
    # Note: temp_config_file fixture already sets DUMMY_API_KEY
    council = AICouncil(config_path=temp_config_file)
    
    # Use a simple prompt that should work with mock models
    prompt = "Hello, AI Council!"
    
    # AICouncil uses process_request, not query
    response = await council.process_request(prompt, execution_mode=ExecutionMode.FAST)
    
    assert response is not None
    # Verify that the response contains some content
    assert len(response.content) > 0
    assert response.success is True
