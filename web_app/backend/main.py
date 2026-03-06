"""FastAPI backend for AI Council web interface."""

from __future__ import annotations

import asyncio
import logging
import inspect
import json
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import jwt

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


def _get_jwt_secret() -> str:
    """
    Shared JWT secret used to validate WebSocket auth tokens.

    This should match the JWT secret used by the auth backend.
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        logging.getLogger(__name__).error("JWT_SECRET is not configured for WebSocket authentication.")
    return secret


def _extract_ws_token(websocket: WebSocket) -> Optional[str]:
    # Prefer query params first for browser compatibility.
    token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    if token:
        return token.strip()

    auth = websocket.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    secret = _get_jwt_secret()
    if not secret:
        return None
    try:
        # Audience/issuer validation can be added if needed.
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError as exc:  # broad but intentional – any JWT error → invalid
        logging.getLogger(__name__).warning("Invalid WebSocket JWT: %s", exc)
        return None


def _get_ws_client_key(websocket: WebSocket, token: Optional[str]) -> str:
    # Prefer token-based keying; fall back to IP.
    if token:
        return f"token:{token}"
    host = websocket.client.host if websocket.client else "unknown"
    return f"ip:{host}"


def _parse_rate(spec: str, *, default: Tuple[int, float]) -> Tuple[int, float]:
    """
    Parse a rate spec like "20/60" meaning 20 events per 60 seconds.
    Returns (limit, window_seconds).
    """
    if not spec:
        return default
    try:
        left, right = spec.split("/", 1)
        limit = int(left.strip())
        window = float(right.strip())
        if limit <= 0 or window <= 0:
            raise ValueError("limit/window must be positive")
        return limit, window
    except Exception:
        logging.getLogger(__name__).warning("Invalid WS_RATE_LIMIT=%r, using default %r", spec, default)
        return default


class _WebSocketRateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float) -> bool:
        q = self._events[key]
        cutoff = now - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


_ws_rate_limit_spec = os.getenv("WS_RATE_LIMIT", "20/60")
_ws_limit, _ws_window = _parse_rate(_ws_rate_limit_spec, default=(20, 60.0))
_ws_msg_limiter = _WebSocketRateLimiter(_ws_limit, _ws_window)
_ws_active_connections: Dict[str, int] = defaultdict(int)  # keyed by client IP
_ws_total_connections: int = 0
_ws_max_connections_per_ip = int(os.getenv("WS_MAX_CONNECTIONS_PER_IP", "5") or "5")
_ws_max_connections_global = int(os.getenv("WS_MAX_CONNECTIONS_GLOBAL", "50") or "50")


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
    # Connection-level accounting
    client_ip = websocket.client.host if websocket.client else "unknown"
    global _ws_total_connections

    # Enforce IP and global connection limits before accepting.
    if _ws_total_connections >= _ws_max_connections_global:
        await websocket.close(code=4429)
        return
    if _ws_active_connections[client_ip] >= _ws_max_connections_per_ip:
        await websocket.close(code=4429)
        return

    # Try to get JWT from query/header first.
    token = _extract_ws_token(websocket)
    jwt_payload: Optional[Dict[str, Any]] = None

    if token:
        jwt_payload = _decode_jwt_token(token)
        if jwt_payload is None:
            # Invalid token → close with requested code 4001.
            await websocket.close(code=4001)
            return

    # At this point, either we have a valid JWT or we will expect it
    # as part of the first client message.
    await websocket.accept()
    _ws_total_connections += 1
    _ws_active_connections[client_ip] += 1

    ai_council: AICouncil = websocket.app.state.ai_council

    try:
        # Per-connection timestamps for rate limiting (20 messages/minute by default)
        message_timestamps: Deque[float] = deque()
        per_connection_limit = 20
        per_connection_window = 60.0

        while True:
            data = await websocket.receive_text()

            now = time.time()
            cutoff = now - per_connection_window
            while message_timestamps and message_timestamps[0] <= cutoff:
                message_timestamps.popleft()
            if len(message_timestamps) >= per_connection_limit:
                await websocket.send_json(
                    {"type": "error", "message": "Too many messages on this connection. Please slow down."}
                )
                await websocket.close(code=4429)
                return
            message_timestamps.append(now)

            if len(data) > 50_000:
                await websocket.send_json({"type": "error", "message": "Message too large"})
                await websocket.close(code=1009)
                return

            try:
                request_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            # If we still don't have a validated JWT, allow the client to provide it
            # in the first message as {"token": "..."}.
            if jwt_payload is None:
                msg_token = request_data.get("token")
                if not isinstance(msg_token, str):
                    await websocket.close(code=4001)
                    return
                jwt_payload = _decode_jwt_token(msg_token)
                if jwt_payload is None:
                    await websocket.close(code=4001)
                    return

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
    finally:
        _ws_active_connections[client_key] = max(0, _ws_active_connections[client_key] - 1)
        if _ws_active_connections[client_key] == 0:
            _ws_active_connections.pop(client_key, None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
