import pytest
from fastapi.testclient import TestClient
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# We need to mock AICouncil before importing main, as main.py instantiates it on startup.
# However, main.py instantiates it inside an async startup_event.
@pytest.fixture
def mock_ai_council():
    patcher = patch("web_app.backend.main.AICouncil")
    mock_class = patcher.start()
    mock_instance = MagicMock()
    mock_class.return_value = mock_instance
    
    # Setup common mock responses
    mock_instance.get_system_status.return_value = {"status": "operational", "version": "1.0.0"}
    
    yield mock_instance
    patcher.stop()

@pytest.fixture
def test_client(mock_ai_council):
    from web_app.backend.main import app
    
    with TestClient(app) as client:
        yield client
