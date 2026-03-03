class MockResponse:
    def __init__(self, success=True, content="Test response"):
        self.success = success
        self.content = content
        self.overall_confidence = 0.95
        self.models_used = ["gpt-4"]
        
        class MetaData:
            def __init__(self):
                self.total_execution_time = 1.2
                self.execution_path = []
                # Required fields expected by serializer
                self.arbitration_decisions = []
                self.synthesis_notes = ""
            
        class CostData:
            total_cost = 0.05
            
        self.execution_metadata = MetaData()
        self.cost_breakdown = CostData()
        self.error_message = None

def test_root(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "AI Council API"

def test_get_status(test_client, mock_ai_council):
    response = test_client.get("/api/status")
    assert response.status_code == 200
    assert response.json() == {"status": "operational", "version": "1.0.0"}
    mock_ai_council.get_system_status.assert_called_once()

def test_process_request_success(test_client, mock_ai_council):
    mock_ai_council.process_request.return_value = MockResponse()
    
    response = test_client.post(
        "/api/process",
        json={"query": "Hello AI", "mode": "fast"}
    )
    
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["success"] is True
    assert data["content"] == "Test response"
    assert "execution_time" in data
    assert "cost" in data

def test_estimate_cost(test_client, mock_ai_council):
    mock_ai_council.estimate_cost.return_value = {"cost": 0.1, "time": 2.0}
    
    response = test_client.post(
        "/api/estimate",
        json={"query": "Complex task", "mode": "best_quality"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"cost": 0.1, "time": 2.0}

def test_analyze_tradeoffs(test_client, mock_ai_council):
    mock_ai_council.analyze_tradeoffs.return_value = {"fast": 0.01, "balanced": 0.05, "best_quality": 0.1}
    
    response = test_client.post(
        "/api/analyze",
        json={"query": "Compare modes", "mode": "balanced"}
    )
    
    assert response.status_code == 200
    assert "fast" in response.json()

import jwt
from starlette.websockets import WebSocketDisconnect
from main import JWT_SECRET_KEY, JWT_ALGORITHM

def test_websocket_unauthenticated(test_client):
    try:
        with test_client.websocket_connect("/ws") as websocket:
            websocket.send_json({"token": "invalid_token_payload"})
            websocket.receive_text()
        raise AssertionError("Should have been rejected")
    except WebSocketDisconnect as e:
        assert e.code == 4001

def test_websocket(test_client, mock_ai_council):
    mock_ai_council.process_request.return_value = MockResponse(content="WS response")
    
    valid_token = jwt.encode({"sub": "test"}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    with test_client.websocket_connect(f"/ws?token={valid_token}") as websocket:
        websocket.send_json({"query": "Hello via WS", "mode": "fast"})
        
        # Should receive status message first
        status_msg = websocket.receive_json()
        assert status_msg["type"] == "status"
        
        # Then the result message
        result_msg = websocket.receive_json()
        assert result_msg["type"] == "result"
        assert result_msg["success"] is True
        assert result_msg["content"] == "WS response"

def test_websocket_rate_limit(test_client, mock_ai_council):
    mock_ai_council.process_request.return_value = MockResponse(content="WS response")
    valid_token = jwt.encode({"sub": "test_rl"}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    with test_client.websocket_connect(f"/ws?token={valid_token}") as websocket:
        # Send 20 messages (allowed)
        for i in range(20):
            websocket.send_json({"query": f"Msg {i}", "mode": "fast"})
            websocket.receive_json() # status
            websocket.receive_json() # result
            
        # Send 21st message (should be rate limited)
        websocket.send_json({"query": "Msg 21", "mode": "fast"})
        error_msg = websocket.receive_json()
        assert error_msg["type"] == "error"
        assert "Rate limit exceeded" in error_msg["message"]
