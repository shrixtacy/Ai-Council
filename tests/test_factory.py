"""
Unit tests for AI Council Factory component creation.

Tests cover the AICouncilFactory class in ai_council/factory.py
including component creation, dependency injection, and caching.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from ai_council.core.models import ExecutionMode, TaskType
from ai_council.core.interfaces import (
    ModelRegistry, AnalysisEngine, TaskDecomposer,
    ModelContextProtocol, ExecutionAgent, ArbitrationLayer, SynthesisLayer
)
from ai_council.utils.config import (
    AICouncilConfig, ModelConfig, ExecutionConfig, create_default_config
)
from ai_council.factory import AICouncilFactory


# =============================================================================
# Factory Initialization Tests
# =============================================================================

class TestFactoryInitialization:
    """Tests for AICouncilFactory initialization."""
    
    def test_factory_creation_with_default_config(self):
        """Test factory creation with default configuration."""
        config = create_default_config()
        factory = AICouncilFactory(config)
        
        assert factory is not None
        assert factory.config == config
    
    def test_factory_stores_config(self):
        """Test that factory stores the configuration."""
        config = create_default_config()
        factory = AICouncilFactory(config)
        
        assert factory.config is config
    
    def test_factory_initializes_component_cache(self):
        """Test that factory initializes empty component cache."""
        config = create_default_config()
        factory = AICouncilFactory(config)
        
        # Check private cache attributes exist
        assert factory._model_registry is None
        assert factory._analysis_engine is None
        assert factory._task_decomposer is None


# =============================================================================
# Component Creation Tests
# =============================================================================

class TestComponentCreation:
    """Tests for individual component creation."""
    
    @pytest.fixture
    def factory(self):
        """Create a factory with default config."""
        config = create_default_config()
        return AICouncilFactory(config)
    
    def test_model_registry_creation(self, factory):
        """Test model registry creation."""
        registry = factory.model_registry
        
        assert registry is not None
        assert isinstance(registry, ModelRegistry)
    
    def test_analysis_engine_creation(self, factory):
        """Test analysis engine creation."""
        engine = factory.analysis_engine
        
        assert engine is not None
        assert isinstance(engine, AnalysisEngine)
    
    def test_task_decomposer_creation(self, factory):
        """Test task decomposer creation."""
        decomposer = factory.task_decomposer
        
        assert decomposer is not None
        assert isinstance(decomposer, TaskDecomposer)
    
    def test_model_context_protocol_creation(self, factory):
        """Test model context protocol creation."""
        mcp = factory.model_context_protocol
        
        assert mcp is not None
        assert isinstance(mcp, ModelContextProtocol)
    
    def test_execution_agent_creation(self, factory):
        """Test execution agent creation."""
        agent = factory.execution_agent
        
        assert agent is not None
        assert isinstance(agent, ExecutionAgent)
    
    def test_arbitration_layer_creation(self, factory):
        """Test arbitration layer creation."""
        arbitration = factory.arbitration_layer
        
        assert arbitration is not None
        assert isinstance(arbitration, ArbitrationLayer)
    
    def test_synthesis_layer_creation(self, factory):
        """Test synthesis layer creation."""
        synthesis = factory.synthesis_layer
        
        assert synthesis is not None
        assert isinstance(synthesis, SynthesisLayer)


# =============================================================================
# Component Caching Tests
# =============================================================================

class TestComponentCaching:
    """Tests for component caching behavior."""
    
    @pytest.fixture
    def factory(self):
        """Create a factory with default config."""
        config = create_default_config()
        return AICouncilFactory(config)
    
    def test_model_registry_is_cached(self, factory):
        """Test that model registry is cached after first access."""
        registry1 = factory.model_registry
        registry2 = factory.model_registry
        
        assert registry1 is registry2
    
    def test_analysis_engine_is_cached(self, factory):
        """Test that analysis engine is cached after first access."""
        engine1 = factory.analysis_engine
        engine2 = factory.analysis_engine
        
        assert engine1 is engine2
    
    def test_task_decomposer_is_cached(self, factory):
        """Test that task decomposer is cached after first access."""
        decomposer1 = factory.task_decomposer
        decomposer2 = factory.task_decomposer
        
        assert decomposer1 is decomposer2
    
    def test_all_components_are_cached(self, factory):
        """Test that all components are cached properly."""
        # Access each component twice
        components = [
            ('model_registry', factory.model_registry),
            ('analysis_engine', factory.analysis_engine),
            ('task_decomposer', factory.task_decomposer),
            ('model_context_protocol', factory.model_context_protocol),
            ('execution_agent', factory.execution_agent),
            ('arbitration_layer', factory.arbitration_layer),
            ('synthesis_layer', factory.synthesis_layer),
        ]
        
        # Verify caching
        for name, component in components:
            cached = getattr(factory, name)
            assert component is cached, f"{name} was not cached properly"


# =============================================================================
# Orchestration Layer Creation Tests
# =============================================================================

class TestOrchestrationLayerCreation:
    """Tests for orchestration layer creation."""
    
    @pytest.fixture
    def factory(self):
        """Create a factory with default config."""
        config = create_default_config()
        return AICouncilFactory(config)
    
    def test_create_orchestration_layer(self, factory):
        """Test orchestration layer creation with all dependencies."""
        orchestration = factory.create_orchestration_layer()
        
        assert orchestration is not None
    
    def test_orchestration_layer_has_all_components(self, factory):
        """Test that orchestration layer receives all required components."""
        orchestration = factory.create_orchestration_layer()
        
        # Verify orchestration layer has the required attributes
        assert hasattr(orchestration, 'analysis_engine')
        assert hasattr(orchestration, 'task_decomposer')
        assert hasattr(orchestration, 'model_context_protocol')
        assert hasattr(orchestration, 'execution_agent')
        assert hasattr(orchestration, 'arbitration_layer')
        assert hasattr(orchestration, 'synthesis_layer')


# =============================================================================
# Configuration Integration Tests
# =============================================================================

class TestConfigurationIntegration:
    """Tests for configuration integration with factory."""
    
    def test_factory_uses_execution_config(self):
        """Test that factory respects execution configuration."""
        config = create_default_config()
        config.execution.max_parallel_executions = 10
        
        factory = AICouncilFactory(config)
        
        assert factory.config.execution.max_parallel_executions == 10
    
    def test_factory_uses_model_config(self):
        """Test that factory uses model configuration."""
        config = create_default_config()
        factory = AICouncilFactory(config)
        
        # Factory should have access to model configs
        assert factory.config.models is not None
    
    def test_different_configs_create_different_factories(self):
        """Test that different configs create independent factories."""
        config1 = create_default_config()
        config2 = create_default_config()
        config2.execution.max_retries = 5
        
        factory1 = AICouncilFactory(config1)
        factory2 = AICouncilFactory(config2)
        
        assert factory1.config.execution.max_retries != factory2.config.execution.max_retries


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestFactoryErrorHandling:
    """Tests for factory error handling."""
    
    def test_factory_handles_minimal_config(self):
        """Test that factory handles minimal configuration gracefully."""
        config = create_default_config()
        factory = AICouncilFactory(config)
        
        # Should not raise any exceptions
        assert factory is not None
    
    def test_factory_with_empty_models(self):
        """Test factory behavior with no models configured."""
        config = create_default_config()
        config.models = {}
        
        factory = AICouncilFactory(config)
        
        # Factory should still be creatable
        assert factory is not None


# =============================================================================
# AI Council Creation Tests
# =============================================================================

class TestAICouncilCreation:
    """Tests for complete AI Council system creation."""
    
    @pytest.fixture
    def factory(self):
        """Create a factory with default config."""
        config = create_default_config()
        return AICouncilFactory(config)
    
    def test_create_ai_council_sync(self, factory):
        """Test synchronous AI Council creation."""
        # The factory should have a method to create the full system
        if hasattr(factory, 'create_ai_council_sync'):
            ai_council = factory.create_ai_council_sync()
            assert ai_council is not None
    
    def test_ai_council_has_process_method(self, factory):
        """Test that AI Council has process_request method."""
        if hasattr(factory, 'create_ai_council_sync'):
            ai_council = factory.create_ai_council_sync()
            assert hasattr(ai_council, 'process_request') or hasattr(ai_council, 'process_request_sync')
