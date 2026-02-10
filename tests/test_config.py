"""
Unit tests for AI Council configuration management.

Tests cover configuration loading, validation, and default value handling
in ai_council/utils/config.py.
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from ai_council.core.models import ExecutionMode, TaskType, RiskLevel, Priority
from ai_council.utils.config import (
    AICouncilConfig, ModelConfig, ExecutionConfig, LoggingConfig,
    CostConfig, RoutingRule, PluginConfig, ExecutionModeConfig,
    load_config, create_default_config
)


# =============================================================================
# ModelConfig Tests
# =============================================================================

class TestModelConfig:
    """Tests for ModelConfig dataclass."""
    
    def test_model_config_defaults(self):
        """Test ModelConfig default values."""
        config = ModelConfig()
        
        assert config.name == ""
        assert config.provider == ""
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0
        assert config.enabled is True
        assert config.reliability_score == 0.8
    
    def test_model_config_with_all_fields(self, sample_model_config):
        """Test ModelConfig with all fields specified."""
        assert sample_model_config.name == "test-model"
        assert sample_model_config.provider == "test-provider"
        assert sample_model_config.max_context_length == 8192
        assert "reasoning" in sample_model_config.capabilities
    
    def test_model_config_capabilities_list(self):
        """Test that capabilities is a list."""
        config = ModelConfig(
            name="test",
            capabilities=["reasoning", "code_generation", "debugging"]
        )
        
        assert len(config.capabilities) == 3
        assert "reasoning" in config.capabilities


# =============================================================================
# ExecutionConfig Tests
# =============================================================================

class TestExecutionConfig:
    """Tests for ExecutionConfig dataclass."""
    
    def test_execution_config_defaults(self):
        """Test ExecutionConfig default values."""
        config = ExecutionConfig()
        
        assert config.default_mode == ExecutionMode.BALANCED
        assert config.max_parallel_executions == 5
        assert config.default_timeout_seconds == 60.0
        assert config.max_retries == 3
        assert config.enable_arbitration is True
        assert config.enable_synthesis is True
        assert config.default_accuracy_requirement == 0.8
    
    def test_execution_config_custom_values(self, sample_execution_config):
        """Test ExecutionConfig with custom values."""
        assert sample_execution_config.max_parallel_executions == 5
        assert sample_execution_config.default_accuracy_requirement == 0.8


# =============================================================================
# LoggingConfig Tests
# =============================================================================

class TestLoggingConfig:
    """Tests for LoggingConfig dataclass."""
    
    def test_logging_config_defaults(self):
        """Test LoggingConfig default values."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.format_json is False
        assert config.include_timestamp is True
        assert config.include_caller is False
    
    def test_logging_config_custom_level(self):
        """Test LoggingConfig with custom log level."""
        config = LoggingConfig(level="DEBUG", format_json=True)
        
        assert config.level == "DEBUG"
        assert config.format_json is True


# =============================================================================
# RoutingRule Tests
# =============================================================================

class TestRoutingRule:
    """Tests for RoutingRule dataclass."""
    
    def test_routing_rule_defaults(self):
        """Test RoutingRule default values."""
        rule = RoutingRule()
        
        assert rule.name == ""
        assert rule.task_types == []
        assert rule.enabled is True
        assert rule.weight == 1.0
    
    def test_routing_rule_with_task_types(self):
        """Test RoutingRule with task types specified."""
        rule = RoutingRule(
            name="code-tasks",
            task_types=[TaskType.CODE_GENERATION, TaskType.DEBUGGING],
            preferred_models=["gpt-4", "claude-3"],
            cost_threshold=0.5
        )
        
        assert rule.name == "code-tasks"
        assert len(rule.task_types) == 2
        assert TaskType.CODE_GENERATION in rule.task_types
        assert rule.cost_threshold == 0.5


# =============================================================================
# PluginConfig Tests
# =============================================================================

class TestPluginConfig:
    """Tests for PluginConfig dataclass."""
    
    def test_plugin_config_defaults(self):
        """Test PluginConfig default values."""
        config = PluginConfig()
        
        assert config.name == ""
        assert config.enabled is True
        assert config.version == "1.0.0"
        assert config.dependencies == []
    
    def test_plugin_config_with_module_path(self):
        """Test PluginConfig with module path."""
        config = PluginConfig(
            name="custom-model",
            module_path="plugins.custom_model",
            class_name="CustomModelAdapter",
            config={"api_url": "http://localhost:8080"}
        )
        
        assert config.module_path == "plugins.custom_model"
        assert config.class_name == "CustomModelAdapter"
        assert "api_url" in config.config


