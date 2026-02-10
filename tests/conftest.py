"""
Pytest fixtures and configuration for AI Council tests.

This module provides shared fixtures used across all test modules,
including mock objects, sample data, and configuration helpers.
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import tempfile
import yaml

from ai_council.core.models import (
    Task, Subtask, SelfAssessment, AgentResponse, FinalResponse,
    TaskType, ExecutionMode, RiskLevel, Priority, ComplexityLevel,
    TaskIntent, CostBreakdown, ExecutionMetadata, ModelCapabilities,
    CostProfile, PerformanceMetrics
)
from ai_council.utils.config import AICouncilConfig, ModelConfig, ExecutionConfig


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_task_content() -> str:
    """Provide sample task content for testing."""
    return "Analyze the benefits and drawbacks of renewable energy adoption"


@pytest.fixture
def sample_task(sample_task_content: str) -> Task:
    """Create a sample Task instance for testing."""
    return Task(
        content=sample_task_content,
        intent=TaskIntent.ANALYSIS,
        complexity=ComplexityLevel.MODERATE,
        execution_mode=ExecutionMode.BALANCED
    )


@pytest.fixture
def sample_subtask(sample_task: Task) -> Subtask:
    """Create a sample Subtask instance for testing."""
    return Subtask(
        parent_task_id=sample_task.id,
        content="Research current renewable energy technologies",
        task_type=TaskType.RESEARCH,
        priority=Priority.HIGH,
        risk_level=RiskLevel.LOW,
        accuracy_requirement=0.9
    )


@pytest.fixture
def sample_self_assessment() -> SelfAssessment:
    """Create a sample SelfAssessment instance for testing."""
    return SelfAssessment(
        confidence_score=0.85,
        assumptions=["Data is from 2024", "US market focus"],
        risk_level=RiskLevel.LOW,
        estimated_cost=0.05,
        token_usage=500,
        execution_time=2.5,
        model_used="gemini-2.5-flash"
    )


@pytest.fixture
def sample_agent_response(sample_subtask: Subtask, sample_self_assessment: SelfAssessment) -> AgentResponse:
    """Create a sample AgentResponse instance for testing."""
    return AgentResponse(
        subtask_id=sample_subtask.id,
        model_used="gemini-2.5-flash",
        content="Renewable energy technologies include solar, wind, and hydroelectric power.",
        self_assessment=sample_self_assessment,
        success=True
    )


@pytest.fixture
def sample_cost_breakdown() -> CostBreakdown:
    """Create a sample CostBreakdown instance for testing."""
    return CostBreakdown(
        total_cost=0.15,
        model_costs={"gemini-2.5-flash": 0.10, "grok-beta": 0.05},
        token_usage={"gemini-2.5-flash": 1000, "grok-beta": 500},
        execution_time=5.5,
        currency="USD"
    )


@pytest.fixture
def sample_execution_metadata() -> ExecutionMetadata:
    """Create a sample ExecutionMetadata instance for testing."""
    return ExecutionMetadata(
        models_used=["gemini-2.5-flash", "grok-beta"],
        execution_path=["analysis", "decomposition", "execution", "synthesis"],
        arbitration_decisions=["Selected highest confidence response"],
        synthesis_notes=["Combined responses from 2 models"],
        total_execution_time=5.5,
        parallel_executions=2
    )


@pytest.fixture
def sample_final_response(
    sample_cost_breakdown: CostBreakdown,
    sample_execution_metadata: ExecutionMetadata
) -> FinalResponse:
    """Create a sample FinalResponse instance for testing."""
    return FinalResponse(
        content="Renewable energy offers significant environmental benefits...",
        overall_confidence=0.88,
        execution_metadata=sample_execution_metadata,
        cost_breakdown=sample_cost_breakdown,
        models_used=["gemini-2.5-flash", "grok-beta"],
        success=True
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def sample_model_config() -> ModelConfig:
    """Create a sample ModelConfig instance for testing."""
    return ModelConfig(
        name="test-model",
        provider="test-provider",
        api_key_env="TEST_API_KEY",
        max_retries=3,
        timeout_seconds=30.0,
        cost_per_input_token=0.00001,
        cost_per_output_token=0.00003,
        max_context_length=8192,
        capabilities=["reasoning", "code_generation"],
        enabled=True,
        reliability_score=0.9,
        average_latency=1.5
    )


@pytest.fixture
def sample_execution_config() -> ExecutionConfig:
    """Create a sample ExecutionConfig instance for testing."""
    return ExecutionConfig(
        default_mode=ExecutionMode.BALANCED,
        max_parallel_executions=5,
        default_timeout_seconds=60.0,
        max_retries=3,
        enable_arbitration=True,
        enable_synthesis=True,
        default_accuracy_requirement=0.8
    )


@pytest.fixture
def sample_config_dict() -> Dict[str, Any]:
    """Provide a sample configuration dictionary for testing."""
    return {
        "execution": {
            "default_mode": "balanced",
            "max_parallel_executions": 5,
            "max_retries": 3,
            "default_timeout_seconds": 60.0,
            "enable_arbitration": True,
            "enable_synthesis": True
        },
        "cost": {
            "max_cost_per_request": 1.0,
            "currency": "USD",
            "enable_cost_tracking": True
        },
        "logging": {
            "level": "INFO",
            "format_json": False
        },
        "models": {
            "test-model": {
                "enabled": True,
                "provider": "test",
                "api_key_env": "TEST_API_KEY",
                "capabilities": ["reasoning"],
                "cost_per_input_token": 0.00001,
                "cost_per_output_token": 0.00003,
                "max_context_length": 8192
            }
        }
    }


@pytest.fixture
def temp_config_file(sample_config_dict: Dict[str, Any]) -> Path:
    """Create a temporary configuration file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config_dict, f)
        return Path(f.name)


# =============================================================================
# Model Capability Fixtures
# =============================================================================

@pytest.fixture
def sample_model_capabilities() -> ModelCapabilities:
    """Create sample ModelCapabilities for testing."""
    return ModelCapabilities(
        task_types=[TaskType.REASONING, TaskType.CODE_GENERATION],
        cost_per_token=0.00002,
        average_latency=1.5,
        max_context_length=8192,
        reliability_score=0.9,
        strengths=["Fast responses", "Good at coding"],
        weaknesses=["Limited context window"]
    )


@pytest.fixture
def sample_cost_profile() -> CostProfile:
    """Create sample CostProfile for testing."""
    return CostProfile(
        cost_per_input_token=0.00001,
        cost_per_output_token=0.00003,
        minimum_cost=0.0,
        currency="USD"
    )


@pytest.fixture
def sample_performance_metrics() -> PerformanceMetrics:
    """Create sample PerformanceMetrics for testing."""
    return PerformanceMetrics(
        average_response_time=1.5,
        success_rate=0.95,
        average_quality_score=0.88,
        total_requests=100,
        failed_requests=5
    )


# =============================================================================
# Helper Functions
# =============================================================================

def create_task_with_mode(content: str, mode: ExecutionMode) -> Task:
    """Helper to create a Task with a specific execution mode."""
    return Task(content=content, execution_mode=mode)


def create_subtask_with_type(parent_id: str, content: str, task_type: TaskType) -> Subtask:
    """Helper to create a Subtask with a specific task type."""
    return Subtask(parent_task_id=parent_id, content=content, task_type=task_type)
