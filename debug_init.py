import sys
import os
import yaml
import tempfile
from pathlib import Path

# Add current directory to path before ai_council imports
sys.path.append(os.getcwd())

from ai_council.main import AICouncil
from ai_council.utils.config import AICouncilConfig

def debug_init():
    temp_config_path = None
    try:
        # Create a dummy config dict
        config_dict = {
            "execution": {
                "default_mode": "balanced",
                "max_parallel_executions": 5,
                "max_retries": 3,
                "default_timeout_seconds": 60.0,
                "enable_arbitration": True,
                "enable_synthesis": True,
                "default_accuracy_requirement": 0.8
            },
            "cost": {
                "max_cost_per_request": 1.0
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
        
        # Write to a secure temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_dict, f)
            temp_config_path = Path(f.name)
            
        print(f"Loading config from {temp_config_path.absolute()}")
        
        print("Initializing AICouncil...")
        council = AICouncil(config_path=temp_config_path)
        print("AICouncil initialized successfully")
        
    except (OSError, yaml.YAMLError, ValueError, RuntimeError) as e:
        print(f"An error occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {str(e)}")
        raise
    finally:
        # Cleanup
        if temp_config_path and temp_config_path.exists():
            try:
                temp_config_path.unlink()
                print(f"Cleaned up temporary config at {temp_config_path}")
            except Exception as cleanup_err:
                print(f"Failed to cleanup {temp_config_path}: {cleanup_err}")

if __name__ == "__main__":
    debug_init()
