"""FastAPI backend for AI Council web interface."""

from __future__ import annotations

import asyncio
import logging
import inspect
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

# Add ai_council to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai_council.core.models import ExecutionMode
from ai_council.main import AICouncil


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit headers to responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if hasattr(request.state, "rate_limit"):
            rate_limit = request.state.rate_limit
            rate_limit_dict = rate_limit if isinstance(rate_limit, dict) else getattr(rate_limit, "__dict__", {})

            limit = rate_limit_dict.get("limit")
            remaining = rate_limit_dict.get("remaining")
            reset = rate_limit_dict.get("reset")

            if isinstance(limit, int):
                response.headers["X-RateLimit-Limit"] = str(limit)
            if isinstance(remaining, int):
                response.headers["X-RateLimit-Remaining"] = str(remaining)
            if isinstance(reset, int):
                response.headers["X-RateLimit-Reset"] = str(reset)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize AI Council on startup."""
    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "ai_council.yaml"
        if config_path.exists():
            os.environ["AI_COUNCIL_CONFIG"] = str(config_path)

        app.state.ai_council = AICouncil(config_path if config_path.exists() else None)
        print("[OK] AI Council initialized successfully")
        yield
    except RuntimeError as exc:
        if "Configuration validation failed" in str(exc):
            print("\n" + "=" * 60)
            print("[CRITICAL] STARTUP FAILED DUE TO CONFIGURATION ERRORS")
            print("=" * 60)
            print(str(exc).replace("Configuration validation failed:", "").strip())
            print("=" * 60 + "\n")
            raise
        print(f"[ERROR] Failed to initialize AI Council: {str(exc)}")
        raise
    except Exception as exc:  # pragma: no cover - defensive startup logging
        print(f"[ERROR] Failed to initialize AI Council: {str(exc)}")
        raise


app = FastAPI(title="AI Council API", version="1.0.0", lifespan=lifespan)

# Load environment variables
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
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom 429 response with retry hints."""
    retry_after = 900
    try:
        # slowapi detail often looks like: "100 per 15 minute"
        detail_text = exc.detail
        if isinstance(detail_text, str):
            parts = detail_text.split(" ")
            retry_after = int(parts[-1]) if parts and parts[-1].isdigit() else retry_after
    except (ValueError, IndexError, TypeError) as error:
        logging.getLogger(__name__).debug(
            "Could not parse rate limit detail for retry_after fallback: detail=%s error=%s",
            exc.detail,
            error,
        )
        retry_after = 900

    headers = {
        "Retry-After": str(retry_after),
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
    }
    request_origin = request.headers.get("origin")
    if request_origin:
        headers["Access-Control-Allow-Origin"] = request_origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=429,
        content={"success": False, "message": "Too many requests", "retryAfter": retry_after},
        headers=headers,
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


class RequestModel(BaseModel):
    query: str
    mode: str = "balanced"


class EstimateModel(BaseModel):
    query: str
    mode: str = "balanced"


def get_ai_council(request: Request) -> AICouncil:
    return request.app.state.ai_council


def normalize_mode(mode: str) -> ExecutionMode:
    mode_map = {
        "fast": ExecutionMode.FAST,
        "balanced": ExecutionMode.BALANCED,
        "best_quality": ExecutionMode.BEST_QUALITY,
    }
    return mode_map.get((mode or "balanced").lower(), ExecutionMode.BALANCED)


async def maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def serialize_response(response) -> Dict[str, Any]:
    metadata = getattr(response, "execution_metadata", None)
    cost_data = getattr(response, "cost_breakdown", None)

    synthesis_notes = getattr(metadata, "synthesis_notes", []) if metadata else []
    if isinstance(synthesis_notes, str):
        synthesis_notes = [synthesis_notes] if synthesis_notes else []

    return {
        "success": getattr(response, "success", False),
        "content": getattr(response, "content", ""),
        "confidence": getattr(response, "overall_confidence", 0),
        "models_used": getattr(response, "models_used", []),
        "execution_time": getattr(metadata, "total_execution_time", 0) if metadata else 0,
        "cost": getattr(cost_data, "total_cost", 0) if cost_data else 0,
        "execution_path": getattr(metadata, "execution_path", []) if metadata else [],
        "arbitration_decisions": getattr(metadata, "arbitration_decisions", []) if metadata else [],
        "synthesis_notes": synthesis_notes,
        "error_message": getattr(response, "error_message", None)
        if not getattr(response, "success", False)
        else None,
    }


@app.get("/")
async def root():
    return {"message": "AI Council API", "version": "1.0.0", "status": "operational"}


@app.get("/api/status")
async def get_status(ai_council: AICouncil = Depends(get_ai_council)):
    try:
        return ai_council.get_system_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/process")
@limiter.limit("100/15minutes")
async def process_request(request: Request, req: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    del request  # used by limiter decorator
    try:
        mode = normalize_mode(req.mode)
        response = await maybe_await(ai_council.process_request(req.query, mode))
        return serialize_response(response)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/estimate")
@limiter.limit("100/15minutes")
async def estimate_cost(request: Request, req: EstimateModel, ai_council: AICouncil = Depends(get_ai_council)):
    del request  # used by limiter decorator
    try:
        mode = normalize_mode(req.mode)
        return ai_council.estimate_cost(req.query, mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze")
async def analyze_tradeoffs(req: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    try:
        return await maybe_await(ai_council.analyze_tradeoffs(req.query))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ai_council: AICouncil = websocket.app.state.ai_council

    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)

            query = request_data.get("query", "")
            mode = request_data.get("mode", "balanced")

            await websocket.send_json({"type": "status", "message": "Processing your request..."})

            response = await maybe_await(ai_council.process_request(query, normalize_mode(mode)))

            await websocket.send_json({"type": "result", **serialize_response(response)})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logging.getLogger(__name__).exception("Unexpected websocket error")
        await websocket.send_json({"type": "error", "message": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
