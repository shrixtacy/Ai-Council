"""
Unit tests for AI Council core data models.

Tests cover all dataclasses in ai_council/core/models.py including:
- Enumerations (TaskType, ExecutionMode, RiskLevel, Priority, etc.)
- Data models (Task, Subtask, SelfAssessment, AgentResponse, FinalResponse)
- Validation logic in __post_init__ methods
- Edge cases and error handling
"""

import pytest
from datetime import datetime
from uuid import UUID

from ai_council.core.models import (
    # Enums
    TaskType, ExecutionMode, RiskLevel, Priority, ComplexityLevel, TaskIntent,
    # Core models
    Task, Subtask, SelfAssessment, AgentResponse, FinalResponse,
    CostBreakdown, ExecutionMetadata,
    # Configuration models
    ModelCapabilities, CostProfile, PerformanceMetrics
)


# =============================================================================
# Enumeration Tests
# =============================================================================

class TestEnumerations:
    """Tests for all enumeration types."""
    
    def test_task_type_values(self):
        """Verify all TaskType enum values exist."""
        assert TaskType.REASONING.value == "reasoning"
        assert TaskType.RESEARCH.value == "research"
        assert TaskType.CODE_GENERATION.value == "code_generation"
        assert TaskType.DEBUGGING.value == "debugging"
        assert TaskType.CREATIVE_OUTPUT.value == "creative_output"
        assert TaskType.IMAGE_GENERATION.value == "image_generation"
        assert TaskType.FACT_CHECKING.value == "fact_checking"
        assert TaskType.VERIFICATION.value == "verification"
    
    def test_execution_mode_values(self):
        """Verify all ExecutionMode enum values exist."""
        assert ExecutionMode.FAST.value == "fast"
        assert ExecutionMode.BALANCED.value == "balanced"
        assert ExecutionMode.BEST_QUALITY.value == "best_quality"
    
    def test_risk_level_values(self):
        """Verify all RiskLevel enum values exist."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"
    
    def test_priority_values(self):
        """Verify all Priority enum values exist."""
        assert Priority.LOW.value == "low"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.HIGH.value == "high"
        assert Priority.CRITICAL.value == "critical"
    
    def test_complexity_level_values(self):
        """Verify all ComplexityLevel enum values exist."""
        assert ComplexityLevel.TRIVIAL.value == "trivial"
        assert ComplexityLevel.SIMPLE.value == "simple"
        assert ComplexityLevel.MODERATE.value == "moderate"
        assert ComplexityLevel.COMPLEX.value == "complex"
        assert ComplexityLevel.VERY_COMPLEX.value == "very_complex"
    
    def test_task_intent_values(self):
        """Verify all TaskIntent enum values exist."""
        assert TaskIntent.QUESTION.value == "question"
        assert TaskIntent.INSTRUCTION.value == "instruction"
        assert TaskIntent.ANALYSIS.value == "analysis"
        assert TaskIntent.CREATION.value == "creation"
        assert TaskIntent.MODIFICATION.value == "modification"
        assert TaskIntent.VERIFICATION.value == "verification"


# =============================================================================
# Task Model Tests
# =============================================================================

class TestTask:
    """Tests for the Task dataclass."""
    
    def test_task_creation_with_defaults(self):
        """Test Task creation with minimal required fields."""
        task = Task(content="Test task content")
        
        assert task.content == "Test task content"
        assert task.execution_mode == ExecutionMode.BALANCED
        assert task.intent is None
        assert task.complexity is None
        assert isinstance(task.id, str)
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.metadata, dict)
    
    def test_task_creation_with_all_fields(self, sample_task_content):
        """Test Task creation with all fields specified."""
        task = Task(
            content=sample_task_content,
            intent=TaskIntent.ANALYSIS,
            complexity=ComplexityLevel.MODERATE,
            execution_mode=ExecutionMode.BEST_QUALITY,
            metadata={"source": "test"}
        )
        
        assert task.content == sample_task_content
        assert task.intent == TaskIntent.ANALYSIS
        assert task.complexity == ComplexityLevel.MODERATE
        assert task.execution_mode == ExecutionMode.BEST_QUALITY
        assert task.metadata == {"source": "test"}
    
    def test_task_id_is_valid_uuid(self):
        """Test that Task ID is a valid UUID string."""
        task = Task(content="Test content")
        # Should not raise an exception
        UUID(task.id)
    
    def test_task_empty_content_raises_error(self):
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="Task content cannot be empty"):
            Task(content="")
    
    def test_task_whitespace_content_raises_error(self):
        """Test that whitespace-only content raises ValueError."""
        with pytest.raises(ValueError, match="Task content cannot be empty"):
            Task(content="   \n\t  ")
    
    def test_task_different_execution_modes(self):
        """Test Task creation with different execution modes."""
        for mode in ExecutionMode:
            task = Task(content="Test", execution_mode=mode)
            assert task.execution_mode == mode


# =============================================================================
# Subtask Model Tests
# =============================================================================

class TestSubtask:
    """Tests for the Subtask dataclass."""
    
    def test_subtask_creation_with_defaults(self):
        """Test Subtask creation with minimal required fields."""
        subtask = Subtask(parent_task_id="parent-123", content="Test subtask")
        
        assert subtask.parent_task_id == "parent-123"
        assert subtask.content == "Test subtask"
        assert subtask.priority == Priority.MEDIUM
        assert subtask.risk_level == RiskLevel.LOW
        assert subtask.accuracy_requirement == 0.8
        assert subtask.estimated_cost == 0.0
    
    def test_subtask_creation_with_all_fields(self):
        """Test Subtask creation with all fields specified."""
        subtask = Subtask(
            parent_task_id="parent-123",
            content="Research task",
            task_type=TaskType.RESEARCH,
            priority=Priority.HIGH,
            risk_level=RiskLevel.MEDIUM,
            accuracy_requirement=0.95,
            estimated_cost=0.10,
            metadata={"category": "research"}
        )
        
        assert subtask.task_type == TaskType.RESEARCH
        assert subtask.priority == Priority.HIGH
        assert subtask.risk_level == RiskLevel.MEDIUM
        assert subtask.accuracy_requirement == 0.95
        assert subtask.estimated_cost == 0.10
    
    def test_subtask_empty_content_raises_error(self):
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="Subtask content cannot be empty"):
            Subtask(parent_task_id="parent-123", content="")
    
    def test_subtask_accuracy_below_zero_raises_error(self):
        """Test that accuracy below 0 raises ValueError."""
        with pytest.raises(ValueError, match="Accuracy requirement must be between 0.0 and 1.0"):
            Subtask(parent_task_id="parent-123", content="Test", accuracy_requirement=-0.1)
    
    def test_subtask_accuracy_above_one_raises_error(self):
        """Test that accuracy above 1 raises ValueError."""
        with pytest.raises(ValueError, match="Accuracy requirement must be between 0.0 and 1.0"):
            Subtask(parent_task_id="parent-123", content="Test", accuracy_requirement=1.1)
    
    def test_subtask_negative_cost_raises_error(self):
        """Test that negative estimated cost raises ValueError."""
        with pytest.raises(ValueError, match="Estimated cost cannot be negative"):
            Subtask(parent_task_id="parent-123", content="Test", estimated_cost=-0.01)
    
    def test_subtask_boundary_accuracy_values(self):
        """Test boundary values for accuracy requirement."""
        # Should not raise
        subtask_zero = Subtask(parent_task_id="p", content="Test", accuracy_requirement=0.0)
        subtask_one = Subtask(parent_task_id="p", content="Test", accuracy_requirement=1.0)
        
        assert subtask_zero.accuracy_requirement == 0.0
        assert subtask_one.accuracy_requirement == 1.0


# =============================================================================
# SelfAssessment Model Tests
# =============================================================================

class TestSelfAssessment:
    """Tests for the SelfAssessment dataclass."""
    
    def test_self_assessment_creation_with_defaults(self):
        """Test SelfAssessment creation with defaults."""
        assessment = SelfAssessment()
        
        assert assessment.confidence_score == 0.0
        assert assessment.assumptions == []
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.estimated_cost == 0.0
        assert assessment.token_usage == 0
        assert assessment.execution_time == 0.0
    
    def test_self_assessment_with_all_fields(self, sample_self_assessment):
        """Test SelfAssessment with all fields populated."""
        assert sample_self_assessment.confidence_score == 0.85
        assert len(sample_self_assessment.assumptions) == 2
        assert sample_self_assessment.model_used == "gemini-2.5-flash"
    
    def test_confidence_below_zero_raises_error(self):
        """Test that confidence below 0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            SelfAssessment(confidence_score=-0.1)
    
    def test_confidence_above_one_raises_error(self):
        """Test that confidence above 1 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            SelfAssessment(confidence_score=1.1)
    
    def test_negative_cost_raises_error(self):
        """Test that negative cost raises ValueError."""
        with pytest.raises(ValueError, match="Estimated cost cannot be negative"):
            SelfAssessment(estimated_cost=-0.01)
    
    def test_negative_token_usage_raises_error(self):
        """Test that negative token usage raises ValueError."""
        with pytest.raises(ValueError, match="Token usage cannot be negative"):
            SelfAssessment(token_usage=-1)
    
    def test_negative_execution_time_raises_error(self):
        """Test that negative execution time raises ValueError."""
        with pytest.raises(ValueError, match="Execution time cannot be negative"):
            SelfAssessment(execution_time=-0.1)


# =============================================================================
# AgentResponse Model Tests
# =============================================================================

class TestAgentResponse:
    """Tests for the AgentResponse dataclass."""
    
    def test_agent_response_successful(self, sample_agent_response):
        """Test successful AgentResponse creation."""
        assert sample_agent_response.success is True
        assert sample_agent_response.content != ""
        assert sample_agent_response.model_used == "gemini-2.5-flash"
    
    def test_agent_response_failed_with_error(self):
        """Test failed AgentResponse with error message."""
        response = AgentResponse(
            subtask_id="subtask-123",
            model_used="test-model",
            content="",
            success=False,
            error_message="API rate limit exceeded"
        )
        
        assert response.success is False
        assert response.error_message == "API rate limit exceeded"
    
    def test_empty_subtask_id_raises_error(self):
        """Test that empty subtask_id raises ValueError."""
        with pytest.raises(ValueError, match="Subtask ID cannot be empty"):
            AgentResponse(subtask_id="", model_used="model", content="content")
    
    def test_empty_model_used_raises_error(self):
        """Test that empty model_used raises ValueError."""
        with pytest.raises(ValueError, match="Model used cannot be empty"):
            AgentResponse(subtask_id="id", model_used="", content="content")
    
    def test_successful_response_without_content_raises_error(self):
        """Test that successful response without content raises ValueError."""
        with pytest.raises(ValueError, match="Successful response must have content"):
            AgentResponse(subtask_id="id", model_used="model", content="", success=True)
    
    def test_failed_response_without_error_message_raises_error(self):
        """Test that failed response without error message raises ValueError."""
        with pytest.raises(ValueError, match="Failed response must have error message"):
            AgentResponse(subtask_id="id", model_used="model", content="", success=False)


# =============================================================================
# CostBreakdown Model Tests
# =============================================================================

class TestCostBreakdown:
    """Tests for the CostBreakdown dataclass."""
    
    def test_cost_breakdown_creation(self, sample_cost_breakdown):
        """Test CostBreakdown creation."""
        assert sample_cost_breakdown.total_cost == 0.15
        assert len(sample_cost_breakdown.model_costs) == 2
        assert sample_cost_breakdown.currency == "USD"
    
    def test_negative_total_cost_raises_error(self):
        """Test that negative total cost raises ValueError."""
        with pytest.raises(ValueError, match="Total cost cannot be negative"):
            CostBreakdown(total_cost=-0.01)
    
    def test_negative_execution_time_raises_error(self):
        """Test that negative execution time raises ValueError."""
        with pytest.raises(ValueError, match="Execution time cannot be negative"):
            CostBreakdown(execution_time=-1.0)


# =============================================================================
# ExecutionMetadata Model Tests
# =============================================================================

class TestExecutionMetadata:
    """Tests for the ExecutionMetadata dataclass."""
    
    def test_execution_metadata_creation(self, sample_execution_metadata):
        """Test ExecutionMetadata creation."""
        assert len(sample_execution_metadata.models_used) == 2
        assert sample_execution_metadata.parallel_executions == 2
    
    def test_negative_execution_time_raises_error(self):
        """Test that negative execution time raises ValueError."""
        with pytest.raises(ValueError, match="Total execution time cannot be negative"):
            ExecutionMetadata(total_execution_time=-1.0)
    
    def test_negative_parallel_executions_raises_error(self):
        """Test that negative parallel executions raises ValueError."""
        with pytest.raises(ValueError, match="Parallel executions cannot be negative"):
            ExecutionMetadata(parallel_executions=-1)


# =============================================================================
# FinalResponse Model Tests
# =============================================================================

class TestFinalResponse:
    """Tests for the FinalResponse dataclass."""
    
    def test_final_response_successful(self, sample_final_response):
        """Test successful FinalResponse creation."""
        assert sample_final_response.success is True
        assert sample_final_response.overall_confidence == 0.88
        assert len(sample_final_response.models_used) == 2
    
    def test_final_response_failed(self):
        """Test failed FinalResponse creation."""
        response = FinalResponse(
            content="",
            overall_confidence=0.0,
            success=False,
            error_message="Processing failed"
        )
        
        assert response.success is False
        assert response.error_message == "Processing failed"
    
    def test_confidence_out_of_range_raises_error(self):
        """Test that confidence out of range raises ValueError."""
        with pytest.raises(ValueError, match="Overall confidence must be between 0.0 and 1.0"):
            FinalResponse(content="Test", overall_confidence=1.5)
    
    def test_successful_without_content_raises_error(self):
        """Test that successful response without content raises ValueError."""
        with pytest.raises(ValueError, match="Successful response must have content"):
            FinalResponse(content="", overall_confidence=0.5, success=True)
    
    def test_failed_without_error_message_raises_error(self):
        """Test that failed response without error message raises ValueError."""
        with pytest.raises(ValueError, match="Failed response must have error message"):
            FinalResponse(content="", overall_confidence=0.0, success=False)


# =============================================================================
# ModelCapabilities Model Tests
# =============================================================================

class TestModelCapabilities:
    """Tests for the ModelCapabilities dataclass."""
    
    def test_model_capabilities_creation(self, sample_model_capabilities):
        """Test ModelCapabilities creation."""
        assert len(sample_model_capabilities.task_types) == 2
        assert sample_model_capabilities.reliability_score == 0.9
    
    def test_negative_cost_per_token_raises_error(self):
        """Test that negative cost per token raises ValueError."""
        with pytest.raises(ValueError, match="Cost per token cannot be negative"):
            ModelCapabilities(cost_per_token=-0.001)
    
    def test_reliability_out_of_range_raises_error(self):
        """Test that reliability score out of range raises ValueError."""
        with pytest.raises(ValueError, match="Reliability score must be between 0.0 and 1.0"):
            ModelCapabilities(reliability_score=1.5)


# =============================================================================
# CostProfile Model Tests
# =============================================================================

class TestCostProfile:
    """Tests for the CostProfile dataclass."""
    
    def test_cost_profile_creation(self, sample_cost_profile):
        """Test CostProfile creation."""
        assert sample_cost_profile.cost_per_input_token == 0.00001
        assert sample_cost_profile.currency == "USD"
    
    def test_negative_input_cost_raises_error(self):
        """Test that negative input cost raises ValueError."""
        with pytest.raises(ValueError, match="Cost per input token cannot be negative"):
            CostProfile(cost_per_input_token=-0.001)
    
    def test_negative_output_cost_raises_error(self):
        """Test that negative output cost raises ValueError."""
        with pytest.raises(ValueError, match="Cost per output token cannot be negative"):
            CostProfile(cost_per_output_token=-0.001)


# =============================================================================
# PerformanceMetrics Model Tests
# =============================================================================

class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics dataclass."""
    
    def test_performance_metrics_creation(self, sample_performance_metrics):
        """Test PerformanceMetrics creation."""
        assert sample_performance_metrics.success_rate == 0.95
        assert sample_performance_metrics.total_requests == 100
        assert sample_performance_metrics.failed_requests == 5
    
    def test_success_rate_out_of_range_raises_error(self):
        """Test that success rate out of range raises ValueError."""
        with pytest.raises(ValueError, match="Success rate must be between 0.0 and 1.0"):
            PerformanceMetrics(success_rate=1.5)
    
    def test_failed_exceeds_total_raises_error(self):
        """Test that failed requests exceeding total raises ValueError."""
        with pytest.raises(ValueError, match="Failed requests cannot exceed total requests"):
            PerformanceMetrics(total_requests=10, failed_requests=15)
    
    def test_negative_total_requests_raises_error(self):
        """Test that negative total requests raises ValueError."""
        with pytest.raises(ValueError, match="Total requests cannot be negative"):
            PerformanceMetrics(total_requests=-1)
