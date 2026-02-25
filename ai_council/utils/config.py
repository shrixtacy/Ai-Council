"""Configuration management for AI Council."""

import os
import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Type, Callable, Union
import yaml
from ai_council.core.models import ExecutionMode, RiskLevel, TaskType, Priority


@dataclass
class RoutingRule:
    """Configuration for a routing rule."""
    name: str = ""
    task_types: List[TaskType] = field(default_factory=list)
    priority_levels: List[Priority] = field(default_factory=list)
    risk_levels: List[RiskLevel] = field(default_factory=list)
    execution_modes: List[ExecutionMode] = field(default_factory=list)
    preferred_models: List[str] = field(default_factory=list)
    excluded_models: List[str] = field(default_factory=list)
    cost_threshold: Optional[float] = None
    accuracy_threshold: Optional[float] = None
    latency_threshold: Optional[float] = None
    enabled: bool = True
    weight: float = 1.0


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str = ""
    module_path: str = ""
    class_name: str = ""
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class ExecutionModeConfig:
    """Configuration for execution mode behavior."""
    mode: ExecutionMode = ExecutionMode.BALANCED
    max_parallel_executions: int = 5
    timeout_seconds: float = 60.0
    max_retries: int = 3
    enable_arbitration: bool = True
    enable_synthesis: bool = True
    accuracy_requirement: float = 0.8
    cost_limit: Optional[float] = None
    preferred_model_types: List[str] = field(default_factory=list)
    fallback_strategy: str = "automatic"


@dataclass
class LoggingConfig:
    """Configuration for logging system."""
    level: str = "INFO"
    format_json: bool = False
    include_timestamp: bool = True
    include_caller: bool = False


@dataclass
class ModelConfig:
    """Configuration for a single AI model."""
    name: str = ""
    provider: str = ""
    api_key_env: str = ""
    base_url: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: float = 30.0
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    max_context_length: int = 4096
    capabilities: List[str] = field(default_factory=list)
    enabled: bool = True
    # Extended model configuration
    reliability_score: float = 0.8
    average_latency: float = 2.0
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    supported_task_types: List[TaskType] = field(default_factory=list)
    plugin_config: Optional[PluginConfig] = None


@dataclass
class ExecutionConfig:
    """Configuration for execution behavior."""
    default_mode: ExecutionMode = ExecutionMode.BALANCED
    max_parallel_executions: int = 5
    default_timeout_seconds: float = 60.0
    max_retries: int = 3
    enable_arbitration: bool = True
    enable_synthesis: bool = True
    default_accuracy_requirement: float = 0.8
    use_mq: bool = False
    redis_url: str = "redis://localhost:6379"

    def __post_init__(self):
        if self.use_mq:
            if not self.redis_url or not (self.redis_url.startswith("redis://") or self.redis_url.startswith("rediss://")):
                raise ValueError("redis_url must start with 'redis://' or 'rediss://' when use_mq is True")


@dataclass
class CostConfig:
    """Configuration for cost management."""
    max_cost_per_request: float = 10.0
    currency: str = "USD"
    enable_cost_tracking: bool = True
    cost_alert_threshold: float = 5.0


