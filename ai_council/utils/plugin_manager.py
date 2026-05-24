"""Plugin management system for AI Council."""

import importlib
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import yaml

from ai_council.core.logger import get_logger

from ..core.interfaces import AIModel, AnalysisEngine, TaskDecomposer, ExecutionAgent
from ..core.interfaces import ArbitrationLayer, SynthesisLayer, ModelRegistry
from ..core.models import ExecutionMode, Priority, RiskLevel, TaskType
from .config import PluginConfig, AICouncilConfig, RoutingRule

logger = get_logger(__name__)


class PluginError(Exception):
    """Exception raised when plugin operations fail."""
    pass


class PluginContext:
    """Registry for plugin runtime hooks and routing rules."""

    def __init__(self, config: AICouncilConfig, manager: "PluginManager"):
        self.config = config
        self.manager = manager
        self.pre_execution_hooks: List[Callable[[str, ExecutionMode], Any]] = []
        self.post_arbitration_hooks: List[Callable[[List[Any], Any], Any]] = []
        self.post_synthesis_hooks: List[Callable[[Any], Any]] = []
        self.routing_rules: List[RoutingRule] = []

    def register_pre_execution_hook(self, hook: Callable[[str, ExecutionMode], Any]) -> None:
        self.pre_execution_hooks.append(hook)

    def register_post_arbitration_hook(self, hook: Callable[[List[Any], Any], Any]) -> None:
        self.post_arbitration_hooks.append(hook)

    def register_post_synthesis_hook(self, hook: Callable[[Any], Any]) -> None:
        self.post_synthesis_hooks.append(hook)

    def register_routing_rule(self, rule: Any) -> None:
        if isinstance(rule, dict):
            rule = self.manager._normalize_routing_rule_from_manifest(rule)
        if not isinstance(rule, RoutingRule):
            raise PluginError("Routing rule must be a RoutingRule or dict")

        self.config.add_routing_rule(rule)
        self.routing_rules.append(rule)

    def run_pre_execution_hooks(self, user_input: str, execution_mode: ExecutionMode) -> None:
        for hook in self.pre_execution_hooks:
            try:
                hook(user_input, execution_mode)
            except Exception as e:
                logger.warning("Plugin pre-execution hook failed", extra={"error": str(e)})

    def run_post_arbitration_hooks(self, validated_responses: List[Any], explanation: Any) -> None:
        for hook in self.post_arbitration_hooks:
            try:
                hook(validated_responses, explanation)
            except Exception as e:
                logger.warning("Plugin post-arbitration hook failed", extra={"error": str(e)})

    def run_post_synthesis_hooks(self, final_response: Any) -> None:
        for hook in self.post_synthesis_hooks:
            try:
                hook(final_response)
            except Exception as e:
                logger.warning("Plugin post-synthesis hook failed", extra={"error": str(e)})


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
        self.manifest_plugins: Dict[str, Dict[str, Any]] = {}
        self.plugin_context = PluginContext(config, self)
        
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
        """Load all enabled plugins from configuration and discover manifest-based plugins."""
        # Discover and merge manifest-based plugins first, before loading config plugins.
        for plugin_folder, manifest_data in self.discover_plugin_manifests():
            try:
                self.load_manifest_plugin(plugin_folder, manifest_data)
            except Exception as e:
                logger.error("Failed to load manifest plugin", extra={"plugin_folder": str(plugin_folder), "error": str(e)})
                if self.config.debug:
                    raise

        # Load explicit plugin definitions from config.
        for plugin_name, plugin_config in self.config.plugins.items():
            if plugin_config.enabled:
                try:
                    self.load_plugin(plugin_name, plugin_config)
                except Exception as e:
                    logger.error("Failed to load plugin", extra={"plugin_name": plugin_name, "error": str(e)})
                    if self.config.debug:
                        raise
    
    def load_plugin(self, plugin_name: str, plugin_config: PluginConfig, plugin_base_path: Optional[Path] = None) -> Any:
        """Load a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            plugin_config: Configuration for the plugin
            plugin_base_path: Optional path used to resolve entry points
            
        Returns:
            The loaded plugin class or registered plugin object
            
        Raises:
            PluginError: If plugin loading fails
        """
        try:
            # Check dependencies
            self._check_dependencies(plugin_config.dependencies)

            if plugin_config.entry_point:
                # Load entry point style plugins that register hooks/context
                base_path = plugin_base_path or Path(self.config.plugin_dir)
                entry_callable = self._get_entry_point_callable(plugin_config.entry_point, base_path)
                plugin_obj = entry_callable(self.plugin_context)
                self.loaded_plugins[plugin_name] = plugin_obj or entry_callable
                logger.info("Successfully loaded plugin entry point", extra={"plugin_name": plugin_name})
                return plugin_obj

            # Preserve existing module/class plugin loading behavior
            module = importlib.import_module(plugin_config.module_path)
            if not hasattr(module, plugin_config.class_name):
                raise PluginError(f"Class {plugin_config.class_name} not found in module {plugin_config.module_path}")
            plugin_class = getattr(module, plugin_config.class_name)
            interface_type = self._validate_plugin_interface(plugin_class)
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

    def discover_plugin_manifests(self, plugin_dir: Optional[str] = None) -> List[Tuple[Path, Dict[str, Any]]]:
        """Discover plugin manifest files under the plugin directory."""
        if plugin_dir is None:
            plugin_dir = self.config.plugin_dir

        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            return []

        manifests = []
        for plugin_folder in plugin_path.iterdir():
            if not plugin_folder.is_dir():
                continue

            manifest_path = None
            for candidate in (plugin_folder / 'plugin.yaml', plugin_folder / 'plugin.yml', plugin_folder / 'plugin.json'):
                if candidate.exists():
                    manifest_path = candidate
                    break

            if manifest_path is None:
                continue

            manifest_data = self._load_manifest_file(manifest_path)
            if manifest_data:
                manifests.append((plugin_folder, manifest_data))

        return manifests

    def load_manifest_plugin(self, plugin_folder: Path, manifest_data: Dict[str, Any]) -> None:
        """Load a plugin from a manifest file."""
        self._validate_manifest_data(manifest_data)

        plugin_name = manifest_data['name']
        existing_plugin = self.config.plugins.get(plugin_name)
        if existing_plugin is None and not manifest_data.get('enabled', True):
            logger.info("Manifest plugin disabled", extra={"plugin_name": plugin_name})
            return

        plugin_config = self._merge_manifest_into_plugin_config(
            plugin_name=plugin_name,
            manifest_data=manifest_data,
            existing_plugin=existing_plugin,
        )
        self.config.add_plugin(plugin_config)
        self.manifest_plugins[plugin_name] = manifest_data

        # Skip loading if plugin is disabled after merge
        if not plugin_config.enabled:
            logger.info("Manifest plugin disabled after merge", extra={"plugin_name": plugin_name})
            return

        # Register routing rules from plugin_config (post-merge source of truth)
        for routing_rule in plugin_config.routing_rules:
            try:
                self.plugin_context.register_routing_rule(routing_rule)
            except Exception as e:
                logger.warning("Could not register manifest routing rule", extra={"plugin_name": plugin_name, "error": str(e)})

        # Load the plugin entry point and call its register() function
        self.load_plugin(plugin_name, plugin_config, plugin_folder)

        # Register any hooks defined in plugin_config (post-merge source of truth)
        for hook_name, hook_entry in plugin_config.hooks.items():
            try:
                hook_callable = self._get_entry_point_callable(hook_entry, plugin_folder)
                self._register_hook(hook_name, hook_callable)
            except Exception as e:
                logger.warning("Could not load manifest hook", extra={"plugin_name": plugin_name, "hook": hook_name, "error": str(e)})

    def _load_manifest_file(self, manifest_path: Path) -> Optional[Dict[str, Any]]:
        try:
            if manifest_path.suffix.lower() == '.json':
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning("Failed to parse plugin manifest", extra={"manifest_path": str(manifest_path), "error": str(e)})
            return None

    def _validate_manifest_data(self, manifest_data: Dict[str, Any]) -> None:
        missing_fields = [field for field in ('name', 'version', 'entry_point') if field not in manifest_data or not manifest_data[field]]
        if missing_fields:
            raise PluginError(f"Plugin manifest missing required fields: {', '.join(missing_fields)}")

    def _merge_manifest_into_plugin_config(
        self,
        plugin_name: str,
        manifest_data: Dict[str, Any],
        existing_plugin: Optional[PluginConfig],
    ) -> PluginConfig:
        """Merge manifest metadata with existing config while preserving explicit config overrides."""
        if existing_plugin is None:
            return PluginConfig(
                name=plugin_name,
                entry_point=manifest_data['entry_point'],
                enabled=manifest_data.get('enabled', True),
                config=manifest_data.get('config', {}),
                dependencies=manifest_data.get('dependencies', []),
                version=manifest_data.get('version', '1.0.0'),
                description=manifest_data.get('description', ''),
                hooks=manifest_data.get('hooks', {}),
                routing_rules=manifest_data.get('routing_rules', []),
            )

        merged_config = {
            **manifest_data.get('config', {}),
            **existing_plugin.config,
        }
        merged_dependencies = existing_plugin.dependencies or manifest_data.get('dependencies', [])
        merged_hooks = {
            **manifest_data.get('hooks', {}),
            **existing_plugin.hooks,
        }
        merged_routing_rules = existing_plugin.routing_rules or manifest_data.get('routing_rules', [])

        effective_entry_point = existing_plugin.entry_point
        if not effective_entry_point and not existing_plugin.module_path:
            effective_entry_point = manifest_data['entry_point']

        return PluginConfig(
            name=plugin_name,
            module_path=existing_plugin.module_path,
            class_name=existing_plugin.class_name,
            entry_point=effective_entry_point,
            enabled=existing_plugin.enabled,
            config=merged_config,
            dependencies=merged_dependencies,
            version=existing_plugin.version or manifest_data.get('version', '1.0.0'),
            description=existing_plugin.description or manifest_data.get('description', ''),
            hooks=merged_hooks,
            routing_rules=merged_routing_rules,
        )

    def _convert_enum_list(self, values: List[Any], enum_class: Type) -> List[Any]:
        """Convert manifest string values to enum values when possible."""
        converted: List[Any] = []
        for value in values:
            if not isinstance(value, str):
                converted.append(value)
                continue

            candidates = [value, value.lower(), value.upper()]
            converted_value = value
            for candidate in candidates:
                try:
                    converted_value = enum_class(candidate)
                    break
                except ValueError:
                    continue
            converted.append(converted_value)
        return converted

    def _normalize_routing_rule_from_manifest(self, rule_data: Dict[str, Any]) -> RoutingRule:
        """Normalize routing rule dictionary values for enum-backed fields."""
        normalized = dict(rule_data)
        if 'task_types' in normalized:
            normalized['task_types'] = self._convert_enum_list(normalized['task_types'], TaskType)
        if 'priority_levels' in normalized:
            normalized['priority_levels'] = self._convert_enum_list(normalized['priority_levels'], Priority)
        if 'risk_levels' in normalized:
            normalized['risk_levels'] = self._convert_enum_list(normalized['risk_levels'], RiskLevel)
        if 'execution_modes' in normalized:
            normalized['execution_modes'] = self._convert_enum_list(normalized['execution_modes'], ExecutionMode)
        return RoutingRule(**normalized)

    def _get_entry_point_callable(self, entry_point: str, plugin_folder: Path) -> Callable:
        if ':' in entry_point:
            module_name, attr_name = entry_point.split(':', 1)
        elif '.' in entry_point:
            module_name, attr_name = entry_point.rsplit('.', 1)
        else:
            module_name, attr_name = entry_point, 'register'

        try:
            module = importlib.import_module(module_name)
        except ImportError:
            module = self._load_entry_point_module_from_path(module_name, plugin_folder)

        if not hasattr(module, attr_name):
            raise PluginError(f"Entry point {attr_name} not found in module {module_name}")

        hook_callable = getattr(module, attr_name)
        if not callable(hook_callable):
            raise PluginError(f"Entry point {entry_point} is not callable")
        return hook_callable

    def _load_entry_point_module_from_path(self, module_name: str, plugin_folder: Path):
        """Load a plugin module from explicit plugin paths without mutating sys.path globally."""
        module_parts = module_name.split('.')
        candidate_files: List[Path] = []

        if plugin_folder.name == module_parts[0] and len(module_parts) > 1:
            candidate_files.append(plugin_folder.joinpath(*module_parts[1:]).with_suffix('.py'))
        candidate_files.append(plugin_folder.joinpath(*module_parts).with_suffix('.py'))
        candidate_files.append(plugin_folder.parent.joinpath(*module_parts).with_suffix('.py'))

        for module_file in candidate_files:
            if not module_file.exists():
                continue
            spec = importlib.util.spec_from_file_location(module_name, module_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        raise PluginError(f"Could not import module for entry point {module_name} from plugin path {plugin_folder}")

    def _register_hook(self, hook_name: str, hook_callable: Callable) -> None:
        if hook_name == 'pre_execution':
            self.plugin_context.register_pre_execution_hook(hook_callable)
        elif hook_name == 'post_arbitration':
            self.plugin_context.register_post_arbitration_hook(hook_callable)
        elif hook_name == 'post_synthesis':
            self.plugin_context.register_post_synthesis_hook(hook_callable)
        else:
            raise PluginError(f"Unsupported hook name: {hook_name}")

    def _check_dependencies(self, dependencies: List[str]) -> None:
        """Check if plugin dependencies are satisfied."""
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