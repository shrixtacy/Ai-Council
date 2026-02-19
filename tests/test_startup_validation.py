
import pytest
import os
from unittest.mock import patch, MagicMock
from ai_council.main import AICouncil
from ai_council.utils.config import AICouncilConfig, ModelConfig
from ai_council.factory import AICouncilFactory

class TestStartupValidation:
    @pytest.fixture
    def mock_config(self):
        config = AICouncilConfig()
        # Enable a model that requires an API key
        config.models["test-model"] = ModelConfig(
            name="test-model",
            provider="openai",
            api_key_env="TEST_API_KEY",
            enabled=True
        )
        return config

    def test_startup_fails_missing_env_var(self, mock_config):
        """Test that AICouncil raises RuntimeError when required env var is missing."""
        # We need to mock load_config to return our custom config
        with patch("ai_council.main.load_config", return_value=mock_config):
            # Ensure environment does NOT have the key
            with patch.dict(os.environ, {}, clear=True):
                # We mock create_orchestration_layer to prevent full system startup,
                # but we want the validation logic (which calls validate_configuration) to run.
                # Since validation happens *before* create_orchestration_layer in our plan,
                # this mock shouldn't even be reached if validation fails as expected.
                with patch.object(AICouncilFactory, "create_orchestration_layer"):
                    with pytest.raises(RuntimeError) as excinfo:
                        AICouncil()
                    assert "Environment variable TEST_API_KEY not set" in str(excinfo.value)

    def test_startup_succeeds_with_env_var(self, mock_config):
        """Test that AICouncil starts up when required env var is present."""
        with patch("ai_council.main.load_config", return_value=mock_config):
            # Ensure environment HAS the key
            with patch.dict(os.environ, {"TEST_API_KEY": "dummy-key"}):
                with patch.object(AICouncilFactory, "create_orchestration_layer"):
                    # Should not raise
                    AICouncil()
