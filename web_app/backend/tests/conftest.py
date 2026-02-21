import pytest
from fastapi.testclient import TestClient
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend directory is in path so imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    from web_app.backend.main import app, startup_event
    import asyncio
    
    # Run the startup event manually in the test environment
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(startup_event())
    finally:
        loop.close()
    
    with TestClient(app) as client:
        yield client
