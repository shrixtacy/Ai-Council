"""Core data models and enumerations for AI Council."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4


class TaskType(Enum):
    """Types of tasks that can be processed by the system."""
    REASONING = "reasoning"
    RESEARCH = "research"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    CREATIVE_OUTPUT = "creative_output"
    IMAGE_GENERATION = "image_generation"
    FACT_CHECKING = "fact_checking"
    VERIFICATION = "verification"


class ExecutionMode(Enum):
    """Execution modes that determine routing decisions and resource allocation."""
    FAST = "fast"
    BALANCED = "balanced"
    BEST_QUALITY = "best_quality"


class RiskLevel(Enum):
    """Risk levels for tasks and assessments."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Priority(Enum):
    """Priority levels for subtasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplexityLevel(Enum):
    """Complexity levels for task analysis."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class TaskIntent(Enum):
    """Intent categories for user requests."""
    QUESTION = "question"
    INSTRUCTION = "instruction"
    ANALYSIS = "analysis"
    CREATION = "creation"
    MODIFICATION = "modification"
    VERIFICATION = "verification"


@dataclass
class Task:
    """Represents a user request that may be decomposed into subtasks."""
    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    intent: Optional[TaskIntent] = None
    complexity: Optional[ComplexityLevel] = None
    execution_mode: ExecutionMode = ExecutionMode.BALANCED
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate task data after initialization."""
        if not self.content.strip():
            raise ValueError("Task content cannot be empty")


@dataclass
class Subtask:
    """Represents an atomic unit of work decomposed from a complex task."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_task_id: str = ""
    content: str = ""
    task_type: Optional[TaskType] = None
    priority: Priority = Priority.MEDIUM
    risk_level: RiskLevel = RiskLevel.LOW
    accuracy_requirement: float = 0.8
    estimated_cost: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate subtask data after initialization."""
        if not self.content.strip():
            raise ValueError("Subtask content cannot be empty")
        if not (0.0 <= self.accuracy_requirement <= 1.0):
            raise ValueError("Accuracy requirement must be between 0.0 and 1.0")
        if self.estimated_cost < 0.0:
            raise ValueError("Estimated cost cannot be negative")


@dataclass
class SelfAssessment:
    """Structured metadata returned by execution agents about their performance."""
    confidence_score: float = 0.0
    assumptions: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    estimated_cost: float = 0.0
    token_usage: int = 0
    execution_time: float = 0.0
    model_used: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate self-assessment data after initialization."""
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        if self.estimated_cost < 0.0:
            raise ValueError("Estimated cost cannot be negative")
        if self.token_usage < 0:
            raise ValueError("Token usage cannot be negative")
        if self.execution_time < 0.0:
            raise ValueError("Execution time cannot be negative")


@dataclass
class AgentResponse:
    """Response from an execution agent including content and self-assessment."""
    subtask_id: str = ""
    model_used: str = ""
    content: str = ""
    self_assessment: Optional[SelfAssessment] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate agent response data after initialization."""
        if not self.subtask_id:
            raise ValueError("Subtask ID cannot be empty")
        if not self.model_used:
            raise ValueError("Model used cannot be empty")
        if self.success and not self.content.strip():
            raise ValueError("Successful response must have content")
        if not self.success and not self.error_message:
            raise ValueError("Failed response must have error message")


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for execution."""
    total_cost: float = 0.0
    model_costs: Dict[str, float] = field(default_factory=dict)
    token_usage: Dict[str, int] = field(default_factory=dict)
    execution_time: float = 0.0
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate cost breakdown data after initialization."""
        if self.total_cost < 0.0:
            raise ValueError("Total cost cannot be negative")
        if self.execution_time < 0.0:
            raise ValueError("Execution time cannot be negative")


@dataclass
class ExecutionMetadata:
    """Metadata about the execution process for explainability."""
    models_used: List[str] = field(default_factory=list)
    execution_path: List[str] = field(default_factory=list)
    arbitration_decisions: List[str] = field(default_factory=list)
    synthesis_notes: List[str] = field(default_factory=list)
    total_execution_time: float = 0.0
    parallel_executions: int = 0

    def __post_init__(self) -> None:
        """Validate execution metadata after initialization."""
        if self.total_execution_time < 0.0:
            raise ValueError("Total execution time cannot be negative")
        if self.parallel_executions < 0:
            raise ValueError("Parallel executions cannot be negative")


@dataclass
class FinalResponse:
    """Final synthesized response returned to the user."""
    content: str = ""
    overall_confidence: float = 0.0
    execution_metadata: Optional[ExecutionMetadata] = None
    cost_breakdown: Optional[CostBreakdown] = None
    models_used: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    error_type: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate final response data after initialization."""
        if not (0.0 <= self.overall_confidence <= 1.0):
            raise ValueError("Overall confidence must be between 0.0 and 1.0")
        if self.success and not self.content.strip():
            raise ValueError("Successful response must have content")
        if not self.success and not self.error_message:
            raise ValueError("Failed response must have error message")


# Model capability and configuration classes
@dataclass
class ModelCapabilities:
    """Capabilities and characteristics of an AI model."""
    task_types: List[TaskType] = field(default_factory=list)
    cost_per_token: float = 0.0
    average_latency: float = 0.0
    max_context_length: int = 0
    reliability_score: float = 0.0
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate model capabilities after initialization."""
        if self.cost_per_token < 0.0:
            raise ValueError("Cost per token cannot be negative")
        if self.average_latency < 0.0:
            raise ValueError("Average latency cannot be negative")
        if self.max_context_length < 0:
            raise ValueError("Max context length cannot be negative")
        if not (0.0 <= self.reliability_score <= 1.0):
            raise ValueError("Reliability score must be between 0.0 and 1.0")


@dataclass
class CostProfile:
    """Cost profile for a model."""
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    minimum_cost: float = 0.0
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate cost profile after initialization."""
        if self.cost_per_input_token < 0.0:
            raise ValueError("Cost per input token cannot be negative")
        if self.cost_per_output_token < 0.0:
            raise ValueError("Cost per output token cannot be negative")
        if self.minimum_cost < 0.0:
            raise ValueError("Minimum cost cannot be negative")


@dataclass
class PerformanceMetrics:
    """Performance metrics for a model."""
    average_response_time: float = 0.0
    success_rate: float = 0.0
    average_quality_score: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate performance metrics after initialization."""
        if self.average_response_time < 0.0:
            raise ValueError("Average response time cannot be negative")
        if not (0.0 <= self.success_rate <= 1.0):
            raise ValueError("Success rate must be between 0.0 and 1.0")
        if not (0.0 <= self.average_quality_score <= 1.0):
            raise ValueError("Average quality score must be between 0.0 and 1.0")
        if self.total_requests < 0:
            raise ValueError("Total requests cannot be negative")
        if self.failed_requests < 0:
            raise ValueError("Failed requests cannot be negative")
        if self.failed_requests > self.total_requests:
            raise ValueError("Failed requests cannot exceed total requests")