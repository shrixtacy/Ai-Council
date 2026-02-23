"""Abstract base classes and interfaces for AI Council system components."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from .models import (
    Task, Subtask, AgentResponse, FinalResponse, SelfAssessment,
    TaskIntent, ComplexityLevel, TaskType, ExecutionMode,
    ModelCapabilities, CostProfile, PerformanceMetrics
)


class AnalysisEngine(ABC):
    """Abstract base class for analyzing user input and determining task characteristics."""
    
    @abstractmethod
    async def analyze_intent(self, input_text: str) -> TaskIntent:
        """Analyze user input to determine the intent of the request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            TaskIntent: The determined intent category
        """
        pass
    
    @abstractmethod
    async def determine_complexity(self, input_text: str) -> ComplexityLevel:
        """Determine the complexity level of a user request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            ComplexityLevel: The determined complexity level
        """
        pass
    
    @abstractmethod
    async def classify_task_type(self, input_text: str) -> List[TaskType]:
        """Classify the types of tasks required to fulfill the request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            List[TaskType]: List of task types that may be needed
        """
        pass


class TaskDecomposer(ABC):
    """Abstract base class for decomposing complex tasks into subtasks."""
    
    @abstractmethod
    async def decompose(self, task: Task) -> List[Subtask]:
        """Decompose a complex task into smaller, atomic subtasks.
        
        Args:
            task: The task to decompose
            
        Returns:
            List[Subtask]: List of subtasks that together fulfill the original task
        """
        pass
    
    @abstractmethod
    async def assign_metadata(self, subtask: Subtask) -> Subtask:
        """Assign metadata to a subtask including priority, risk level, etc.
        
        Args:
            subtask: The subtask to assign metadata to
            
        Returns:
            Subtask: The subtask with updated metadata
        """
        pass
    
    @abstractmethod
    async def validate_decomposition(self, subtasks: List[Subtask]) -> bool:
        """Validate that a decomposition is complete and consistent.
        
        Args:
            subtasks: List of subtasks to validate
            
        Returns:
            bool: True if decomposition is valid, False otherwise
        """
        pass


class ModelSelection:
    """Represents a model selection decision."""
    
    def __init__(self, model_id: str, confidence: float = 1.0, reasoning: str = ""):
        self.model_id = model_id
        self.confidence = confidence
        self.reasoning = reasoning


class ExecutionPlan:
    """Represents an execution plan for multiple subtasks."""
    
    def __init__(self, parallel_groups: List[List[Subtask]], sequential_order: List[str]):
        self.parallel_groups = parallel_groups
        self.sequential_order = sequential_order


class ModelContextProtocol(ABC):
    """Abstract base class for intelligent task routing and model selection."""
    
    @abstractmethod
    async def route_task(self, subtask: Subtask) -> ModelSelection:
        """Route a subtask to the most appropriate model.
        
        Args:
            subtask: The subtask to route
            
        Returns:
            ModelSelection: The selected model and routing decision
        """
        pass
    
    @abstractmethod
    async def select_fallback(self, failed_model: str, subtask: Subtask) -> ModelSelection:
        """Select a fallback model when the primary model fails.
        
        Args:
            failed_model: ID of the model that failed
            subtask: The subtask that needs a fallback model
            
        Returns:
            ModelSelection: The fallback model selection
        """
        pass
    
    @abstractmethod
    async def determine_parallelism(self, subtasks: List[Subtask]) -> ExecutionPlan:
        """Determine which subtasks can be executed in parallel.
        
        Args:
            subtasks: List of subtasks to analyze for parallelism
            
        Returns:
            ExecutionPlan: Plan for parallel and sequential execution
        """
        pass


class AIModel(ABC):
    """Abstract base class for AI model implementations."""
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the AI model.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional model-specific parameters
            
        Returns:
            str: The generated response
        """
        pass
    
    @abstractmethod
    def get_model_id(self) -> str:
        """Get the unique identifier for this model.
        
        Returns:
            str: Model identifier
        """
        pass


