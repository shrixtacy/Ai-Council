"""FastAPI backend for AI Council web interface."""

import asyncio
import logging
import inspect
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Set
import os
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
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


class TaskManager:
    """Tracks in-flight tasks to allow graceful shutdown waiting."""
    def __init__(self):
        self.active_tasks: Set[asyncio.Task] = set()

    def add(self, task: asyncio.Task):
        self.active_tasks.add(task)

    def remove(self, task: asyncio.Task):
        self.active_tasks.discard(task)

    async def wait_for_completion(self, timeout: float = 15.0):
        """Wait for all tracked tasks to complete, or cancel them after timeout."""
        if not self.active_tasks:
            return
        
        logging.info(f"Waiting for {len(self.active_tasks)} in-flight tasks to complete...")
        deadline = time.time() + timeout
        
        # CodeRabbit Fix: Loop to continuously re-evaluate the task set for late-arrivers
        while self.active_tasks:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            
            # Use FIRST_COMPLETED and a short timeout to wake up and catch newly added tasks
            await asyncio.wait(
                self.active_tasks, 
                timeout=min(1.0, remaining), 
                return_when=asyncio.FIRST_COMPLETED
            )
            
        if self.active_tasks:
            pending = list(self.active_tasks)
            logging.warning(f"{len(pending)} tasks did not complete in time. Cancelling them...")
            for task in pending:
                task.cancel()
            
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                logging.warning(
                    "%s tasks did not acknowledge cancellation before shutdown cleanup",
                    len([task for task in pending if not task.done()]),
                )


class TaskTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track all HTTP requests instantly to prevent shutdown race conditions."""
    async def dispatch(self, request: Request, call_next):
        task = asyncio.current_task()
        task_manager = getattr(request.app.state, "task_manager", None)
        
        if task and task_manager:
            task_manager.add(task)
            
        try:
            return await call_next(request)
        finally:
            if task and task_manager:
                task_manager.remove(task)


def check_shutdown_status(request: Request):
    """Dependency to reject new requests if the server is shutting down."""
    if hasattr(request.app.state, "is_shutting_down") and request.app.state.is_shutting_down.is_set():
        raise HTTPException(status_code=503, detail="Server is currently shutting down. Please try again later.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize AI Council on startup."""
    try:
        app.state.is_shutting_down = asyncio.Event()
        app.state.task_manager = TaskManager()
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

    finally:
        print("\n[INFO] Initiating graceful shutdown sequence...")
        if hasattr(app.state, "is_shutting_down"):
            app.state.is_shutting_down.set()
        
        print("[INFO] Waiting for in-flight tasks to complete...")
        await app.state.task_manager.wait_for_completion(timeout=15.0)
        
        print("[INFO] Closing active WebSocket connections...")
        await ws_manager.close_all()
        
        print("[INFO] Cleaning up persistent layers and caching...")
        ai_council = getattr(app.state, "ai_council", None)
        # CodeRabbit Fix: Explicitly delegate teardown sequencing to AICouncil.shutdown()
        if ai_council and hasattr(ai_council, "shutdown"):
            try:
                if inspect.iscoroutinefunction(ai_council.shutdown):
                    await ai_council.shutdown()
                else:
                    ai_council.shutdown()
                print("[OK] Successfully executed AI Council `shutdown`")
            except Exception as e:
                print(f"[ERROR] Failed during AI Council `shutdown`: {e}")

        print("[OK] Graceful shutdown complete.")


app = FastAPI(title="AI Council API", version="1.0.0", lifespan=lifespan)

# Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# CORS configuration
env = os.getenv("ENVIRONMENT", "production").strip().lower()
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
elif env == "development":
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
else:
    allowed_origins = []

app.add_middleware(TaskTrackingMiddleware)
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


@app.get("/", dependencies=[Depends(check_shutdown_status)])
async def root():
    return {"message": "AI Council API", "version": "1.0.0", "status": "operational"}


@app.get("/api/status", dependencies=[Depends(check_shutdown_status)])
async def get_status(ai_council: AICouncil = Depends(get_ai_council)):
    try:
        return ai_council.get_system_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/process", dependencies=[Depends(check_shutdown_status)])
