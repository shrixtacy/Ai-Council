"""
FastAPI backend for AI Council web interface.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import sys
import time
from pathlib import Path

# Rate limiting imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Add ai_council to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai_council.main import AICouncil
from ai_council.core.models import ExecutionMode

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit headers to responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Get rate limit info from limiter
        if hasattr(request.state, 'rate_limit'):
            limit = request.state.rate_limit.get("limit", 100)
            remaining = request.state.rate_limit.get("remaining", 100)
            reset = request.state.rate_limit.get("reset", int(time.time()) + 900)
        else:
            # Default values if rate limit info not available
            limit = 100
            remaining = 100
            reset = int(time.time()) + 900
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        
        return response

app = FastAPI(title="AI Council API", version="1.0.0")

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

# Rate limit exceeded handler
app.state.limiter = limiter

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler with proper headers."""
    retry_after = int(exc.detail.split(" ")[-1]) if " " in exc.detail else 900
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Too many requests",
            "retryAfter": retry_after
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + retry_after)
        }
    )

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global AI Council instance
ai_council = None


class RequestModel(BaseModel):
    query: str
    mode: str = "balanced"


class EstimateModel(BaseModel):
    query: str
    mode: str = "balanced"


@app.on_event("startup")
async def startup_event():
    """Initialize AI Council on startup."""
    global ai_council
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Set config path
        import os
        config_path = Path(__file__).parent.parent.parent / "config" / "ai_council.yaml"
        if config_path.exists():
            os.environ['AI_COUNCIL_CONFIG'] = str(config_path)
        
        ai_council = AICouncil(config_path if config_path.exists() else None)
        print("✓ AI Council initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize AI Council: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Council API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/api/status")
@limiter.limit("100/15minutes")
async def get_status(request: Request):
    """Get system status."""
    try:
        status = ai_council.get_system_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process")
@limiter.limit("100/15minutes")
async def process_request(request: Request, req: RequestModel):
    """Process a user request."""
    try:
        # Map mode string to ExecutionMode
        mode_map = {
            "fast": ExecutionMode.FAST,
            "balanced": ExecutionMode.BALANCED,
            "best_quality": ExecutionMode.BEST_QUALITY
        }
        
        mode = mode_map.get(req.mode.lower(), ExecutionMode.BALANCED)
        
        # Process the request
        response = ai_council.process_request(req.query, mode)
        
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
@limiter.limit("100/15minutes")
async def estimate_cost(request: Request, req: EstimateModel):
    """Estimate cost and time for a request."""
    try:
        mode_map = {
            "fast": ExecutionMode.FAST,
            "balanced": ExecutionMode.BALANCED,
            "best_quality": ExecutionMode.BEST_QUALITY
        }
        
        mode = mode_map.get(req.mode.lower(), ExecutionMode.BALANCED)
        estimate = ai_council.estimate_cost(req.query, mode)
        
        return estimate
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
@limiter.limit("100/15minutes")
async def analyze_tradeoffs(request: Request, req: RequestModel):
    """Analyze cost-quality trade-offs."""
    try:
        analysis = ai_council.analyze_tradeoffs(req.query)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    
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
