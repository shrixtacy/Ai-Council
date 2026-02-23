"""
FastAPI backend for AI Council web interface.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import sys
from pathlib import Path

from ai_council.main import AICouncil
from ai_council.core.models import ExecutionMode

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize AI Council on startup."""
    try:
        import os

        # Set config path
        config_path = Path(__file__).parent.parent.parent / "config" / "ai_council.yaml"
        if config_path.exists():
            os.environ['AI_COUNCIL_CONFIG'] = str(config_path)
        
        ai_council_instance = AICouncil(config_path if config_path.exists() else None)
        app.state.ai_council = ai_council_instance
        print("[OK] AI Council initialized successfully")
        yield
    except RuntimeError as e:
        # Handle configuration validation errors gracefully without stack trace
        if "Configuration validation failed" in str(e):
            print("\n" + "="*60)
            print("[CRITICAL] STARTUP FAILED DUE TO CONFIGURATION ERRORS")
            print("="*60)
            print(str(e).replace("Configuration validation failed:", "").strip())
            print("="*60 + "\n")
            import sys
            sys.exit(1)
        
        # Fall through for other RuntimeErrors
        print(f"[ERROR] Failed to initialize AI Council: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"[ERROR] Failed to initialize AI Council: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

app = FastAPI(title="AI Council API", version="1.0.0", lifespan=lifespan)

# Load environment variables
import os
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# CORS configuration
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    # Default to localhost/local IPs for development
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_ai_council(request: Request) -> AICouncil:
    """Dependency to get AI Council instance."""
    return request.app.state.ai_council

class RequestModel(BaseModel):
    query: str
    mode: str = "balanced"

class EstimateModel(BaseModel):
    query: str
    mode: str = "balanced"


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Council API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/api/status")
async def get_status(ai_council: AICouncil = Depends(get_ai_council)):
    """Get system status."""
    try:
        status = ai_council.get_system_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process")
async def process_request(request: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    """Process a user request."""
    try:
        # Map mode string to ExecutionMode
        mode_map = {
            "fast": ExecutionMode.FAST,
            "balanced": ExecutionMode.BALANCED,
            "best_quality": ExecutionMode.BEST_QUALITY
        }
        
        mode = mode_map.get(request.mode.lower(), ExecutionMode.BALANCED)
        
        # Process the request
        response = ai_council.process_request(request.query, mode)
        
        return {
            "success": response.success,
            "content": response.content,
            "confidence": response.overall_confidence,
            "models_used": response.models_used,
            "execution_time": response.execution_metadata.total_execution_time if response.execution_metadata else 0,
            "cost": response.cost_breakdown.total_cost if response.cost_breakdown else 0,
            "execution_path": response.execution_metadata.execution_path if response.execution_metadata else [],
            "arbitration_decisions": response.execution_metadata.arbitration_decisions if response.execution_metadata else [],
            "synthesis_notes": response.execution_metadata.synthesis_notes if response.execution_metadata else [],
            "error_message": response.error_message if not response.success else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/estimate")
async def estimate_cost(request: EstimateModel, ai_council: AICouncil = Depends(get_ai_council)):
    """Estimate cost and time for a request."""
    try:
        mode_map = {
            "fast": ExecutionMode.FAST,
            "balanced": ExecutionMode.BALANCED,
            "best_quality": ExecutionMode.BEST_QUALITY
        }
        
        mode = mode_map.get(request.mode.lower(), ExecutionMode.BALANCED)
        estimate = ai_council.estimate_cost(request.query, mode)
        
        return estimate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
async def analyze_tradeoffs(request: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    """Analyze cost-quality trade-offs."""
    try:
        analysis = ai_council.analyze_tradeoffs(request.query)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    ai_council: AICouncil = websocket.app.state.ai_council
    
    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            query = request_data.get("query", "")
            mode = request_data.get("mode", "balanced")
            
            # Send processing status
            await websocket.send_json({
                "type": "status",
                "message": "Processing your request..."
            })
            
            # Process request
            mode_map = {
                "fast": ExecutionMode.FAST,
                "balanced": ExecutionMode.BALANCED,
                "best_quality": ExecutionMode.BEST_QUALITY
            }
            
            execution_mode = mode_map.get(mode.lower(), ExecutionMode.BALANCED)
            response = ai_council.process_request(query, execution_mode)
            
            # Send result
            await websocket.send_json({
                "type": "result",
                "success": response.success,
                "content": response.content,
                "confidence": response.overall_confidence,
                "models_used": response.models_used,
                "execution_time": response.execution_metadata.total_execution_time if response.execution_metadata else 0,
                "cost": response.cost_breakdown.total_cost if response.cost_breakdown else 0,
                "execution_path": response.execution_metadata.execution_path if response.execution_metadata else [],
                "arbitration_decisions": response.execution_metadata.arbitration_decisions if response.execution_metadata else [],
                "synthesis_notes": response.execution_metadata.synthesis_notes if response.execution_metadata else [],
                "error_message": response.error_message if not response.success else None
            })
            
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