@limiter.limit("100/15minutes")
async def process_request(request: Request, req: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    del request  # used by limiter decorator
    try:
        mode = normalize_mode(req.mode)
        response = await maybe_await(ai_council.process_request(req.query, mode))
        return serialize_response(response)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/estimate", dependencies=[Depends(check_shutdown_status)])
@limiter.limit("100/15minutes")
async def estimate_cost(request: Request, req: EstimateModel, ai_council: AICouncil = Depends(get_ai_council)):
    try:
        mode = normalize_mode(req.mode)
        return ai_council.estimate_cost(req.query, mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze", dependencies=[Depends(check_shutdown_status)])
async def analyze_tradeoffs(request: Request, req: RequestModel, ai_council: AICouncil = Depends(get_ai_council)):
    try:
        return await maybe_await(ai_council.analyze_tradeoffs(req.query))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

class WebSocketManager:
    def __init__(self):
        self.active_sockets: Set[WebSocket] = set()
        self.ip_connections: Dict[str, int] = {}
        self.message_timestamps: Dict[WebSocket, List[float]] = {}
        self.active_connections = 0

        self.MAX_CONNECTIONS = 1000
        self.MAX_IP_CONNECTIONS = 10
        self.RATE_LIMIT_MESSAGES = 20
        self.RATE_LIMIT_WINDOW = 60  # seconds

    async def authenticate(self, websocket: WebSocket) -> bool:

        jwt_secret = os.getenv("JWT_SECRET_KEY")
        if not jwt_secret:
            raise RuntimeError("JWT_SECRET_KEY must be set for WebSocket auth")
        jwt_algorithm = JWT_ALGORITHM

        token = websocket.query_params.get("token")
        if not token:
            try:
                auth_payload = await asyncio.wait_for(websocket.receive_json(), timeout=5)
                token = auth_payload.get("token") if isinstance(auth_payload, dict) else None
            except Exception:
                pass
                
        if not token:
            return False
            
        try:
            jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
            return True
        except jwt.PyJWTError:
            return False

    def connect(self, websocket: WebSocket, client_ip: str) -> bool:
        if len(self.active_sockets) >= self.MAX_CONNECTIONS:
            return False
        
        current_ip_count = self.ip_connections.get(client_ip, 0)
        if current_ip_count >= self.MAX_IP_CONNECTIONS:
            return False

        self.active_sockets.add(websocket)
        self.ip_connections[client_ip] = current_ip_count + 1
        self.message_timestamps[websocket] = []
        return True

    def disconnect(self, websocket: WebSocket, client_ip: str):
        self.active_sockets.discard(websocket)
        if websocket in self.message_timestamps:
            del self.message_timestamps[websocket]
            self.active_connections = max(0, self.active_connections - 1)
            if client_ip in self.ip_connections:
                self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
                if self.ip_connections[client_ip] == 0:
                    del self.ip_connections[client_ip]

    def check_rate_limit(self, websocket: WebSocket) -> bool:
        """Returns True if limits are exceeded."""
        now = time.time()
        timestamps = self.message_timestamps.get(websocket, [])
        timestamps = [ts for ts in timestamps if now - ts < self.RATE_LIMIT_WINDOW]
        
        if len(timestamps) >= self.RATE_LIMIT_MESSAGES:
            self.message_timestamps[websocket] = timestamps
            return True
            
        timestamps.append(now)
        self.message_timestamps[websocket] = timestamps
        return False

    async def close_all(self):
        """Cleanly notifies and closes all active websocket connections during shutdown."""
        sockets = list(self.active_sockets)
        
        async def _close_socket(ws: WebSocket):
            try:
                await asyncio.wait_for(
                    ws.send_json({"type": "system", "message": "Server is shutting down. Connection closing."}),
                    timeout=1.0,
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to send websocket shutdown notice", exc_info=True)
                
            try:
                await asyncio.wait_for(
                    ws.close(code=1001, reason="Server going down"),
                    timeout=1.0,
                )
            except Exception:
                logging.getLogger(__name__).debug("Failed to close websocket during shutdown", exc_info=True)

        if sockets:
            await asyncio.gather(*(_close_socket(ws) for ws in sockets), return_exceptions=True)


ws_manager = WebSocketManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if websocket.app.state.is_shutting_down.is_set():
        try:
            await websocket.accept()
            await websocket.close(code=1013, reason="Server is shutting down")
        except Exception:
            pass
        return

    await websocket.accept()
    
    client = websocket.client
    client_ip = client.host if client else "unknown"

    if not ws_manager.connect(websocket, client_ip):
        await websocket.close(code=1008, reason="Connection limit exceeded")
        return

    try:
        if not await ws_manager.authenticate(websocket):
            await websocket.close(code=4001, reason="Authentication failed")
            return

        ai_council: AICouncil = websocket.app.state.ai_council

        while not websocket.app.state.is_shutting_down.is_set():
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                continue 

            if websocket.app.state.is_shutting_down.is_set():
                try:
                    await websocket.close(code=1013, reason="Server is shutting down")
                except Exception:
                    pass
                break

            if ws_manager.check_rate_limit(websocket):
                await websocket.send_json({"type": "error", "message": "Rate limit exceeded. Please wait."})
                await websocket.close(code=1008, reason="Rate limit exceeded")
                break
                
            try:
                request_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
                continue

            query = request_data.get("query", "")
            mode = request_data.get("mode", "balanced")

            await websocket.send_json({"type": "status", "message": "Processing your request..."})

            # CodeRabbit Fix: Final check immediately before spawning background job
            if websocket.app.state.is_shutting_down.is_set():
                try:
                    await websocket.send_json({"type": "error", "message": "Server is shutting down. Request aborted."})
                    await websocket.close(code=1013, reason="Server is shutting down")
                except Exception:
                    pass
                break

            task = asyncio.create_task(maybe_await(ai_council.process_request(query, normalize_mode(mode))))
            websocket.app.state.task_manager.add(task)
            
            try:
                response = await task
                await websocket.send_json({"type": "result", **serialize_response(response)})
            except asyncio.CancelledError:
                try:
                    await websocket.send_json({"type": "error", "message": "Request cancelled due to server shutdown."})
                except Exception:
                    pass
                break
            except Exception as e:
                logging.error(f"Error processing WS request: {e}")
                await websocket.send_json({"type": "error", "message": "Error processing request"})
            finally:
                websocket.app.state.task_manager.remove(task)

    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass  
    except Exception as exc:
        logging.getLogger(__name__).exception("Unexpected websocket error")
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
    finally:
        ws_manager.disconnect(websocket, client_ip)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)