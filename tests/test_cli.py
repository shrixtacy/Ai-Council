import unittest
from unittest.mock import MagicMock, call
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_council.cli_utils import CLIHandler
from ai_council.core.models import ExecutionMode

class TestCLIHandler(unittest.TestCase):
    def setUp(self):
        self.cli_handler = CLIHandler()
        self.mock_ai_council = MagicMock()

    def test_setup_arg_parser(self):
        parser = self.cli_handler._setup_arg_parser()
        self.assertIsNotNone(parser)
        args = parser.parse_args(['--status', 'my_request'])
        self.assertTrue(args.status)
        self.assertEqual(args.request, 'my_request')

    def test_print_system_status(self):
        self.mock_ai_council.get_system_status.return_value = {
            'status': 'operational',
            'available_models': [{'id': 'model1', 'capabilities': ['chat']}],
            'health': {'overall_health': 'healthy'},
            'configuration': {'default_execution_mode': 'balanced'}
        }
        
        # Capture stdout to verify print output if needed, but for now just verify call
        self.cli_handler.print_system_status(self.mock_ai_council)
        self.mock_ai_council.get_system_status.assert_called_once()

    def test_handle_estimate_only(self):
        self.mock_ai_council.estimate_cost.return_value = {
            'estimated_cost': 0.1,
            'estimated_time': 1.0,
            'confidence': 0.9
        }
        self.cli_handler.handle_estimate_only(self.mock_ai_council, "test request", "balanced")
        self.mock_ai_council.estimate_cost.assert_called_once_with("test request", ExecutionMode.BALANCED)

    def test_handle_tradeoff_analysis(self):
        self.mock_ai_council.analyze_tradeoffs.return_value = {
            'balanced': {'total_cost': 0.1, 'total_time': 1.0, 'average_quality': 0.9}
        }
        self.cli_handler.handle_tradeoff_analysis(self.mock_ai_council, "test request")
        self.mock_ai_council.analyze_tradeoffs.assert_called_once_with("test request")

    def test_process_single_request(self):
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.content = "Response content"
        mock_response.overall_confidence = 0.95
        mock_response.models_used = ["model1"]
        mock_response.execution_metadata = MagicMock()
        mock_response.execution_metadata.total_execution_time = 1.5
        mock_response.cost_breakdown = MagicMock()
        mock_response.cost_breakdown.total_cost = 0.05
        
        self.mock_ai_council.process_request.return_value = mock_response
        
        self.cli_handler.process_single_request(self.mock_ai_council, "test request", "fast")
        self.mock_ai_council.process_request.assert_called_once_with("test request", ExecutionMode.FAST)

if __name__ == '__main__':
    unittest.main()
