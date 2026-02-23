"""
FastAPI backend for AI Council web interface.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from contextlib import asynccontextmanager
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
    """Middleware to add rate limit headers to responses.
    
    Adds standard rate limit headers to all HTTP responses for client visibility:
    - X-RateLimit-Limit: Total requests allowed
    - X-RateLimit-Remaining: Requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp for window reset
    
    Integrates with slowapi limiter to extract rate limit information.
    """
    
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

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

# Rate limit exceeded handler
app.state.limiter = limiter

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler with proper headers.
    
    Returns a 429 Too Many Requests response with:
    - Standardized error format
    - Retry-After header indicating wait time
    - Rate limit headers for client visibility
    
    Args:
        request: FastAPI request object
        exc: RateLimitExceeded exception
        
    Returns:
        JSONResponse with 429 status code and rate limit information
    """
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
@limiter.limit("100/15minutes")
async def process_request(request: Request, req: RequestModel):
    """Process a user request.
    
    Rate limited to 100 requests per 15 minutes per IP address.
    Main endpoint for processing user queries through the AI Council.
    
    Args:
        request: FastAPI request object (used for rate limiting)
        req: RequestModel containing query and execution mode
        
    Returns:
        Processed response with content, confidence, and metadata
        
    Raises:
        HTTPException: If processing fails
    """
async def process_request(request: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
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
        response = await ai_council.process_request(request.query, mode)
        
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
    """Estimate cost and time for a request.
    
    Rate limited to 100 requests per 15 minutes per IP address.
    Provides cost and time estimates without executing the request.
    
    Args:
        request: FastAPI request object (used for rate limiting)
        req: EstimateModel containing query and execution mode
        
    Returns:
        Cost and time estimate information
        
    Raises:
        HTTPException: If estimation fails
    """
async def estimate_cost(request: EstimateModel, ai_council: AICouncil = Depends(get_ai_council)):
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
async def analyze_tradeoffs(request: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    """Analyze cost-quality trade-offs."""
    try:
        analysis = await ai_council.analyze_tradeoffs(request.query)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.
    
    Provides real-time communication for request processing.
    Note: WebSocket connections are not rate limited by slowapi.
    
    Args:
        websocket: WebSocket connection object
        
    Flow:
        1. Accept connection
        2. Receive JSON messages with query and mode
        3. Send status updates during processing
        4. Return final result
    """
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
            response = await ai_council.process_request(query, execution_mode)
            
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
