"""Admin endpoints for user management and system monitoring."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.middleware import get_current_admin_user
from app.models.user import User
from app.models.request import Request
from app.models.response import Response
from app.services.websocket_manager import websocket_manager
from app.services.cloud_ai.circuit_breaker import get_circuit_breaker
from app.services.provider_health_checker import get_health_checker

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


# Pydantic schemas
class UserListItem(BaseModel):
    """User list item schema for admin user list."""
    model_config = {"from_attributes": True}
    
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    total_requests: int


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[UserListItem]
    total: int
    page: int
    pages: int


class UserUpdateRequest(BaseModel):
    """User update request schema for admin."""
    is_active: Optional[bool] = None
    role: Optional[str] = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate role is either 'user' or 'admin'."""
        if v is not None and v not in ['user', 'admin']:
            raise ValueError('Role must be either "user" or "admin"')
        return v


class UserDetailResponse(BaseModel):
    """Detailed user information for admin."""
    model_config = {"from_attributes": True}
    
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    total_requests: int
    recent_requests: list[dict]


class AuditLogEntry(BaseModel):
    """Audit log entry for admin actions."""
    timestamp: str
    admin_id: str
    admin_email: str
    action: str
    target_user_id: str
    target_user_email: str
    changes: dict


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get paginated list of all users.
    
    Requires admin role for access.
    
    Args:
        page: Page number (1-indexed)
        limit: Number of items per page (max 100)
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Paginated list of users with email, registration date, total requests, and account status
    """
    # Calculate offset
    offset = (page - 1) * limit
    
    # Query users with request count
    users_query = (
        db.query(
            User,
            func.count(Request.id).label('total_requests')
        )
        .outerjoin(Request, User.id == Request.user_id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    
    # Get total count
    total = db.query(User).count()
    
    # Get paginated results
    users_with_counts = users_query.offset(offset).limit(limit).all()
    
    # Format response
    user_items = []
    for user, request_count in users_with_counts:
        user_items.append(UserListItem(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            total_requests=request_count
        ))
    
    # Calculate total pages
    pages = (total + limit - 1) // limit
    
    return UserListResponse(
        users=user_items,
        total=total,
        page=page,
        pages=pages
    )


@router.patch("/users/{user_id}", status_code=status.HTTP_200_OK)
async def update_user(
    user_id: str,
    update_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Update user account (enable/disable, change role).
    
    Requires admin role for access.
    Logs all admin actions for audit purposes.
    
    Args:
        user_id: User ID to update
        update_data: Update data (is_active, role)
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException 404: If user not found
        HTTPException 400: If trying to modify own account
    """
    # Convert string UUID to UUID object
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Find user
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from modifying their own account
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account"
        )
    
    # Track changes for audit log
    changes = {}
    
    # Update is_active if provided
    if update_data.is_active is not None:
        old_value = user.is_active
        user.is_active = update_data.is_active
        changes['is_active'] = {'old': old_value, 'new': update_data.is_active}
    
    # Update role if provided
    if update_data.role is not None:
        old_value = user.role
        user.role = update_data.role
        changes['role'] = {'old': old_value, 'new': update_data.role}
    
    # Update timestamp
    user.updated_at = datetime.utcnow()
    
    # Commit changes
    db.commit()
    db.refresh(user)
    
    # Log admin action for audit
    audit_entry = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        admin_id=str(current_admin.id),
        admin_email=current_admin.email,
        action="update_user",
        target_user_id=str(user.id),
        target_user_email=user.email,
        changes=changes
    )
    
    logger.info(f"Admin action: {audit_entry.model_dump_json()}")
    
    return {
        "message": "User updated successfully",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "role": user.role
        }
    }


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get detailed user information including request history and statistics.
    
    Requires admin role for access.
    
    Args:
        user_id: User ID to retrieve
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Detailed user information with request history
        
    Raises:
        HTTPException 404: If user not found
    """
    # Convert string UUID to UUID object
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Find user
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get total request count
    total_requests = db.query(func.count(Request.id)).filter(
        Request.user_id == user_uuid
    ).scalar()
    
    # Get recent requests (last 10)
    recent_requests = (
        db.query(Request)
        .filter(Request.user_id == user_uuid)
        .order_by(Request.created_at.desc())
        .limit(10)
        .all()
    )
    
    # Format recent requests
    recent_requests_data = []
    for req in recent_requests:
        recent_requests_data.append({
            "id": str(req.id),
            "content": req.content[:100] + "..." if len(req.content) > 100 else req.content,
            "execution_mode": req.execution_mode,
            "status": req.status,
            "created_at": req.created_at.isoformat(),
            "completed_at": req.completed_at.isoformat() if req.completed_at else None
        })
    
    return UserDetailResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
        total_requests=total_requests or 0,
        recent_requests=recent_requests_data
    )


class ProviderHealthStatus(BaseModel):
    """Health status for a cloud AI provider."""
    status: str  # "healthy", "degraded", or "down"
    last_check: str
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status for a provider."""
    state: str  # "closed", "open", or "half_open"
    failure_count: int
    timeout: float


