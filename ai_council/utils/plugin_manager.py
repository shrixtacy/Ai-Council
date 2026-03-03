"""Plugin management system for AI Council."""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Type, Any, Optional, Callable
from ai_council.core.logger import get_logger

from ..core.interfaces import AIModel, AnalysisEngine, TaskDecomposer, ExecutionAgent
from ..core.interfaces import ArbitrationLayer, SynthesisLayer, ModelRegistry
from .config import PluginConfig, AICouncilConfig

logger = get_logger(__name__)


class PluginError(Exception):
    """Exception raised when plugin operations fail."""
    pass


class PluginManager:
    """Manages loading and registration of plugins for AI Council."""
    
    def __init__(self, config: AICouncilConfig):
        """Initialize the plugin manager.
        
        Args:
            config: The AI Council configuration
        """
        self.config = config
        self.loaded_plugins: Dict[str, Any] = {}
        self.plugin_instances: Dict[str, Any] = {}
        self.plugin_types: Dict[str, Type] = {}
        
        # Supported plugin interfaces
        self.supported_interfaces = {
            'AIModel': AIModel,
            'AnalysisEngine': AnalysisEngine,
            'TaskDecomposer': TaskDecomposer,
            'ExecutionAgent': ExecutionAgent,
            'ArbitrationLayer': ArbitrationLayer,
            'SynthesisLayer': SynthesisLayer,
            'ModelRegistry': ModelRegistry,
        }
    
    def load_all_plugins(self) -> None:
        """Load all enabled plugins from configuration."""
        for plugin_name, plugin_config in self.config.plugins.items():
            if plugin_config.enabled:
                try:
                    self.load_plugin(plugin_name, plugin_config)
                except Exception as e:
                    logger.error("Failed to load plugin", extra={"plugin_name": plugin_name, "error": str(e)})
                    if self.config.debug:
                        raise
    
    def load_plugin(self, plugin_name: str, plugin_config: PluginConfig) -> Any:
        """Load a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            plugin_config: Configuration for the plugin
            
        Returns:
            The loaded plugin class
            
        Raises:
            PluginError: If plugin loading fails
        """
        try:
            # Check dependencies
            self._check_dependencies(plugin_config.dependencies)
            
            # Import the plugin module
            module = importlib.import_module(plugin_config.module_path)
            
            # Get the plugin class
            if not hasattr(module, plugin_config.class_name):
                raise PluginError(f"Class {plugin_config.class_name} not found in module {plugin_config.module_path}")
            
            plugin_class = getattr(module, plugin_config.class_name)
            
            # Validate plugin interface
            interface_type = self._validate_plugin_interface(plugin_class)
            
            # Store plugin information
            self.loaded_plugins[plugin_name] = plugin_class
            self.plugin_types[plugin_name] = interface_type
            
            logger.info("Successfully loaded plugin", extra={"plugin_name": plugin_name, "interface_type": interface_type.__name__})
            return plugin_class
            
        except Exception as e:
            raise PluginError(f"Failed to load plugin {plugin_name}: {e}")
    
    def create_plugin_instance(self, plugin_name: str, *args, **kwargs) -> Any:
        """Create an instance of a loaded plugin.
        
        Args:
            plugin_name: Name of the plugin
            *args: Positional arguments for plugin constructor
            **kwargs: Keyword arguments for plugin constructor
            
        Returns:
            Plugin instance
            
        Raises:
            PluginError: If plugin is not loaded or instantiation fails
        """
        if plugin_name not in self.loaded_plugins:
            raise PluginError(f"Plugin {plugin_name} is not loaded")
        
        try:
            plugin_class = self.loaded_plugins[plugin_name]
            plugin_config = self.config.plugins[plugin_name]
            
            # Merge plugin config with provided kwargs
            merged_kwargs = {**plugin_config.config, **kwargs}
            
            # Create instance
            instance = plugin_class(*args, **merged_kwargs)
            self.plugin_instances[plugin_name] = instance
            
            logger.info("Created instance of plugin", extra={"plugin_name": plugin_name})
            return instance
            
        except Exception as e:
            raise PluginError(f"Failed to create instance of plugin {plugin_name}: {e}")
    
    def get_plugin_instance(self, plugin_name: str) -> Optional[Any]:
        """Get an existing plugin instance.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin instance if exists, None otherwise
        """
        return self.plugin_instances.get(plugin_name)
    
    def get_plugins_by_type(self, interface_type: Type) -> List[str]:
        """Get all loaded plugins that implement a specific interface.
        
        Args:
            interface_type: The interface type to filter by
            
        Returns:
            List of plugin names that implement the interface
        """
        matching_plugins = []
        for plugin_name, plugin_type in self.plugin_types.items():
            if issubclass(plugin_type, interface_type):
                matching_plugins.append(plugin_name)
        return matching_plugins
    
    def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin and clean up its resources.
        
        Args:
            plugin_name: Name of the plugin to unload
        """
        if plugin_name in self.plugin_instances:
            instance = self.plugin_instances[plugin_name]
            # Call cleanup method if it exists
            if hasattr(instance, 'cleanup'):
                try:
                    instance.cleanup()
                except Exception as e:
                    logger.warning("Error during cleanup of plugin", extra={"plugin_name": plugin_name, "error": str(e)})
            del self.plugin_instances[plugin_name]
        
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
        
        if plugin_name in self.plugin_types:
            del self.plugin_types[plugin_name]
        
        logger.info("Unloaded plugin", extra={"plugin_name": plugin_name})
    
    def reload_plugin(self, plugin_name: str) -> Any:
        """Reload a plugin (useful for development).
        
        Args:
            plugin_name: Name of the plugin to reload
            
        Returns:
            The reloaded plugin class
        """
        if plugin_name not in self.config.plugins:
            raise PluginError(f"Plugin {plugin_name} not found in configuration")
        
        # Unload existing plugin
        if plugin_name in self.loaded_plugins:
            self.unload_plugin(plugin_name)
        
        # Reload the module
        plugin_config = self.config.plugins[plugin_name]
        if plugin_config.module_path in sys.modules:
            importlib.reload(sys.modules[plugin_config.module_path])
        
        # Load the plugin again
        return self.load_plugin(plugin_name, plugin_config)
    
    def discover_plugins(self, plugin_dir: Optional[str] = None) -> List[str]:
        """Discover available plugins in the plugin directory.
        
        Args:
            plugin_dir: Directory to search for plugins (defaults to config.plugin_dir)
            
        Returns:
            List of discovered plugin module paths
        """
        if plugin_dir is None:
            plugin_dir = self.config.plugin_dir
        
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            return []
        
        discovered_plugins = []
        
        # Look for Python files in the plugin directory
        for py_file in plugin_path.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            # Convert file path to module path
            relative_path = py_file.relative_to(plugin_path)
            module_path = str(relative_path.with_suffix("")).replace("/", ".").replace("\\", ".")
            
            # Try to import and inspect the module
            try:
                spec = importlib.util.spec_from_file_location(module_path, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for classes that implement our interfaces
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if self._is_plugin_class(obj):
                            discovered_plugins.append(f"{module_path}.{name}")
                            
            except Exception as e:
                logger.debug("Could not inspect py file", extra={"py_file": py_file, "error": str(e)})
        
        return discovered_plugins
    
    def register_plugin_from_discovery(self, module_class_path: str, plugin_name: Optional[str] = None) -> str:
        """Register a plugin discovered through discovery.
        
        Args:
            module_class_path: Module path and class name (e.g., "my_plugin.MyModel")
            plugin_name: Optional name for the plugin (defaults to class name)
            
        Returns:
            The registered plugin name
        """
        if "." not in module_class_path:
            raise PluginError("Invalid module class path format")
        
        module_path, class_name = module_class_path.rsplit(".", 1)
        
        if plugin_name is None:
            plugin_name = class_name.lower()
        
        plugin_config = PluginConfig(
            name=plugin_name,
            module_path=module_path,
            class_name=class_name,
            enabled=True,
        )
        
        self.config.add_plugin(plugin_config)
        return plugin_name
    
    def _check_dependencies(self, dependencies: List[str]) -> None:
        """Check if plugin dependencies are satisfied.
        
        Args:
            dependencies: List of required dependencies
            
        Raises:
            PluginError: If dependencies are not satisfied
        """
        for dependency in dependencies:
            try:
                importlib.import_module(dependency)
            except ImportError:
                raise PluginError(f"Missing dependency: {dependency}")
    
    def _validate_plugin_interface(self, plugin_class: Type) -> Type:
        """Validate that a plugin class implements a supported interface.
        
        Args:
            plugin_class: The plugin class to validate
            
        Returns:
            The interface type that the plugin implements
            
        Raises:
            PluginError: If plugin doesn't implement a supported interface
        """
        for interface_name, interface_type in self.supported_interfaces.items():
            if issubclass(plugin_class, interface_type):
                return interface_type
        
        raise PluginError(f"Plugin class {plugin_class.__name__} does not implement any supported interface")
    
    def _is_plugin_class(self, cls: Type) -> bool:
        """Check if a class is a valid plugin class.
        
        Args:
            cls: The class to check
            
        Returns:
            True if the class is a valid plugin
        """
        if not inspect.isclass(cls):
            return False
        
        # Check if it implements any of our interfaces
        for interface_type in self.supported_interfaces.values():
            if issubclass(cls, interface_type) and cls != interface_type:
                return True
        
        return False
    
    def get_plugin_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all loaded plugins.
        
        Returns:
            Dictionary with plugin information
        """
        info = {}
        for plugin_name in self.loaded_plugins:
            plugin_config = self.config.plugins.get(plugin_name)
            plugin_type = self.plugin_types.get(plugin_name)
            has_instance = plugin_name in self.plugin_instances
            
            info[plugin_name] = {
                'config': plugin_config.__dict__ if plugin_config else None,
                'interface_type': plugin_type.__name__ if plugin_type else None,
                'has_instance': has_instance,
                'enabled': plugin_config.enabled if plugin_config else False,
            }
        
        return info


def create_plugin_manager(config: AICouncilConfig) -> PluginManager:
    """Create and initialize a plugin manager.
    
    Args:
        config: The AI Council configuration
        
    Returns:
        Initialized plugin manager
    """
    manager = PluginManager(config)
    manager.load_all_plugins()
    return manager