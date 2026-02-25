"""
Factory for creating and wiring AI Council components with dependency injection.

This module provides a factory class that creates and configures all
AI Council components based on the provided configuration.
"""

import logging
from typing import Dict, List, Optional

from .core.interfaces import (
    OrchestrationLayer, AnalysisEngine, TaskDecomposer, ModelContextProtocol,
    ExecutionAgent, ArbitrationLayer, SynthesisLayer, ModelRegistry, AIModel
)
from .core.models import ModelCapabilities, CostProfile, PerformanceMetrics, TaskType
from .utils.config import AICouncilConfig, ModelConfig
from .utils.logging import get_logger

# Import concrete implementations
from .orchestration.layer import ConcreteOrchestrationLayer
from .analysis.engine import BasicAnalysisEngine
from .analysis.decomposer import BasicTaskDecomposer
from .routing.registry import ModelRegistryImpl
from .routing.context_protocol import ModelContextProtocolImpl
from .execution.agent import BaseExecutionAgent
from .execution.mock_models import MockModelFactory
from .arbitration.layer import ConcreteArbitrationLayer
from .synthesis.layer import SynthesisLayerImpl


class AICouncilFactory:
    """
    Factory class for creating and wiring AI Council components.
    
    This factory handles dependency injection and component configuration
    based on the provided configuration.
    """
    
    def __init__(self, config: AICouncilConfig):
        """
        Initialize the factory with configuration.
        
        Args:
            config: The AI Council configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Cache for created components
        self._model_registry: Optional[ModelRegistry] = None
        self._analysis_engine: Optional[AnalysisEngine] = None
        self._task_decomposer: Optional[TaskDecomposer] = None
        self._model_context_protocol: Optional[ModelContextProtocol] = None
        self._execution_agent: Optional[ExecutionAgent] = None
        self._arbitration_layer: Optional[ArbitrationLayer] = None
        self._synthesis_layer: Optional[SynthesisLayer] = None
        
        self.logger.info("AI Council factory initialized")
    
    @property
    def model_registry(self) -> ModelRegistry:
        """Get or create the model registry."""
        if self._model_registry is None:
            self._model_registry = self._create_model_registry()
        return self._model_registry
    
    @property
    def analysis_engine(self) -> AnalysisEngine:
        """Get or create the analysis engine."""
        if self._analysis_engine is None:
            self._analysis_engine = self._create_analysis_engine()
        return self._analysis_engine
    
    @property
    def task_decomposer(self) -> TaskDecomposer:
        """Get or create the task decomposer."""
        if self._task_decomposer is None:
            self._task_decomposer = self._create_task_decomposer()
        return self._task_decomposer
    
    @property
    def model_context_protocol(self) -> ModelContextProtocol:
        """Get or create the model context protocol."""
        if self._model_context_protocol is None:
            self._model_context_protocol = self._create_model_context_protocol()
        return self._model_context_protocol
    
    @property
    def execution_agent(self) -> ExecutionAgent:
        """Get or create the execution agent."""
        if self._execution_agent is None:
            self._execution_agent = self._create_execution_agent()
        return self._execution_agent
    
    @property
    def arbitration_layer(self) -> ArbitrationLayer:
        """Get or create the arbitration layer."""
        if self._arbitration_layer is None:
            self._arbitration_layer = self._create_arbitration_layer()
        return self._arbitration_layer
    
    @property
    def synthesis_layer(self) -> SynthesisLayer:
        """Get or create the synthesis layer."""
        if self._synthesis_layer is None:
            self._synthesis_layer = self._create_synthesis_layer()
        return self._synthesis_layer
    
    def create_orchestration_layer(self) -> OrchestrationLayer:
        """
        Create the main orchestration layer with all dependencies.
        
        Returns:
            OrchestrationLayer: Fully configured orchestration layer
        """
        self.logger.info("Creating orchestration layer with all dependencies")
        
        # Create orchestration layer with all dependencies
        orchestration_layer = ConcreteOrchestrationLayer(
            analysis_engine=self.analysis_engine,
            task_decomposer=self.task_decomposer,
            model_context_protocol=self.model_context_protocol,
            execution_agent=self.execution_agent,
            arbitration_layer=self.arbitration_layer,
            synthesis_layer=self.synthesis_layer,
            model_registry=self.model_registry,
            max_retries=self.config.execution.max_retries,
            timeout_seconds=self.config.execution.default_timeout_seconds
        )
        
        self.logger.info("Orchestration layer created successfully")
        return orchestration_layer
    
    def _create_model_registry(self) -> ModelRegistry:
        """Create and configure the model registry."""
        self.logger.info("Creating model registry")
        
        registry = ModelRegistryImpl()
        
        # Register models from configuration
        for model_name, model_config in self.config.models.items():
            if not model_config.enabled:
                self.logger.info(f"Skipping disabled model: {model_name}")
                continue
            
            try:
                # Create model instance
                model = self._create_model_instance(model_name, model_config)
                
                # Create capabilities
                capabilities = self._create_model_capabilities(model_config)
                
                # Create cost profile
                cost_profile = CostProfile(
                    cost_per_input_token=model_config.cost_per_input_token,
                    cost_per_output_token=model_config.cost_per_output_token,
                    minimum_cost=0.001  # Default minimum cost
                )
                
                # Create performance metrics (initial estimates)
                performance_metrics = PerformanceMetrics(
                    average_response_time=model_config.timeout_seconds / 2,  # Estimate
                    success_rate=0.95,  # Default high success rate
                    average_quality_score=0.85,  # Default quality score
                    total_requests=0,
                    failed_requests=0
                )
                
                # Register the model
                registry.register_model(model, capabilities)
                
                # Set additional profiles (accessing private attributes for setup)
                if hasattr(registry, '_cost_profiles'):
                    registry._cost_profiles[model.get_model_id()] = cost_profile
                if hasattr(registry, '_performance_metrics'):
                    registry._performance_metrics[model.get_model_id()] = performance_metrics
                
                self.logger.info(f"Registered model: {model_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to register model {model_name}: {str(e)}")
                continue
        
        # If no models were registered from config, create default mock models
        if not hasattr(registry, '_models') or not registry._models:
            self.logger.warning("No models registered from config, creating default mock models")
            self._register_default_mock_models(registry)
        
        self.logger.info("Model registry created successfully")
        return registry
    
    def _create_model_instance(self, model_name: str, model_config: ModelConfig) -> AIModel:
        """Create a model instance based on configuration."""
        import os
        
        # Try to import real adapters
        try:
            from web_app.backend.ai_adapters import create_model_adapter
            
            # Check if API key is available
            api_key = os.getenv(model_config.api_key_env) if model_config.api_key_env else None
            
            if api_key:
                # Create real model adapter
                self.logger.info(f"Creating real {model_config.provider} adapter for {model_name}")
                return create_model_adapter(model_config.provider, model_name, api_key)
            else:
                self.logger.warning(f"No API key found for {model_name}, using mock model")
        except ImportError:
            self.logger.warning(f"Real adapters not available, using mock model for {model_name}")
        except Exception as e:
            self.logger.warning(f"Failed to create real adapter for {model_name}: {str(e)}, using mock")
        
        # Fallback to mock models
        if model_config.provider == "openai":
            if "gpt-4" in model_name.lower():
                return MockModelFactory.create_specialized_model(
                    model_name, "reasoning", "high"
                )
            else:
                return MockModelFactory.create_fast_model(model_name)
        
        elif model_config.provider == "anthropic":
            return MockModelFactory.create_specialized_model(
                model_name, "research", "high"
            )
        
        elif model_config.provider in ["google", "groq", "mistral"]:
            # Create appropriate mock for these providers
            return MockModelFactory.create_specialized_model(
                model_name, "reasoning", "high"
            )
        
        else:
            return MockModelFactory.create_fast_model(model_name)
    
    def _create_model_capabilities(self, model_config: ModelConfig) -> ModelCapabilities:
        """Create model capabilities from configuration."""
        # Map capability strings to TaskType enums
        task_type_mapping = {
            "reasoning": TaskType.REASONING,
            "research": TaskType.RESEARCH,
            "code_generation": TaskType.CODE_GENERATION,
            "debugging": TaskType.DEBUGGING,
            "creative_output": TaskType.CREATIVE_OUTPUT,
            "image_generation": TaskType.IMAGE_GENERATION,
            "fact_checking": TaskType.FACT_CHECKING,
            "verification": TaskType.VERIFICATION
        }
        
        task_types = []
        for capability in model_config.capabilities:
            if capability in task_type_mapping:
                task_types.append(task_type_mapping[capability])
        
        # Default to reasoning if no capabilities specified
        if not task_types:
            task_types = [TaskType.REASONING]
        
        return ModelCapabilities(
            task_types=task_types,
            cost_per_token=(model_config.cost_per_input_token + model_config.cost_per_output_token) / 2,
            average_latency=model_config.timeout_seconds / 3,  # Estimate
            max_context_length=model_config.max_context_length,
            reliability_score=0.9,  # Default reliability
            strengths=model_config.capabilities[:2],  # First two as strengths
            weaknesses=[]  # No weaknesses specified in config
        )
    
    def _register_default_mock_models(self, registry: ModelRegistry):
        """Register default mock models for testing."""
        default_models = [
            (MockModelFactory.create_specialized_model("mock-gpt-4", "reasoning", "high"),
             ModelCapabilities(
                task_types=[TaskType.REASONING, TaskType.CODE_GENERATION, TaskType.CREATIVE_OUTPUT],
                cost_per_token=0.00003,
                average_latency=2.5,
                max_context_length=8000,
                reliability_score=0.95,
                strengths=["reasoning", "code generation"],
                weaknesses=["factual accuracy"]
            )),
            
            (MockModelFactory.create_specialized_model("mock-claude-3", "research", "high"),
             ModelCapabilities(
                task_types=[TaskType.REASONING, TaskType.RESEARCH, TaskType.FACT_CHECKING],
                cost_per_token=0.00002,
                average_latency=3.0,
                max_context_length=200000,
                reliability_score=0.92,
                strengths=["research", "fact checking"],
                weaknesses=["creative tasks"]
            )),
            
            (MockModelFactory.create_fast_model("mock-gpt-3.5"),
             ModelCapabilities(
                task_types=[TaskType.REASONING, TaskType.CREATIVE_OUTPUT],
                cost_per_token=0.000002,
                average_latency=1.5,
                max_context_length=16000,
                reliability_score=0.88,
                strengths=["speed", "cost efficiency"],
                weaknesses=["complex reasoning"]
            ))
        ]
        
        for model, capabilities in default_models:
            registry.register_model(model, capabilities)
            
            # Set cost profile
            if hasattr(registry, '_cost_profiles'):
                registry._cost_profiles[model.get_model_id()] = CostProfile(
                    cost_per_input_token=capabilities.cost_per_token * 0.8,
                    cost_per_output_token=capabilities.cost_per_token * 1.2,
                    minimum_cost=0.001
                )
            
            # Set performance metrics
            if hasattr(registry, '_performance_metrics'):
                registry._performance_metrics[model.get_model_id()] = PerformanceMetrics(
                    average_response_time=capabilities.average_latency,
                    success_rate=capabilities.reliability_score,
                    average_quality_score=capabilities.reliability_score,
                    total_requests=100,
                    failed_requests=int(100 * (1 - capabilities.reliability_score))
                )
    
    def _create_analysis_engine(self) -> AnalysisEngine:
        """Create the analysis engine."""
        self.logger.info("Creating analysis engine")
        return BasicAnalysisEngine()
    
    def _create_task_decomposer(self) -> TaskDecomposer:
        """Create the task decomposer."""
        self.logger.info("Creating task decomposer")
        return BasicTaskDecomposer()
    
    def _create_model_context_protocol(self) -> ModelContextProtocol:
        """Create the model context protocol."""
        self.logger.info("Creating model context protocol")
        return ModelContextProtocolImpl(self.model_registry)
    
    def _create_execution_agent(self) -> ExecutionAgent:
        """Create the execution agent."""
        self.logger.info("Creating execution agent")
        if self.config.execution.use_mq:
            from .execution.mq_agent import MQExecutionAgent
            import math
            from urllib.parse import urlparse
            
            parsed_url = urlparse(self.config.execution.redis_url)
            sanitized_netloc = f"***:***@{parsed_url.hostname}:{parsed_url.port}" if parsed_url.password else f"{parsed_url.hostname}:{parsed_url.port}"
            sanitized_url = parsed_url._replace(netloc=sanitized_netloc).geturl()
            
            self.logger.info(f"Using MQExecutionAgent with Redis URL: {sanitized_url}")
            
            raw_timeout = self.config.execution.default_timeout_seconds
            safe_timeout = int(math.ceil(raw_timeout)) if raw_timeout and raw_timeout > 0 else 1
            safe_timeout = max(1, safe_timeout)

            return MQExecutionAgent(
                redis_url=self.config.execution.redis_url,
                timeout_seconds=safe_timeout
            )
        return BaseExecutionAgent()
    
    def _create_arbitration_layer(self) -> ArbitrationLayer:
        """Create the arbitration layer."""
        self.logger.info("Creating arbitration layer")
        
        # Check if arbitration is enabled in config
        if not self.config.execution.enable_arbitration:
            self.logger.info("Arbitration disabled in configuration")
            # Return a no-op arbitration layer that just passes through responses
            from .arbitration.layer import NoOpArbitrationLayer
            return NoOpArbitrationLayer()
        
        return ConcreteArbitrationLayer()
    
    def _create_synthesis_layer(self) -> SynthesisLayer:
        """Create the synthesis layer."""
        self.logger.info("Creating synthesis layer")
        
        # Check if synthesis is enabled in config
        if not self.config.execution.enable_synthesis:
            self.logger.info("Synthesis disabled in configuration")
            # Return a no-op synthesis layer that just returns the first response
            from .synthesis.layer import NoOpSynthesisLayer
            return NoOpSynthesisLayer()
        
        return SynthesisLayerImpl()
    
    def create_models_from_config(self) -> Dict[str, AIModel]:
        """
        Create all model instances from configuration.
        
        Returns:
            Dict mapping model names to model instances
        """
        models = {}
        
        for model_name, model_config in self.config.models.items():
            if model_config.enabled:
                try:
                    model = self._create_model_instance(model_name, model_config)
                    models[model_name] = model
                    self.logger.info(f"Created model instance: {model_name}")
                except Exception as e:
                    self.logger.error(f"Failed to create model {model_name}: {str(e)}")
        
        return models
    
    def validate_configuration(self) -> List[str]:
        """
        Validate the configuration and return any issues found.
        
        Returns:
            List of validation error messages
        """
        issues = []
        
        try:
            self.config.validate()
        except ValueError as e:
            issues.append(f"Configuration validation failed: {str(e)}")
        
        # Check if at least one model is enabled
        enabled_models = [name for name, config in self.config.models.items() if config.enabled]
        if not enabled_models:
            issues.append("No models are enabled in configuration")
        
        # Check for required environment variables
        for model_name, model_config in self.config.models.items():
            if model_config.enabled and model_config.api_key_env:
                import os
                if not os.getenv(model_config.api_key_env):
                    issues.append(f"Environment variable {model_config.api_key_env} not set for model {model_name}")
        
        return issues