class MonitoringResponse(BaseModel):
    """System monitoring data response."""
    total_users: int
    requests_last_24h: int
    average_response_time: float
    total_cost_last_24h: float
    success_rate: float
    active_websockets: int
    provider_health: Dict[str, ProviderHealthStatus]
    circuit_breakers: Dict[str, CircuitBreakerStatus]
    provider_cost_breakdown: Dict[str, Any]


@router.get("/monitoring", response_model=MonitoringResponse)
async def get_monitoring_data(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get system monitoring data including metrics, health status, and circuit breaker states.
    
    Requires admin role for access.
    
    Args:
        db: Database session
        current_admin: Current admin user
        
    Returns:
        System monitoring data with all metrics
    """
    # Calculate 24 hours ago
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    
    # Count total registered users
    total_users = db.query(func.count(User.id)).scalar() or 0
    
    # Count requests in last 24 hours
    requests_last_24h = (
        db.query(func.count(Request.id))
        .filter(Request.created_at >= twenty_four_hours_ago)
        .scalar() or 0
    )
    
    # Calculate average response time from completed requests in last 24 hours
    avg_response_time_result = (
        db.query(func.avg(Response.execution_time))
        .join(Request, Response.request_id == Request.id)
        .filter(Request.created_at >= twenty_four_hours_ago)
        .filter(Request.status == "completed")
        .scalar()
    )
    average_response_time = float(avg_response_time_result) if avg_response_time_result else 0.0
    
    # Calculate total cost in last 24 hours
    total_cost_result = (
        db.query(func.sum(Response.total_cost))
        .join(Request, Response.request_id == Request.id)
        .filter(Request.created_at >= twenty_four_hours_ago)
        .scalar()
    )
    total_cost_last_24h = float(total_cost_result) if total_cost_result else 0.0
    
    # Calculate success rate
    total_requests_24h = (
        db.query(func.count(Request.id))
        .filter(Request.created_at >= twenty_four_hours_ago)
        .filter(Request.status.in_(["completed", "failed"]))
        .scalar() or 0
    )
    
    successful_requests_24h = (
        db.query(func.count(Request.id))
        .filter(Request.created_at >= twenty_four_hours_ago)
        .filter(Request.status == "completed")
        .scalar() or 0
    )
    
    success_rate = (
        (successful_requests_24h / total_requests_24h) 
        if total_requests_24h > 0 
        else 1.0
    )
    
    # Count active WebSocket connections
    active_websockets = websocket_manager.get_active_connection_count()
    
    # Get provider health status (will be implemented in next subtask)
    provider_health = await _check_provider_health()
    
    # Get circuit breaker states
    circuit_breaker = get_circuit_breaker()
    providers = ["groq", "together", "openrouter", "huggingface"]
    
    circuit_breakers = {}
    for provider in providers:
        stats = circuit_breaker.get_stats(provider)
        circuit_breakers[provider] = CircuitBreakerStatus(
            state=stats["state"],
            failure_count=stats["failure_count"],
            timeout=stats["timeout"]
        )
    
    # Get provider cost breakdown for last 24 hours
    from app.services.provider_cost_tracker import get_provider_cost_tracker
    provider_cost_tracker = get_provider_cost_tracker()
    provider_cost_breakdown = await provider_cost_tracker.get_provider_costs_system_wide(
        db, start_date=twenty_four_hours_ago
    )
    
    return MonitoringResponse(
        total_users=total_users,
        requests_last_24h=requests_last_24h,
        average_response_time=average_response_time,
        total_cost_last_24h=total_cost_last_24h,
        success_rate=success_rate,
        active_websockets=active_websockets,
        provider_health=provider_health,
        circuit_breakers=circuit_breakers,
        provider_cost_breakdown=provider_cost_breakdown
    )


async def _check_provider_health() -> Dict[str, ProviderHealthStatus]:
    """
    Check health status of all cloud AI providers.
    
    Uses the ProviderHealthChecker service to ping each provider
    and cache results for 1 minute.
    
    Returns:
        Dictionary mapping provider names to health status
    """
    health_checker = get_health_checker()
    health_statuses = await health_checker.check_all_providers()
    
    # Convert to dictionary format for API response
    result = {}
    for provider, status in health_statuses.items():
        result[provider] = ProviderHealthStatus(
            status=status.status,
            last_check=status.last_check.isoformat(),
            response_time_ms=status.response_time_ms,
            error_message=status.error_message
        )
    
    return result



class MonthlyReportResponse(BaseModel):
    """Monthly cost report response."""
    year: int
    month: int
    month_name: str
    start_date: str
    end_date: str
    by_provider: List[Dict[str, Any]]
    total_cost: float
    total_requests: int
    estimated_savings: float
    free_provider_usage_percent: float


@router.get("/reports/monthly", response_model=MonthlyReportResponse)
async def get_monthly_cost_report(
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (defaults to current month)"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Generate monthly cost report by provider.
    
    Requires admin role for access.
    
    Args:
        year: Year (defaults to current year)
        month: Month (defaults to current month)
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Monthly cost report with provider breakdown
    """
    from app.services.provider_cost_tracker import get_provider_cost_tracker
    
    provider_cost_tracker = get_provider_cost_tracker()
    report = await provider_cost_tracker.get_monthly_cost_report(
        db, user_id=None, year=year, month=month
    )
    
    return MonthlyReportResponse(**report)


class CostThresholdResponse(BaseModel):
    """Cost threshold check response."""
    user_id: str
    period_days: int
    threshold: float
    total_cost: float
    exceeds_threshold: bool
    percentage_of_threshold: float
    by_provider: List[Dict[str, Any]]


@router.get("/costs/threshold/{user_id}", response_model=CostThresholdResponse)
async def check_user_cost_threshold(
    user_id: str,
    threshold: float = Query(10.0, ge=0, description="Cost threshold in USD"),
    period_days: int = Query(30, ge=1, le=365, description="Number of days to check"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Check if user's costs exceed threshold in the given period.
    
    Requires admin role for access.
    
    Args:
        user_id: User ID to check
        threshold: Cost threshold in USD
        period_days: Number of days to check
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Cost threshold check results
        
    Raises:
        HTTPException 400: If user ID is invalid
    """
    # Convert string UUID to UUID object
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    from app.services.provider_cost_tracker import get_provider_cost_tracker
    
    provider_cost_tracker = get_provider_cost_tracker()
    result = await provider_cost_tracker.check_cost_threshold(
        db, user_uuid, threshold, period_days
    )
    
    return CostThresholdResponse(**result)


class ProviderCostBreakdownResponse(BaseModel):
    """Provider cost breakdown response."""
    by_provider: List[Dict[str, Any]]
    total_cost: float
    total_requests: int
    estimated_savings: float
    free_provider_usage_percent: float


@router.get("/costs/providers", response_model=ProviderCostBreakdownResponse)
async def get_provider_cost_breakdown(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get system-wide provider cost breakdown.
    
    Requires admin role for access.
    
    Args:
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        db: Database session
        current_admin: Current admin user
        
    Returns:
        Provider cost breakdown
        
    Raises:
        HTTPException 400: If date format is invalid
    """
    from app.services.provider_cost_tracker import get_provider_cost_tracker
    
    # Parse dates if provided
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
            )
    
    provider_cost_tracker = get_provider_cost_tracker()
    breakdown = await provider_cost_tracker.get_provider_costs_system_wide(
        db, start_date=start_dt, end_date=end_dt
    )
    
    return ProviderCostBreakdownResponse(**breakdown)
