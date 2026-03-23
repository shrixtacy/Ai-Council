import pytest
from ai_council.main import AICouncil
from ai_council.utils.config import AICouncilConfig

def test_aicouncil_init(temp_config_file):
    """Test that AICouncil can be initialized with a config file."""
    council = AICouncil(config_path=temp_config_file)
    assert council is not None
    assert council.orchestration_layer is not None
