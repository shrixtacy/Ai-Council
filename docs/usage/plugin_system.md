# Plugin System

AI Council supports a manifest-based plugin system that discovers plugin folders under the `plugins/` directory.

## Plugin folder structure

A manifest-based plugin lives in its own folder under `plugins/`.

Example:

```
plugins/example_plugin/
  plugin.py
  plugin.yaml
```

The manifest can be either `plugin.yaml`, `plugin.yml`, or `plugin.json`.

## Manifest fields

Required fields:

- `name`: Unique plugin name
- `version`: Plugin version
- `entry_point`: Python entry point for the plugin registration function

Optional fields:

- `description`: Free-form plugin description
- `hooks`: Map hook names to entry points
- `routing_rules`: List of routing rule definitions

### Example `plugin.yaml`

```yaml
name: example-plugin
version: "1.0.0"
description: "Example manifest-based plugin for AI Council."
entry_point: example_plugin.plugin:register
hooks:
  pre_execution: example_plugin.plugin:pre_execution
  post_arbitration: example_plugin.plugin:post_arbitration
  post_synthesis: example_plugin.plugin:post_synthesis
routing_rules:
  - name: example-plugin-cost-aware
    task_types:
      - reasoning
    enabled: true
    weight: 0.5
```

## `plugin.py` example

The plugin module should expose a callable that can register hooks and routing rules using the plugin context.

```python
from ai_council.core.models import ExecutionMode


def register(context):
  # Hooks are declared in the manifest under `hooks`.
  # Routing rules are declared in the manifest under `routing_rules`.
  return None


def pre_execution(user_input: str, execution_mode: ExecutionMode):
    return None


def post_arbitration(validated_responses, explanation):
    return None


def post_synthesis(final_response):
    return None
```

## Hooks

Supported hook names:

- `pre_execution`
- `post_arbitration`
- `post_synthesis`

Hooks may be registered by manifest field entries under `hooks`, and they are invoked at runtime by the orchestration layer.

## Routing rules

Plugins can add routing rules directly from the manifest under `routing_rules`.
These rules are registered in the AI Council config and can influence model selection.

## Usage

AI Council automatically discovers manifest plugins during startup from `config.plugin_dir` (default `./plugins`).

To use manifest-based plugins:

1. Create a plugin folder under `plugins/`
2. Add a manifest file (`plugin.yaml`, `plugin.yml`, or `plugin.json`)
3. Add the plugin module and entry point file
4. Start AI Council normally

If you need to preserve existing configuration-based plugins, use `config.plugins` entries with `module_path`/`class_name` or `entry_point`.
