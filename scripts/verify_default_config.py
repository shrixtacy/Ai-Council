
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_council.utils.config import load_config

def verify_default_config():
    config_path = Path("config/ai_council.yaml")
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        return False

    try:
        config = load_config(config_path)
        if config.execution.enable_arbitration:
            print("SUCCESS: Arbitration layer is ENABLED by default.")
            return True
        else:
            print("FAILURE: Arbitration layer is DISABLED.")
            return False
    except Exception as e:
        print(f"Error loading config: {e}")
        return False

if __name__ == "__main__":
    if verify_default_config():
        sys.exit(0)
    else:
        sys.exit(1)
