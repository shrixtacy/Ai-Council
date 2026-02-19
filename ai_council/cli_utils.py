import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from .core.models import ExecutionMode

if TYPE_CHECKING:
    from .main import AICouncil


class CLIHandler:
    """
    Handles Command Line Interface interactions for AI Council.
    """

    def __init__(self):
        self.parser = self._setup_arg_parser()

    def _setup_arg_parser(self) -> argparse.ArgumentParser:
        """Configures and returns the argument parser."""
        parser = argparse.ArgumentParser(description="AI Council - Multi-Agent Orchestration System")
        parser.add_argument("--config", type=Path, help="Path to configuration file")
        parser.add_argument("--mode", choices=["fast", "balanced", "best_quality"], 
                           default="balanced", help="Execution mode")
        parser.add_argument("--estimate-only", action="store_true", 
                           help="Only estimate cost and time, don't execute")
        parser.add_argument("--analyze-tradeoffs", action="store_true",
                           help="Analyze cost vs quality trade-offs")
        parser.add_argument("--status", action="store_true",
                           help="Show system status and exit")
        parser.add_argument("--interactive", action="store_true",
                           help="Start interactive mode")
        parser.add_argument("request", nargs="?", help="User request to process")
        return parser

    def parse_args(self) -> argparse.Namespace:
        """Parses command line arguments."""
        return self.parser.parse_args()

    def print_system_status(self, ai_council: 'AICouncil'):
        """Prints the current system status."""
        status = ai_council.get_system_status()
        print("\n" + "="*60)
        print("AI COUNCIL SYSTEM STATUS")
        print("="*60)
        print(f"Status: {status.get('status', 'unknown')}")
        
        if 'available_models' in status:
            print(f"\nAvailable Models ({len(status['available_models'])}):")
            for model in status['available_models']:
                print(f"  - {model['id']}: {', '.join(model['capabilities'])}")
        
        if 'health' in status:
            health = status['health']
            print(f"\nSystem Health: {health.get('overall_health', 'unknown')}")
            if 'circuit_breakers' in health:
                print(f"Circuit Breakers: {len(health['circuit_breakers'])} active")
        
        if 'configuration' in status:
            config = status['configuration']
            print(f"\nConfiguration:")
            print(f"  Default Mode: {config.get('default_execution_mode', 'unknown')}")
            print(f"  Max Parallel: {config.get('max_parallel_executions', 'unknown')}")
            print(f"  Max Cost: ${config.get('max_cost_per_request', 0)}")

    def handle_interactive_mode(self, ai_council: 'AICouncil', default_mode: str):
        """Runs the interactive REPL loop."""
        print("\n" + "="*60)
        print("AI COUNCIL INTERACTIVE MODE")
        print("="*60)
        print("Enter your requests (type 'quit' to exit, 'status' for system status)")
        print("Commands: estimate <request>, analyze <request>, help")
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'status':
                    status = ai_council.get_system_status()
                    print(f"System Status: {status.get('status', 'unknown')}")
                    continue
                elif user_input.lower() == 'help':
                    print("Commands:")
                    print("  estimate <request> - Estimate cost and time")
                    print("  analyze <request>  - Analyze trade-offs")
                    print("  status            - Show system status")
                    print("  quit              - Exit interactive mode")
                    print("  <request>         - Process request")
                    continue
                elif user_input.startswith('estimate '):
                    request = user_input[9:]
                    # For interactive mode, we use the default mode from args if not specified otherwise in command
                    # But the requirement was to estimate. The original code used args.mode.
                    # We will assume args.mode validation happened before or defaults are handled.
                    # Here we treat 'default_mode' as the one passed from main args.
                    estimate = ai_council.estimate_cost(request, ExecutionMode(default_mode))
                    self._print_estimate(estimate)
                    continue
                elif user_input.startswith('analyze '):
                    request = user_input[8:]
                    analysis = ai_council.analyze_tradeoffs(request)
                    self._print_analysis(analysis)
                    continue
                
                if not user_input:
                    continue
                
                # Process the request
                execution_mode = ExecutionMode(default_mode)
                response = ai_council.process_request(user_input, execution_mode)
                
                self._print_response(response)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")

    def handle_estimate_only(self, ai_council: 'AICouncil', request: str, mode: str):
        """Handles estimate-only requests."""
        execution_mode = ExecutionMode(mode)
        estimate = ai_council.estimate_cost(request, execution_mode)
        print(f"\nCost Estimate for '{request[:50]}...':")
        self._print_estimate(estimate)

    def handle_tradeoff_analysis(self, ai_council: 'AICouncil', request: str):
        """Handles trade-off analysis requests."""
        analysis = ai_council.analyze_tradeoffs(request)
        print(f"\nTrade-off Analysis for '{request[:50]}...':")
        self._print_analysis(analysis)

    def process_single_request(self, ai_council: 'AICouncil', request: str, mode: str):
        """Processes a single request."""
        execution_mode = ExecutionMode(mode)
        print(f"\nProcessing request in {execution_mode.value} mode...")
        response = ai_council.process_request(request, execution_mode)
        
        print(f"\n" + "="*60)
        print("AI COUNCIL RESPONSE")
        print("="*60)
        self._print_response(response)

    def _print_estimate(self, estimate: Dict[str, Any]):
        print(f"  Estimated Cost: ${estimate.get('estimated_cost', 0):.4f}")
        print(f"  Estimated Time: {estimate.get('estimated_time', 0):.1f}s")
        print(f"  Confidence: {estimate.get('confidence', 0):.2f}")

    def _print_analysis(self, analysis: Dict[str, Any]):
        if 'error' not in analysis:
            for mode, data in analysis.items():
                if mode != 'recommendations':
                    print(f"  {mode}: ${data.get('total_cost', 0):.4f}, "
                          f"{data.get('total_time', 0):.1f}s, "
                          f"quality: {data.get('average_quality', 0):.2f}")
            
            if 'recommendations' in analysis:
                print(f"\nRecommendations:")
                for criterion, recommendation in analysis['recommendations'].items():
                    print(f"  {criterion.replace('_', ' ').title()}: {recommendation}")
        else:
             print(f"Analysis failed: {analysis['error']}")

    def _print_response(self, response):
        if response.success:
            print(f"Content: {response.content}")
            print(f"\nConfidence: {response.overall_confidence:.2f}")
            print(f"Models Used: {', '.join(response.models_used)}")
            
            if response.execution_metadata:
                print(f"Execution Time: {response.execution_metadata.total_execution_time:.2f}s")
                if response.cost_breakdown:
                    print(f"Total Cost: ${response.cost_breakdown.total_cost:.4f}")
        else:
            print(f"Request failed: {response.error_message}")