class FailureResponse:
    """Represents a failure response from an execution agent."""
    
    def __init__(self, error_type: str, error_message: str, retry_suggested: bool = False):
        self.error_type = error_type
        self.error_message = error_message
        self.retry_suggested = retry_suggested


class ModelError(Exception):
    """Exception raised when a model fails to execute."""
    
    def __init__(self, model_id: str, error_message: str, error_type: str = "unknown"):
        self.model_id = model_id
        self.error_message = error_message
        self.error_type = error_type
        super().__init__(f"Model {model_id} failed: {error_message}")


class ExecutionAgent(ABC):
    """Abstract base class for agents that execute subtasks using AI models."""
    
    @abstractmethod
    async def execute(self, subtask: Subtask, model: AIModel) -> AgentResponse:
        """Execute a subtask using the specified AI model.
        
        Args:
            subtask: The subtask to execute
            model: The AI model to use for execution
            
        Returns:
            AgentResponse: The response including content and self-assessment
        """
        pass
    
    @abstractmethod
    async def generate_self_assessment(self, response: str, subtask: Subtask) -> SelfAssessment:
        """Generate a self-assessment of the agent's performance.
        
        Args:
            response: The generated response content
            subtask: The subtask that was executed
            
        Returns:
            SelfAssessment: Structured self-assessment metadata
        """
        pass
    
    @abstractmethod
    async def handle_model_failure(self, error: ModelError) -> FailureResponse:
        """Handle failures from the underlying AI model.
        
        Args:
            error: The model error that occurred
            
        Returns:
            FailureResponse: Information about the failure and suggested actions
        """
        pass


class Conflict:
    """Represents a conflict between multiple agent responses."""
    
    def __init__(self, response_ids: List[str], conflict_type: str, description: str):
        self.response_ids = response_ids
        self.conflict_type = conflict_type
        self.description = description


class Resolution:
    """Represents the resolution of a conflict."""
    
    def __init__(self, chosen_response_id: str, reasoning: str, confidence: float = 1.0):
        self.chosen_response_id = chosen_response_id
        self.reasoning = reasoning
        self.confidence = confidence


class ArbitrationResult:
    """Result of the arbitration process."""
    
    def __init__(self, validated_responses: List[AgentResponse], conflicts_resolved: List[Resolution]):
        self.validated_responses = validated_responses
        self.conflicts_resolved = conflicts_resolved


class ArbitrationLayer(ABC):
    """Abstract base class for arbitrating between multiple agent responses."""
    
    @abstractmethod
    async def arbitrate(self, responses: List[AgentResponse]) -> ArbitrationResult:
        """Arbitrate between multiple agent responses to resolve conflicts.
        
        Args:
            responses: List of agent responses to arbitrate
            
        Returns:
            ArbitrationResult: The result of arbitration with validated responses
        """
        pass
    
    @abstractmethod
    async def detect_conflicts(self, responses: List[AgentResponse]) -> List[Conflict]:
        """Detect conflicts between multiple agent responses.
        
        Args:
            responses: List of agent responses to analyze
            
        Returns:
            List[Conflict]: List of detected conflicts
        """
        pass
    
    @abstractmethod
    async def resolve_contradiction(self, conflict: Conflict) -> Resolution:
        """Resolve a specific contradiction between responses.
        
        Args:
            conflict: The conflict to resolve
            
        Returns:
            Resolution: The resolution decision
        """
        pass


class ExecutionMetadata:
    """Metadata about the execution process for explainability."""
    
    def __init__(self):
        self.models_used: List[str] = []
        self.execution_path: List[str] = []
        self.arbitration_decisions: List[str] = []
        self.synthesis_notes: List[str] = []
        self.total_execution_time: float = 0.0
        self.parallel_executions: int = 0