@dataclass
class AICouncilConfig:
    """Main configuration class for AI Council."""
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    
    # Extended configuration
    routing_rules: List[RoutingRule] = field(default_factory=list)
    execution_modes: Dict[str, ExecutionModeConfig] = field(default_factory=dict)
    plugins: Dict[str, PluginConfig] = field(default_factory=dict)
    
    # System settings
    debug: bool = False
    environment: str = "production"
    data_dir: str = "./data"
    cache_dir: str = "./cache"
    plugin_dir: str = "./plugins"
    
    @classmethod
    def from_file(cls, config_path: Path) -> "AICouncilConfig":
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Loaded configuration instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            ValueError: If config contains invalid values
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        return cls.from_dict(config_data or {})
    
    @classmethod
    def from_dict(cls, config_data: Dict[str, Any]) -> "AICouncilConfig":
        """
        Create configuration from a dictionary.
        
        Args:
            config_data: Configuration data as dictionary
            
        Returns:
            Configuration instance
        """
        # Extract and convert nested configurations
        logging_data = config_data.get('logging', {})
        execution_data = config_data.get('execution', {})
        cost_data = config_data.get('cost', {})
        models_data = config_data.get('models', {})
        routing_rules_data = config_data.get('routing_rules', [])
        execution_modes_data = config_data.get('execution_modes', {})
        plugins_data = config_data.get('plugins', {})
        
        # Convert execution mode if specified
        if 'default_mode' in execution_data:
            mode_str = execution_data['default_mode']
            if isinstance(mode_str, str):
                execution_data['default_mode'] = ExecutionMode(mode_str.lower())
        
        # Create model configurations
        models = {}
        for model_name, model_data in models_data.items():
            # Convert task types if present
            if 'supported_task_types' in model_data:
                task_types = []
                for task_type_str in model_data['supported_task_types']:
                    if isinstance(task_type_str, str):
                        try:
                            task_types.append(TaskType(task_type_str.lower()))
                        except ValueError:
                            pass  # Skip invalid task types
                model_data['supported_task_types'] = task_types
            
            # Handle plugin config if present
            if 'plugin_config' in model_data and model_data['plugin_config'] is not None:
                plugin_data = model_data['plugin_config']
                model_data['plugin_config'] = PluginConfig(**plugin_data)
            
            model_config = ModelConfig(name=model_name, **model_data)
            models[model_name] = model_config
        
        # Create routing rules
        routing_rules = []
        for rule_data in routing_rules_data:
            # Convert enum fields
            if 'task_types' in rule_data:
                task_types = []
                for task_type_str in rule_data['task_types']:
                    if isinstance(task_type_str, str):
                        try:
                            task_types.append(TaskType(task_type_str.lower()))
                        except ValueError:
                            pass
                rule_data['task_types'] = task_types
            
            if 'priority_levels' in rule_data:
                priorities = []
                for priority_str in rule_data['priority_levels']:
                    if isinstance(priority_str, str):
                        try:
                            priorities.append(Priority(priority_str.upper()))
                        except ValueError:
                            pass
                rule_data['priority_levels'] = priorities
            
            if 'risk_levels' in rule_data:
                risk_levels = []
                for risk_str in rule_data['risk_levels']:
                    if isinstance(risk_str, str):
                        try:
                            risk_levels.append(RiskLevel(risk_str.upper()))
                        except ValueError:
                            pass
                rule_data['risk_levels'] = risk_levels
            
            if 'execution_modes' in rule_data:
                exec_modes = []
                for mode_str in rule_data['execution_modes']:
                    if isinstance(mode_str, str):
                        try:
                            exec_modes.append(ExecutionMode(mode_str.lower()))
                        except ValueError:
                            pass
                rule_data['execution_modes'] = exec_modes
            
            routing_rules.append(RoutingRule(**rule_data))
        
        # Create execution mode configurations
        execution_modes = {}
        for mode_name, mode_data in execution_modes_data.items():
            if 'mode' in mode_data and isinstance(mode_data['mode'], str):
                mode_data['mode'] = ExecutionMode(mode_data['mode'].lower())
            execution_modes[mode_name] = ExecutionModeConfig(**mode_data)
        
        # Create plugin configurations
        plugins = {}
        for plugin_name, plugin_data in plugins_data.items():
            plugins[plugin_name] = PluginConfig(name=plugin_name, **plugin_data)
        
        return cls(
            logging=LoggingConfig(**logging_data),
            execution=ExecutionConfig(**execution_data),
            cost=CostConfig(**cost_data),
            models=models,
            routing_rules=routing_rules,
            execution_modes=execution_modes,
            plugins=plugins,
            debug=config_data.get('debug', False),
            environment=config_data.get('environment', 'production'),
            data_dir=config_data.get('data_dir', './data'),
            cache_dir=config_data.get('cache_dir', './cache'),
            plugin_dir=config_data.get('plugin_dir', './plugins'),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Configuration as dictionary
        """
        config_dict = {
            'logging': {
                'level': self.logging.level,
                'format_json': self.logging.format_json,
                'include_timestamp': self.logging.include_timestamp,
                'include_caller': self.logging.include_caller,
            },
            'execution': {
                'default_mode': self.execution.default_mode.value,
                'max_parallel_executions': self.execution.max_parallel_executions,
                'default_timeout_seconds': self.execution.default_timeout_seconds,
                'max_retries': self.execution.max_retries,
                'enable_arbitration': self.execution.enable_arbitration,
                'enable_synthesis': self.execution.enable_synthesis,
                'default_accuracy_requirement': self.execution.default_accuracy_requirement,
                'use_mq': self.execution.use_mq,
                'redis_url': self.execution.redis_url,
            },
            'cost': {
                'max_cost_per_request': self.cost.max_cost_per_request,
                'currency': self.cost.currency,
                'enable_cost_tracking': self.cost.enable_cost_tracking,
                'cost_alert_threshold': self.cost.cost_alert_threshold,
            },
            'models': {
                name: {
                    'provider': config.provider,
                    'api_key_env': config.api_key_env,
                    'base_url': config.base_url,
                    'max_retries': config.max_retries,
                    'timeout_seconds': config.timeout_seconds,
                    'cost_per_input_token': config.cost_per_input_token,
                    'cost_per_output_token': config.cost_per_output_token,
                    'max_context_length': config.max_context_length,
                    'capabilities': config.capabilities,
                    'enabled': config.enabled,
                    'reliability_score': config.reliability_score,
                    'average_latency': config.average_latency,
                    'strengths': config.strengths,
                    'weaknesses': config.weaknesses,
                    'supported_task_types': [tt.value for tt in config.supported_task_types],
                    'plugin_config': config.plugin_config.__dict__ if config.plugin_config else None,
                }
                for name, config in self.models.items()
            },
            'routing_rules': [
                {
                    'name': rule.name,
                    'task_types': [tt.value for tt in rule.task_types],
                    'priority_levels': [p.value for p in rule.priority_levels],
                    'risk_levels': [rl.value for rl in rule.risk_levels],
                    'execution_modes': [em.value for em in rule.execution_modes],
                    'preferred_models': rule.preferred_models,
                    'excluded_models': rule.excluded_models,
                    'cost_threshold': rule.cost_threshold,
                    'accuracy_threshold': rule.accuracy_threshold,
                    'latency_threshold': rule.latency_threshold,
                    'enabled': rule.enabled,
                    'weight': rule.weight,
                }
                for rule in self.routing_rules
            ],
            'execution_modes': {
                name: {
                    'mode': config.mode.value,
                    'max_parallel_executions': config.max_parallel_executions,
                    'timeout_seconds': config.timeout_seconds,
                    'max_retries': config.max_retries,
                    'enable_arbitration': config.enable_arbitration,
                    'enable_synthesis': config.enable_synthesis,
                    'accuracy_requirement': config.accuracy_requirement,
                    'cost_limit': config.cost_limit,
                    'preferred_model_types': config.preferred_model_types,
                    'fallback_strategy': config.fallback_strategy,
                }
                for name, config in self.execution_modes.items()
            },
            'plugins': {
                name: {
                    'module_path': config.module_path,
                    'class_name': config.class_name,
                    'enabled': config.enabled,
                    'config': config.config,
                    'dependencies': config.dependencies,
                    'version': config.version,
                }
                for name, config in self.plugins.items()
            },
            'debug': self.debug,
            'environment': self.environment,
            'data_dir': self.data_dir,
            'cache_dir': self.cache_dir,
            'plugin_dir': self.plugin_dir,
        }
        
        return config_dict
    
    def save_to_file(self, config_path: Path) -> None:
        """
        Save configuration to a YAML file.
        
        Args:
            config_path: Path where to save the configuration
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, indent=2)
    
    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """
        Get configuration for a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model configuration if found, None otherwise
        """
        return self.models.get(model_name)
    
    def add_routing_rule(self, rule: RoutingRule) -> None:
        """
        Add a routing rule to the configuration.
        
        Args:
            rule: The routing rule to add
        """
        # Remove existing rule with same name if present
        self.routing_rules = [r for r in self.routing_rules if r.name != rule.name]
        self.routing_rules.append(rule)
    
    def get_routing_rules(self, task_type: Optional[TaskType] = None, 
                         execution_mode: Optional[ExecutionMode] = None) -> List[RoutingRule]:
        """
        Get routing rules that match the specified criteria.
        
        Args:
            task_type: Optional task type to filter by
            execution_mode: Optional execution mode to filter by
            
        Returns:
            List of matching routing rules
        """
        matching_rules = []
        
        for rule in self.routing_rules:
            if not rule.enabled:
                continue
                
            if task_type and rule.task_types and task_type not in rule.task_types:
                continue
                
            if execution_mode and rule.execution_modes and execution_mode not in rule.execution_modes:
                continue
                
            matching_rules.append(rule)
        
        # Sort by weight (descending)
        matching_rules.sort(key=lambda r: r.weight, reverse=True)
        return matching_rules
    
    def get_execution_mode_config(self, mode_name: str) -> Optional[ExecutionModeConfig]:
        """
        Get configuration for a specific execution mode.
        
        Args:
            mode_name: Name of the execution mode
            
        Returns:
            Execution mode configuration if found, None otherwise
        """
        return self.execution_modes.get(mode_name)
    
    def add_plugin(self, plugin: PluginConfig) -> None:
        """
        Add a plugin configuration.
        
        Args:
            plugin: The plugin configuration to add
        """
        self.plugins[plugin.name] = plugin
    
    def get_enabled_plugins(self) -> List[PluginConfig]:
        """
        Get all enabled plugin configurations.
        
        Returns:
            List of enabled plugin configurations
        """
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
    
    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Remove a plugin configuration.
        
        Args:
            plugin_name: Name of the plugin to remove
            
        Returns:
            True if plugin was removed, False if not found
        """
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            return True
        return False
    
    def validate(self) -> None:
        """
        Validate the configuration for consistency and completeness.
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate execution config
        if self.execution.max_parallel_executions <= 0:
            raise ValueError("max_parallel_executions must be positive")
        
        if self.execution.default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        
        if not (0.0 <= self.execution.default_accuracy_requirement <= 1.0):
            raise ValueError("default_accuracy_requirement must be between 0.0 and 1.0")
        
        # Validate cost config
        if self.cost.max_cost_per_request <= 0:
            raise ValueError("max_cost_per_request must be positive")
        
        # Validate model configs
        for model_name, model_config in self.models.items():
            if not model_config.name:
                model_config.name = model_name
            
            if model_config.cost_per_input_token < 0:
                raise ValueError(f"Model {model_name}: cost_per_input_token cannot be negative")
            
            if model_config.cost_per_output_token < 0:
                raise ValueError(f"Model {model_name}: cost_per_output_token cannot be negative")
            
            if model_config.max_context_length <= 0:
                raise ValueError(f"Model {model_name}: max_context_length must be positive")
            
            if not (0.0 <= model_config.reliability_score <= 1.0):
                raise ValueError(f"Model {model_name}: reliability_score must be between 0.0 and 1.0")
            
            if model_config.average_latency < 0:
                raise ValueError(f"Model {model_name}: average_latency cannot be negative")
        
        # Validate routing rules
        for rule in self.routing_rules:
            if not rule.name:
                raise ValueError("Routing rule must have a name")
            
            if rule.weight < 0:
                raise ValueError(f"Routing rule {rule.name}: weight cannot be negative")
            
            if rule.cost_threshold is not None and rule.cost_threshold < 0:
                raise ValueError(f"Routing rule {rule.name}: cost_threshold cannot be negative")
            
            if rule.accuracy_threshold is not None and not (0.0 <= rule.accuracy_threshold <= 1.0):
                raise ValueError(f"Routing rule {rule.name}: accuracy_threshold must be between 0.0 and 1.0")
            
            if rule.latency_threshold is not None and rule.latency_threshold < 0:
                raise ValueError(f"Routing rule {rule.name}: latency_threshold cannot be negative")
        
        # Validate execution mode configs
        for mode_name, mode_config in self.execution_modes.items():
            if mode_config.max_parallel_executions <= 0:
                raise ValueError(f"Execution mode {mode_name}: max_parallel_executions must be positive")
            
            if mode_config.timeout_seconds <= 0:
                raise ValueError(f"Execution mode {mode_name}: timeout_seconds must be positive")
            
            if not (0.0 <= mode_config.accuracy_requirement <= 1.0):
                raise ValueError(f"Execution mode {mode_name}: accuracy_requirement must be between 0.0 and 1.0")
            
            if mode_config.cost_limit is not None and mode_config.cost_limit <= 0:
                raise ValueError(f"Execution mode {mode_name}: cost_limit must be positive")
        
        # Validate plugin configs
        for plugin_name, plugin_config in self.plugins.items():
            if not plugin_config.module_path:
                raise ValueError(f"Plugin {plugin_name}: module_path is required")
            
            if not plugin_config.class_name:
                raise ValueError(f"Plugin {plugin_name}: class_name is required")
        
        # Validate directories exist or can be created
        for dir_path in [self.data_dir, self.cache_dir, self.plugin_dir]:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create directory {dir_path}: {e}")