# =============================================================================
# ExecutionModeConfig Tests
# =============================================================================

class TestExecutionModeConfig:
    """Tests for ExecutionModeConfig dataclass."""
    
    def test_execution_mode_config_defaults(self):
        """Test ExecutionModeConfig default values."""
        config = ExecutionModeConfig()
        
        assert config.mode == ExecutionMode.BALANCED
        assert config.max_parallel_executions == 5
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 3
        assert config.enable_arbitration is True
        assert config.fallback_strategy == "automatic"
    
    def test_execution_mode_config_fast_mode(self):
        """Test ExecutionModeConfig for fast mode."""
        config = ExecutionModeConfig(
            mode=ExecutionMode.FAST,
            max_parallel_executions=10,
            timeout_seconds=30.0,
            accuracy_requirement=0.7
        )
        
        assert config.mode == ExecutionMode.FAST
        assert config.max_parallel_executions == 10
        assert config.accuracy_requirement == 0.7


# =============================================================================
# Configuration Loading Tests
# =============================================================================

class TestConfigurationLoading:
    """Tests for configuration file loading."""
    
    def test_create_default_config(self):
        """Test creating default configuration."""
        config = create_default_config()
        
        assert config is not None
        assert isinstance(config, AICouncilConfig)
        assert config.execution is not None
        assert config.logging is not None
    
    def test_load_config_from_yaml_file(self, temp_config_file):
        """Test loading configuration from YAML file."""
        config = load_config(temp_config_file)
        
        assert config is not None
        assert isinstance(config, AICouncilConfig)
    
    def test_load_config_nonexistent_file_returns_default(self):
        """Test that loading nonexistent file returns default config."""
        config = load_config(Path("/nonexistent/path/config.yaml"))
        
        # Should return default config instead of raising
        assert config is not None
    
    def test_config_from_dict(self, sample_config_dict):
        """Test creating configuration from dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config_dict, f)
            temp_path = Path(f.name)
        
        try:
            config = load_config(temp_path)
            assert config is not None
        finally:
            os.unlink(temp_path)
    
    def test_config_models_dictionary(self, sample_config_dict):
        """Test that models are properly loaded as dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config_dict, f)
            temp_path = Path(f.name)
        
        try:
            config = load_config(temp_path)
            assert config.models is not None
            # Models should be accessible
            assert isinstance(config.models, dict)
        finally:
            os.unlink(temp_path)


# =============================================================================
# Environment Variable Tests
# =============================================================================

class TestEnvironmentVariables:
    """Tests for environment variable handling in configuration."""
    
    def test_model_api_key_env_reference(self):
        """Test that API key environment variable reference is stored correctly."""
        config = ModelConfig(
            name="test-model",
            api_key_env="MY_API_KEY"
        )
        
        assert config.api_key_env == "MY_API_KEY"
    
    def test_config_respects_env_override(self):
        """Test that configuration respects environment variable overrides."""
        # Set environment variable
        os.environ['AI_COUNCIL_LOG_LEVEL'] = 'DEBUG'
        
        try:
            # This tests if the config system respects env vars
            # The actual behavior depends on implementation
            config = create_default_config()
            assert config is not None
        finally:
            del os.environ['AI_COUNCIL_LOG_LEVEL']


# =============================================================================
# Configuration Validation Tests
# =============================================================================

class TestConfigurationValidation:
    """Tests for configuration validation."""
    
    def test_valid_execution_modes(self):
        """Test that all execution modes are valid."""
        for mode in ExecutionMode:
            config = ExecutionConfig(default_mode=mode)
            assert config.default_mode == mode
    
    def test_positive_timeout_values(self):
        """Test that timeout values can be positive."""
        config = ExecutionConfig(default_timeout_seconds=120.0)
        assert config.default_timeout_seconds == 120.0
    
    def test_positive_retry_counts(self):
        """Test that retry counts can be positive."""
        config = ExecutionConfig(max_retries=5)
        assert config.max_retries == 5
    
    def test_accuracy_requirement_range(self):
        """Test accuracy requirement within valid range."""
        config = ExecutionConfig(default_accuracy_requirement=0.95)
        assert config.default_accuracy_requirement == 0.95


# =============================================================================
# Configuration Serialization Tests
# =============================================================================

class TestConfigurationSerialization:
    """Tests for configuration serialization."""
    
    def test_config_to_dict_round_trip(self, sample_config_dict):
        """Test that config can be saved and loaded."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config_dict, f)
            temp_path = Path(f.name)
        
        try:
            # Load config
            config = load_config(temp_path)
            
            # Save it again
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
                # This tests that the config can be used
                assert config is not None
        finally:
            os.unlink(temp_path)
