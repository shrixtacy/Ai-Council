"""Council processing endpoints."""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.middleware import get_current_user
from app.models.user import User
from app.models.request import Request
from app.models.response import Response
from app.services.council_orchestration_bridge import get_council_bridge
from app.services.websocket_manager import websocket_manager
from ai_council.core.models import ExecutionMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/council", tags=["council"])


# Pydantic schemas
class ExecutionModeEnum(str):
    """Execution mode enum."""
    FAST = "fast"
    BALANCED = "balanced"
    BEST_QUALITY = "best_quality"


class CouncilRequestCreate(BaseModel):
    """Schema for creating a council request."""
    content: str = Field(..., min_length=1, max_length=5000)
    execution_mode: str = Field(default="balanced")
    
    @field_validator('execution_mode')
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        """Validate execution mode."""
        valid_modes = ["fast", "balanced", "best_quality"]
        if v not in valid_modes:
            raise ValueError(f"execution_mode must be one of: {', '.join(valid_modes)}")
        return v
    
    @field_validator('content')
    @classmethod
    def validate_content_length(cls, v: str) -> str:
        """Validate content length."""
        if len(v) < 1:
            raise ValueError("content must not be empty")
        if len(v) > 5000:
            raise ValueError("content must not exceed 5000 characters")
        return v


class CouncilRequestResponse(BaseModel):
    """Schema for council request response."""
    request_id: str
    status: str
    websocket_url: str


class RequestStatusResponse(BaseModel):
    """Schema for request status response."""
    request_id: str
    status: str
    progress: int
    current_stage: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ModelContribution(BaseModel):
    """Schema for model contribution."""
    model_id: str
    subtasks_handled: int
    total_cost: float
    average_confidence: float


class CouncilResponseDetail(BaseModel):
    """Schema for detailed council response."""
    request_id: str
    content: str
    confidence: float
    execution_time: float
    total_cost: float
    models_used: list
    orchestration_metadata: dict
    created_at: datetime


