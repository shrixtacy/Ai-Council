import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from web_app.backend.ai_adapters import (
    OpenAIAdapter, AnthropicAdapter, GoogleGeminiAdapter, GroqAdapter, MistralAdapter, XAIAdapter, create_model_adapter
)

@pytest.fixture
def mock_httpx_post():
    with patch("httpx.AsyncClient.post") as mock_post:
        # Create a mock response
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        yield mock_post

def test_create_model_adapter():
    adapter = create_model_adapter("openai", "gpt-4", "test-key")
    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.get_model_id() == "gpt-4"
    assert adapter.api_key == "test-key"

@pytest.mark.asyncio
async def test_openai_adapter_async(mock_httpx_post):
    adapter = OpenAIAdapter("gpt-4", "test-key")
    
    # Configure mock response correctly for asyncio tests
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello from OpenAI"}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_post.return_value = mock_response
    
    result = await adapter.generate_async("Test prompt")
    assert result == "Hello from OpenAI"
    
    # Verify the call
    mock_httpx_post.assert_called_with(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test prompt"}],
            "temperature": 0.7,
            "max_tokens": 4000
        }
    )

@pytest.mark.asyncio
async def test_anthropic_adapter_async(mock_httpx_post):
    adapter = AnthropicAdapter("claude-3-opus", "test-key")
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"text": "Hello from Anthropic"}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_post.return_value = mock_response
    
    result = await adapter.generate_async("Test prompt")
    assert result == "Hello from Anthropic"

@pytest.mark.asyncio
async def test_google_adapter_async(mock_httpx_post):
    adapter = GoogleGeminiAdapter("gemini-pro", "test-key")
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Hello from Google"}]}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx_post.return_value = mock_response
    
    result = await adapter.generate_async("Test prompt")
    assert result == "Hello from Google"

def test_missing_api_key():
    adapter = OpenAIAdapter("gpt-4", api_key="")
    
    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        import asyncio
        asyncio.run(adapter.generate_async("Test"))
