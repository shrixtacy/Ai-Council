
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import ai_council
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_council.main import AICouncil
from ai_council.core.models import FinalResponse
from ai_council.core.exceptions import (
    ConfigurationError, ValidationError, AuthenticationError, 
    ModelTimeoutError, RateLimitError, ProviderError, OrchestrationError, AICouncilError
)

class TestErrorHandling(unittest.TestCase):
    def setUp(self):
        # Mock load_config to avoid file system reads
        self.config_patcher = patch('ai_council.main.load_config')
        self.mock_load_config = self.config_patcher.start()
        
        # Mock configure_logging to suppress output
        self.logging_patcher = patch('ai_council.main.configure_logging')
        self.mock_configure_logging = self.logging_patcher.start()
        
        # Mock AICouncilFactory
        self.factory_patcher = patch('ai_council.main.AICouncilFactory')
        self.mock_factory_cls = self.factory_patcher.start()
        self.mock_factory = self.mock_factory_cls.return_value
        
        # Setup factory validation to pass
        self.mock_factory.validate_configuration.return_value = []
        
        # Create AICouncil instance
        self.ai_council = AICouncil()
        
        # Mock orchestration_layer
        self.ai_council.orchestration_layer = MagicMock()

    def tearDown(self):
        self.config_patcher.stop()
        self.logging_patcher.stop()
        self.factory_patcher.stop()

    def test_configuration_error(self):
        # ConfigurationError is usually raised within orchestrator if config is bad at runtime
        # asking orchestrator to raise it
        self.ai_council.orchestration_layer.process_request.side_effect = ConfigurationError("Config invalid")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "ConfigurationError")
        self.assertIn("Config invalid", response.error_message)

    def test_validation_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = ValidationError("Invalid input")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "ValidationError")
        self.assertIn("Invalid input", response.error_message)

    def test_authentication_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = AuthenticationError("Auth failed")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "AuthenticationError")
        self.assertIn("Auth failed", response.error_message)

    def test_timeout_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = ModelTimeoutError("Timeout")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "ModelTimeoutError")
        self.assertIn("Timeout", response.error_message)
        
    def test_rate_limit_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = RateLimitError("Rate limit exceeded")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "RateLimitError")
        self.assertIn("Rate limit exceeded", response.error_message)
        
    def test_provider_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = ProviderError("Provider failed")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "ProviderError")
        self.assertIn("Provider failed", response.error_message)
        
    def test_orchestration_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = OrchestrationError("Orchestration failed")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "OrchestrationError")
        self.assertIn("Orchestration failed", response.error_message)

    def test_generic_ai_council_error(self):
        self.ai_council.orchestration_layer.process_request.side_effect = AICouncilError("Generic error")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "AICouncilError")
        self.assertIn("Generic error", response.error_message)
        
    def test_unexpected_exception(self):
        self.ai_council.orchestration_layer.process_request.side_effect = RuntimeError("Unexpected crash")
        
        response = self.ai_council.process_request("test")
        
        self.assertFalse(response.success)
        self.assertEqual(response.error_type, "SystemError")
        self.assertIn("Unexpected crash", response.error_message)

if __name__ == '__main__':
    unittest.main()