@router.post("/process", response_model=CouncilRequestResponse)
async def process_request(
    request_data: CouncilRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Process a request through AI Council with real-time orchestration.
    
    This endpoint:
    1. Validates the request content and execution mode
    2. Creates a Request record with status "pending"
    3. Establishes a WebSocket connection for real-time updates
    4. Starts async processing with CouncilOrchestrationBridge
    5. Returns request_id and websocket_url
    
    Args:
        request_data: Request content and execution mode
        current_user: Authenticated user
        db: Database session
        
    Returns:
        CouncilRequestResponse with request_id, status, and websocket_url
    """
    try:
        logger.info(
            f"Processing council request for user {current_user.id}: "
            f"mode={request_data.execution_mode}, "
            f"content_length={len(request_data.content)}"
        )
        
        # Create Request record with status "pending"
        db_request = Request(
            user_id=current_user.id,
            content=request_data.content,
            execution_mode=request_data.execution_mode,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        db.add(db_request)
        await db.commit()
        await db.refresh(db_request)
        
        request_id = str(db_request.id)
        logger.info(f"Created request record: {request_id}")
        
        # Map execution mode string to ExecutionMode enum
        execution_mode_map = {
            "fast": ExecutionMode.FAST,
            "balanced": ExecutionMode.BALANCED,
            "best_quality": ExecutionMode.BEST_QUALITY
        }
        execution_mode = execution_mode_map[request_data.execution_mode]
        
        # Start async processing in background
        # We don't await this - it runs in the background
        asyncio.create_task(
            _process_request_background(
                request_id=request_id,
                user_input=request_data.content,
                execution_mode=execution_mode,
                db=db,
                user_id=str(current_user.id)
            )
        )
        
        # Generate WebSocket URL
        from app.core.config import settings
        websocket_url = f"ws://localhost:8000{settings.API_V1_PREFIX}/ws/{request_id}"
        
        logger.info(f"Request {request_id} queued for processing")
        
        return CouncilRequestResponse(
            request_id=request_id,
            status="pending",
            websocket_url=websocket_url
        )
        
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process request"
        )


async def _process_request_background(
    request_id: str,
    user_input: str,
    execution_mode: ExecutionMode,
    db: AsyncSession,
    user_id: str = None
):
    """
    Process request in background and update database.
    
    This function:
    1. Processes the request through AI Council (with user API keys if available)
    2. Updates the Request status to "completed" or "failed"
    3. Creates a Response record with the results
    
    Args:
        request_id: Request ID
        user_input: User's input text
        execution_mode: Execution mode
        db: Database session
        user_id: User ID to load user-specific API keys
    """
    # Create a new database session for background processing
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        try:
            logger.info(f"Background processing started for request {request_id}")
            
            # Get council bridge
            bridge = get_council_bridge()
            
            # Process request through AI Council with user_id for API key loading
            final_response = await bridge.process_request(
                request_id=request_id,
                user_input=user_input,
                execution_mode=execution_mode,
                user_id=user_id
            )
            
            # Update Request record
            from sqlalchemy import select
            result = await session.execute(
                select(Request).where(Request.id == UUID(request_id))
            )
            db_request = result.scalar_one_or_none()
            
            if db_request:
                db_request.status = "completed" if final_response.success else "failed"
                db_request.completed_at = datetime.utcnow()
                
                # Create Response record
                db_response = Response(
                    request_id=UUID(request_id),
                    content=final_response.content,
                    confidence=final_response.overall_confidence,
                    total_cost=final_response.cost_breakdown.total_cost if final_response.cost_breakdown else 0.0,
                    execution_time=final_response.cost_breakdown.execution_time if final_response.cost_breakdown else 0.0,
                    models_used={"models": final_response.models_used or []},
                    orchestration_metadata={
                        "execution_path": final_response.execution_metadata.execution_path if hasattr(final_response, 'execution_metadata') and final_response.execution_metadata else [],
                        "parallel_executions": final_response.execution_metadata.parallel_executions if hasattr(final_response, 'execution_metadata') and final_response.execution_metadata else 0,
                        "success": final_response.success,
                        "error_message": final_response.error_message if hasattr(final_response, 'error_message') else None
                    },
                    created_at=datetime.utcnow()
                )
                
                session.add(db_response)
                await session.commit()
                
                # Track provider costs
                if final_response.cost_breakdown and hasattr(final_response.cost_breakdown, 'by_subtask'):
                    try:
                        from app.services.provider_cost_tracker import get_provider_cost_tracker
                        provider_cost_tracker = get_provider_cost_tracker()
                        
                        # Extract subtask costs from cost breakdown
                        subtask_costs = []
                        for subtask_cost in final_response.cost_breakdown.by_subtask:
                            subtask_costs.append({
                                "model_id": subtask_cost.get("model_id", "unknown"),
                                "input_tokens": subtask_cost.get("input_tokens", 0),
                                "output_tokens": subtask_cost.get("output_tokens", 0),
                                "cost": subtask_cost.get("cost", 0.0)
                            })
                        
                        await provider_cost_tracker.track_request_costs(
                            session, UUID(request_id), subtask_costs
                        )
                        logger.info(f"Tracked provider costs for request {request_id}")
                    except Exception as cost_error:
                        logger.warning(f"Failed to track provider costs: {cost_error}")
                
                # Invalidate user stats cache
                try:
                    from app.core.redis import redis_client
                    cache_key = redis_client.get_user_stats_key(str(db_request.user_id))
                    await redis_client.client.delete(cache_key)
                    logger.info(f"Invalidated stats cache for user {db_request.user_id}")
                except Exception as cache_error:
                    logger.warning(f"Failed to invalidate cache: {cache_error}")
                
                logger.info(
                    f"Request {request_id} completed: "
                    f"success={final_response.success}, "
                    f"confidence={final_response.overall_confidence:.2f}"
                )
            else:
                logger.error(f"Request {request_id} not found in database")
                
        except Exception as e:
            logger.error(f"Error in background processing for request {request_id}: {e}", exc_info=True)
            
            # Try to update request status to failed
            try:
                from sqlalchemy import select
                result = await session.execute(
                    select(Request).where(Request.id == UUID(request_id))
                )
                db_request = result.scalar_one_or_none()
                
                if db_request:
                    db_request.status = "failed"
                    db_request.completed_at = datetime.utcnow()
                    await session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update request status: {update_error}")


@router.get("/status/{request_id}", response_model=RequestStatusResponse)
async def get_request_status(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of a request.
    
    Args:
        request_id: Request ID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        RequestStatusResponse with status, progress, and current_stage
    """
    try:
        # Query Request record
        from sqlalchemy import select
        result = await db.execute(
            select(Request).where(Request.id == request_id)
        )
        db_request = result.scalar_one_or_none()
        
        if not db_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found"
            )
        
        # Check if user owns this request
        if db_request.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this request"
            )
        
        # Calculate progress based on status
        progress_map = {
            "pending": 0,
            "processing": 50,
            "completed": 100,
            "failed": 100
        }
        progress = progress_map.get(db_request.status, 0)
        
        # Determine current stage
        current_stage = None
        if db_request.status == "pending":
            current_stage = "queued"
        elif db_request.status == "processing":
            current_stage = "processing"
        elif db_request.status == "completed":
            current_stage = "complete"
        elif db_request.status == "failed":
            current_stage = "failed"
        
        return RequestStatusResponse(
            request_id=str(db_request.id),
            status=db_request.status,
            progress=progress,
            current_stage=current_stage,
            created_at=db_request.created_at,
            completed_at=db_request.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get request status"
        )