class SynthesisLayer(ABC):
    """Abstract base class for synthesizing final responses from validated outputs."""
    
    @abstractmethod
    async def synthesize(self, validated_responses: List[AgentResponse]) -> FinalResponse:
        """Synthesize a final response from validated agent responses.
        
        Args:
            validated_responses: List of validated agent responses
            
        Returns:
            FinalResponse: The final synthesized response
        """
        pass
    
    @abstractmethod
    async def normalize_output(self, content: str) -> str:
        """Normalize output content for consistency.
        
        Args:
            content: Raw content to normalize
            
        Returns:
            str: Normalized content
        """
        pass
    
    @abstractmethod
    async def attach_metadata(self, response: FinalResponse, metadata: ExecutionMetadata) -> FinalResponse:
        """Attach execution metadata to the final response.
        
        Args:
            response: The final response
            metadata: Execution metadata to attach
            
        Returns:
            FinalResponse: Response with attached metadata
        """
        pass


# Additional supporting interfaces

class ModelRegistry(ABC):
    """Abstract base class for managing AI model registry."""
    
    @abstractmethod
    def register_model(self, model: AIModel, capabilities: ModelCapabilities) -> None:
        """Register a new AI model with its capabilities.
        
        Args:
            model: The AI model to register
            capabilities: The model's capabilities and characteristics
        """
        pass
    
    @abstractmethod
    def get_models_for_task_type(self, task_type: TaskType) -> List[AIModel]:
        """Get all models capable of handling a specific task type.
        
        Args:
            task_type: The type of task
            
        Returns:
            List[AIModel]: List of capable models
        """
        pass
    
    @abstractmethod
    def get_model_cost_profile(self, model_id: str) -> CostProfile:
        """Get the cost profile for a specific model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            CostProfile: The model's cost profile
        """
        pass
    
    @abstractmethod
    def update_model_performance(self, model_id: str, performance: PerformanceMetrics) -> None:
        """Update performance metrics for a model.
        
        Args:
            model_id: The model identifier
            performance: Updated performance metrics
        """
        pass


class CostEstimate:
    """Represents a cost estimate for task execution."""
    
    def __init__(self, estimated_cost: float, estimated_time: float, confidence: float = 1.0):
        self.estimated_cost = estimated_cost
        self.estimated_time = estimated_time
        self.confidence = confidence


class ExecutionFailure:
    """Represents an execution failure."""
    
    def __init__(self, failure_type: str, error_message: str, subtask_id: str, model_id: str):
        self.failure_type = failure_type
        self.error_message = error_message
        self.subtask_id = subtask_id
        self.model_id = model_id


class FallbackStrategy:
    """Represents a fallback strategy for handling failures."""
    
    def __init__(self, strategy_type: str, alternative_model: Optional[str] = None, retry_count: int = 0):
        self.strategy_type = strategy_type
        self.alternative_model = alternative_model
        self.retry_count = retry_count


class OrchestrationLayer(ABC):
    """Abstract base class for the main orchestration layer."""
    
    @abstractmethod
    async def process_request(self, user_input: str, execution_mode: ExecutionMode) -> FinalResponse:
        """Process a user request through the entire pipeline.
        
        Args:
            user_input: Raw user input
            execution_mode: The execution mode to use
            
        Returns:
            FinalResponse: The final processed response
        """
        pass
    
    @abstractmethod
    async def estimate_cost_and_time(self, task: Task) -> CostEstimate:
        """Estimate the cost and time for executing a task.
        
        Args:
            task: The task to estimate
            
        Returns:
            CostEstimate: Cost and time estimates
        """
        pass
    
    @abstractmethod
    async def handle_failure(self, failure: ExecutionFailure) -> FallbackStrategy:
        """Handle execution failures with appropriate fallback strategies.
        
        Args:
            failure: The execution failure that occurred
            
        Returns:
            FallbackStrategy: The recommended fallback strategy
        """
        pass