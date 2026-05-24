import json
from pathlib import Path

import pytest
import yaml

from ai_council.core.models import TaskType
from ai_council.utils.config import AICouncilConfig, PluginConfig
from ai_council.utils.plugin_manager import PluginError, PluginManager, create_plugin_manager


def _write_example_plugin(plugin_dir: Path, manifest_file_name: str = "plugin.yaml") -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_code = """from ai_council.core.models import ExecutionMode


def register(context):
    # The routing rule is declared through the manifest.
    return None


def pre_execution(user_input: str, execution_mode: ExecutionMode):
    return None


def post_arbitration(validated_responses, explanation):
    return None


def post_synthesis(final_response):
    return None
"""
    (plugin_dir / "plugin.py").write_text(plugin_code, encoding="utf-8")

    manifest = {
        "name": "example-plugin",
        "version": "1.0.0",
        "description": "Example manifest-based plugin.",
        "entry_point": "example_plugin.plugin:register",
        "hooks": {
            "pre_execution": "example_plugin.plugin:pre_execution",
            "post_arbitration": "example_plugin.plugin:post_arbitration",
            "post_synthesis": "example_plugin.plugin:post_synthesis",
        },
        "routing_rules": [
            {
                "name": "example-plugin-cost-aware",
                "task_types": ["reasoning"],
                "enabled": True,
                "weight": 0.5,
            }
        ],
    }
    (plugin_dir / manifest_file_name).write_text(yaml.safe_dump(manifest), encoding="utf-8")


@pytest.mark.parametrize("manifest_file_name", ["plugin.yaml", "plugin.yml", "plugin.json"])
def test_manifest_plugin_discovery_and_hook_registration(tmp_path: Path, manifest_file_name: str):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "example_plugin"
    _write_example_plugin(plugin_dir, manifest_file_name)

    if manifest_file_name.endswith(".json"):
        yaml_data = yaml.safe_load((plugin_dir / manifest_file_name).read_text(encoding="utf-8"))
        (plugin_dir / manifest_file_name).write_text(
            json.dumps(yaml_data),
            encoding="utf-8",
        )

    config = AICouncilConfig(plugin_dir=str(plugins_root))
    manager = create_plugin_manager(config)

    assert "example-plugin" in manager.loaded_plugins
    assert len(manager.plugin_context.pre_execution_hooks) == 1
    assert len(manager.plugin_context.post_arbitration_hooks) == 1
    assert len(manager.plugin_context.post_synthesis_hooks) == 1
    assert len(manager.plugin_context.routing_rules) == 1
    assert manager.plugin_context.routing_rules[0].name == "example-plugin-cost-aware"
    assert manager.plugin_context.routing_rules[0].task_types[0] == TaskType.REASONING


def test_manifest_plugin_validation_requires_entry_point(tmp_path: Path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "bad_plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"name": "bad-plugin", "version": "1.0.0"}),
        encoding="utf-8"
    )

    config = AICouncilConfig(plugin_dir=str(plugins_root))
    manager = PluginManager(config)

    with pytest.raises(PluginError, match="missing required fields"):
        manager.load_manifest_plugin(plugin_dir, {"name": "bad-plugin", "version": "1.0.0"})


def test_config_entry_point_plugin_loads_from_plugin_dir(tmp_path: Path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "example_plugin"
    _write_example_plugin(plugin_dir)

    config = AICouncilConfig(
        plugin_dir=str(plugins_root),
        plugins={
            "example-plugin": PluginConfig(
                name="example-plugin",
                entry_point="example_plugin.plugin:register",
                enabled=True,
            )
        },
    )

    manager = create_plugin_manager(config)
    assert "example-plugin" in manager.loaded_plugins


def test_manifest_metadata_merges_with_existing_config_plugin(tmp_path: Path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "example_plugin"
    _write_example_plugin(plugin_dir)

    config = AICouncilConfig(
        plugin_dir=str(plugins_root),
        plugins={
            "example-plugin": PluginConfig(
                name="example-plugin",
                config={"override": "from-config"},
                enabled=True,
            )
        },
    )

    manager = create_plugin_manager(config)
    merged = manager.config.plugins["example-plugin"]

    assert merged.entry_point == "example_plugin.plugin:register"
    assert merged.config["override"] == "from-config"
    assert len(manager.plugin_context.pre_execution_hooks) == 1
    assert len(manager.plugin_context.routing_rules) == 1