@router.get("/result/{request_id}", response_model=CouncilResponseDetail)
async def get_request_result(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the result of a completed request.
    
    Args:
        request_id: Request ID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        CouncilResponseDetail with full response and orchestration metadata
    """
    try:
        # Query Request and Response records
        from sqlalchemy import select
        result = await db.execute(
            select(Request).where(Request.id == request_id)
        )
        db_request = result.scalar_one_or_none()
        
        if not db_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found"
            )
        
        # Check if user owns this request
        if db_request.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this request"
            )
        
        # Get response
        result = await db.execute(
            select(Response).where(Response.request_id == request_id)
        )
        db_response = result.scalar_one_or_none()
        
        if not db_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response not found - request may not be completed yet"
            )
        
        return CouncilResponseDetail(
            request_id=str(db_request.id),
            content=db_response.content,
            confidence=db_response.confidence,
            execution_time=db_response.execution_time,
            total_cost=db_response.total_cost,
            models_used=db_response.models_used.get("models", []),
            orchestration_metadata=db_response.orchestration_metadata,
            created_at=db_response.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request result: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get request result"
        )


class RequestHistoryItem(BaseModel):
    """Schema for request history item."""
    id: str
    content: str
    execution_mode: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    confidence: Optional[float] = None
    cost: Optional[float] = None


class RequestHistoryResponse(BaseModel):
    """Schema for request history response."""
    items: list[RequestHistoryItem]
    total: int
    page: int
    pages: int


@router.get("/history", response_model=RequestHistoryResponse)
async def get_request_history(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    mode: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's request history with pagination and filtering.
    
    This endpoint:
    1. Queries user's requests with pagination (page, limit)
    2. Supports search filter by content substring
    3. Supports filter by execution_mode
    4. Supports filter by date range (start_date, end_date)
    5. Sorts by created_at DESC
    6. Returns items, total, page, pages
    
    Args:
        page: Page number (1-indexed)
        limit: Items per page (default 20)
        search: Search term for content substring match
        mode: Filter by execution mode
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        current_user: Authenticated user
        db: Database session
        
    Returns:
        RequestHistoryResponse with paginated items and metadata
    """
    try:
        from sqlalchemy import select, func, and_, or_
        from sqlalchemy.orm import selectinload
        
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page must be >= 1"
            )
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100"
            )
        
        # Build base query
        query = select(Request).where(Request.user_id == current_user.id)
        
        # Apply search filter (case-insensitive substring match)
        if search:
            query = query.where(Request.content.ilike(f"%{search}%"))
        
        # Apply execution mode filter
        if mode:
            valid_modes = ["fast", "balanced", "best_quality"]
            if mode not in valid_modes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"mode must be one of: {', '.join(valid_modes)}"
                )
            query = query.where(Request.execution_mode == mode)
        
        # Apply date range filters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.where(Request.created_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date must be in ISO format"
                )
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.where(Request.created_at <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date must be in ISO format"
                )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar()
        
        # Calculate pages
        pages = (total + limit - 1) // limit if total > 0 else 0
        
        # Apply sorting (created_at DESC)
        query = query.order_by(Request.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        requests = result.scalars().all()
        
        # Build response items
        items = []
        for req in requests:
            # Get response if exists
            response_query = select(Response).where(Response.request_id == req.id)
            response_result = await db.execute(response_query)
            response = response_result.scalar_one_or_none()
            
            items.append(RequestHistoryItem(
                id=str(req.id),
                content=req.content,
                execution_mode=req.execution_mode,
                status=req.status,
                created_at=req.created_at,
                completed_at=req.completed_at,
                confidence=float(response.confidence) if response else None,
                cost=float(response.total_cost) if response else None
            ))
        
        logger.info(
            f"Retrieved request history for user {current_user.id}: "
            f"page={page}, limit={limit}, total={total}, items={len(items)}"
        )
        
        return RequestHistoryResponse(
            items=items,
            total=total,
            page=page,
            pages=pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get request history"
        )