def load_config(config_path: Optional[Path] = None) -> AICouncilConfig:
    """
    Load configuration from file or environment variables.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Loaded configuration
    """
    # Default config paths to try
    default_paths = [
        Path("ai_council_config.yaml"),
        Path("config/ai_council.yaml"),
        Path.home() / ".ai_council" / "config.yaml",
    ]
    
    if config_path:
        default_paths.insert(0, config_path)
    
    # Try to load from file
    for path in default_paths:
        if path.exists():
            config = AICouncilConfig.from_file(path)
            config.validate()
            return config
    
    # Fall back to default configuration
    config = AICouncilConfig()
    
    # Override with environment variables if present
    if os.getenv('AI_COUNCIL_DEBUG'):
        config.debug = os.getenv('AI_COUNCIL_DEBUG', '').lower() in ('true', '1', 'yes')
    
    if os.getenv('AI_COUNCIL_ENVIRONMENT'):
        config.environment = os.getenv('AI_COUNCIL_ENVIRONMENT', 'production')
    
    if os.getenv('AI_COUNCIL_LOG_LEVEL'):
        config.logging.level = os.getenv('AI_COUNCIL_LOG_LEVEL', 'INFO')
    
    config.validate()
    return config


def create_default_config() -> AICouncilConfig:
    """
    Create a default configuration with sample model configurations.
    
    Returns:
        Default configuration instance
    """
    config = AICouncilConfig()
    
    # Add sample model configurations
    config.models = {
        "gpt-4": ModelConfig(
            name="gpt-4",
            provider="openai",
            api_key_env="OPENAI_API_KEY",
            cost_per_input_token=0.00003,
            cost_per_output_token=0.00006,
            max_context_length=8192,
            capabilities=["reasoning", "code_generation", "creative_output"],
            reliability_score=0.95,
            average_latency=3.0,
            strengths=["complex reasoning", "code generation", "creative tasks"],
            weaknesses=["high cost", "slower response"],
            supported_task_types=[TaskType.REASONING, TaskType.CODE_GENERATION, TaskType.CREATIVE_OUTPUT],
        ),
        "claude-3": ModelConfig(
            name="claude-3",
            provider="anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            cost_per_input_token=0.000015,
            cost_per_output_token=0.000075,
            max_context_length=200000,
            capabilities=["reasoning", "research", "fact_checking"],
            reliability_score=0.92,
            average_latency=2.5,
            strengths=["large context", "research", "fact checking"],
            weaknesses=["limited code generation"],
            supported_task_types=[TaskType.REASONING, TaskType.RESEARCH, TaskType.FACT_CHECKING],
        ),
        "gpt-3.5-turbo": ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            api_key_env="OPENAI_API_KEY",
            cost_per_input_token=0.0000015,
            cost_per_output_token=0.000002,
            max_context_length=16384,
            capabilities=["reasoning", "creative_output"],
            reliability_score=0.85,
            average_latency=1.5,
            strengths=["fast", "cost-effective", "general purpose"],
            weaknesses=["lower accuracy", "limited complex reasoning"],
            supported_task_types=[TaskType.REASONING, TaskType.CREATIVE_OUTPUT],
        ),
    }
    
    # Add sample routing rules
    config.routing_rules = [
        RoutingRule(
            name="high_accuracy_reasoning",
            task_types=[TaskType.REASONING],
            priority_levels=[Priority.CRITICAL, Priority.HIGH],
            preferred_models=["gpt-4", "claude-3"],
            accuracy_threshold=0.9,
            weight=2.0,
        ),
        RoutingRule(
            name="cost_effective_general",
            task_types=[TaskType.REASONING, TaskType.CREATIVE_OUTPUT],
            priority_levels=[Priority.LOW, Priority.MEDIUM],
            preferred_models=["gpt-3.5-turbo"],
            cost_threshold=0.01,
            weight=1.0,
        ),
        RoutingRule(
            name="research_tasks",
            task_types=[TaskType.RESEARCH, TaskType.FACT_CHECKING],
            preferred_models=["claude-3"],
            weight=1.5,
        ),
    ]
    
    # Add sample execution mode configurations
    config.execution_modes = {
        "fast": ExecutionModeConfig(
            mode=ExecutionMode.FAST,
            max_parallel_executions=3,
            timeout_seconds=30.0,
            max_retries=1,
            enable_arbitration=False,
            enable_synthesis=True,
            accuracy_requirement=0.7,
            cost_limit=5.0,
            preferred_model_types=["gpt-3.5-turbo"],
            fallback_strategy="cheapest",
        ),
        "balanced": ExecutionModeConfig(
            mode=ExecutionMode.BALANCED,
            max_parallel_executions=5,
            timeout_seconds=60.0,
            max_retries=3,
            enable_arbitration=True,
            enable_synthesis=True,
            accuracy_requirement=0.8,
            cost_limit=10.0,
            preferred_model_types=["gpt-4", "claude-3", "gpt-3.5-turbo"],
            fallback_strategy="automatic",
        ),
        "best_quality": ExecutionModeConfig(
            mode=ExecutionMode.BEST_QUALITY,
            max_parallel_executions=8,
            timeout_seconds=120.0,
            max_retries=5,
            enable_arbitration=True,
            enable_synthesis=True,
            accuracy_requirement=0.95,
            preferred_model_types=["gpt-4", "claude-3"],
            fallback_strategy="highest_quality",
        ),
    }
    
    return config