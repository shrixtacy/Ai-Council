#!/usr/bin/env python3
"""
Mode Comparison Example for AI Council.

This example demonstrates how to compare different execution modes (Fast, Balanced, 
Best Quality) to understand the trade-offs between speed, cost, and quality.

Use Cases:
- Compare response quality across modes for the same query
- Analyze cost-effectiveness for different types of tasks
- Benchmark performance for production deployment decisions

Prerequisites:
- API keys configured in web_app/backend/.env
- AI Council installed: pip install -e .
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass

# Add ai_council to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_council.core.models import ExecutionMode
from ai_council.utils.logging import configure_logging, get_logger


@dataclass
class ModeResult:
    """Results from a single execution mode."""
    mode: str
    execution_time: float
    estimated_cost: float
    quality_score: float
    response_preview: str
    success: bool
    error: str = ""


def compare_execution_modes(query: str) -> Dict[str, ModeResult]:
    """
    Compare all execution modes for a given query.
    
    Args:
        query: The user query to process
        
    Returns:
        Dictionary mapping mode names to their results
    """
    from ai_council.main import AICouncil
    
    # Initialize AI Council
    config_path = Path(__file__).parent.parent / "config" / "ai_council.yaml"
    council = AICouncil(config_path if config_path.exists() else None)
    
    modes = {
        "fast": ExecutionMode.FAST,
        "balanced": ExecutionMode.BALANCED,
        "best_quality": ExecutionMode.BEST_QUALITY
    }
    
    results = {}
    
    for mode_name, mode_enum in modes.items():
        print(f"\n{'='*50}")
        print(f"Testing {mode_name.upper()} mode...")
        print('='*50)
        
        start_time = time.time()
        
        try:
            response = council.process_request(query, mode_enum)
            execution_time = time.time() - start_time
            
            # Extract response details
            cost = response.cost_breakdown.total_cost if response.cost_breakdown else 0.0
            confidence = response.overall_confidence if response.success else 0.0
            content = response.content if response.success else response.error_message
            
            results[mode_name] = ModeResult(
                mode=mode_name,
                execution_time=execution_time,
                estimated_cost=cost,
                quality_score=confidence,
                response_preview=content[:200] + "..." if len(content) > 200 else content,
                success=response.success,
                error="" if response.success else response.error_message
            )
            
            print(f"✓ Completed in {execution_time:.2f}s")
            print(f"  Cost: ${cost:.6f}")
            print(f"  Quality Score: {confidence:.2%}")
            
        except Exception as e:
            execution_time = time.time() - start_time
            results[mode_name] = ModeResult(
                mode=mode_name,
                execution_time=execution_time,
                estimated_cost=0.0,
                quality_score=0.0,
                response_preview="",
                success=False,
                error=str(e)
            )
            print(f"✗ Failed: {str(e)}")
    
    return results


def print_comparison_report(results: Dict[str, ModeResult], query: str) -> None:
    """
    Print a formatted comparison report.
    
    Args:
        results: Dictionary of mode results
        query: The original query
    """
    print("\n")
    print("╔" + "═"*70 + "╗")
    print("║" + " MODE COMPARISON REPORT ".center(70) + "║")
    print("╚" + "═"*70 + "╝")
    
    print(f"\nQuery: {query[:80]}{'...' if len(query) > 80 else ''}")
    print("-"*72)
    
    # Header
    print(f"{'Mode':<15} {'Time (s)':<12} {'Cost ($)':<15} {'Quality':<12} {'Status':<10}")
    print("-"*72)
    
    # Results rows
    for mode_name, result in results.items():
        status = "✓ Success" if result.success else "✗ Failed"
        print(f"{mode_name.capitalize():<15} "
              f"{result.execution_time:<12.2f} "
              f"{result.estimated_cost:<15.6f} "
              f"{result.quality_score:<12.1%} "
              f"{status:<10}")
    
    print("-"*72)
    
    # Analysis
    print("\n📊 ANALYSIS:")
    
    successful_results = {k: v for k, v in results.items() if v.success}
    
    if successful_results:
        # Find fastest
        fastest = min(successful_results.values(), key=lambda x: x.execution_time)
        print(f"  ⚡ Fastest: {fastest.mode.capitalize()} ({fastest.execution_time:.2f}s)")
        
        # Find cheapest
        cheapest = min(successful_results.values(), key=lambda x: x.estimated_cost)
        print(f"  💰 Cheapest: {cheapest.mode.capitalize()} (${cheapest.estimated_cost:.6f})")
        
        # Find best quality
        best_quality = max(successful_results.values(), key=lambda x: x.quality_score)
        print(f"  🏆 Best Quality: {best_quality.mode.capitalize()} ({best_quality.quality_score:.1%})")
        
        # Calculate value score (quality / cost, higher is better)
        print("\n💡 RECOMMENDATIONS:")
        
        for mode_name, result in successful_results.items():
            if result.estimated_cost > 0:
                value = result.quality_score / result.estimated_cost
                print(f"  • {mode_name.capitalize()}: Value Score = {value:.2f}")
        
        # Provide recommendations
        print("\n📋 USE CASES:")
        print("  • Fast Mode: Quick iterations, prototyping, low-stakes queries")
        print("  • Balanced Mode: General use, good quality-to-cost ratio")
        print("  • Best Quality Mode: Critical decisions, production deployments")
    else:
        print("  ⚠️ All modes failed. Check API configuration and connectivity.")
    
    print("\n" + "="*72)


def run_sample_queries() -> None:
    """Run comparison on several sample queries to demonstrate capabilities."""
    
    sample_queries = [
        "Explain the differences between REST and GraphQL APIs",
        "What are the best practices for securing a Python web application?",
        "Compare machine learning and traditional programming approaches",
    ]
    
    print("\n" + "🚀 AI COUNCIL MODE COMPARISON DEMO ".center(72, "="))
    print("\nThis example compares Fast, Balanced, and Best Quality modes")
    print("to help you understand the trade-offs for different use cases.\n")
    
    # For demo, just use the first query
    query = sample_queries[0]
    
    print(f"Demo Query: {query}")
    print("-"*72)
    
    results = compare_execution_modes(query)
    print_comparison_report(results, query)


def interactive_mode() -> None:
    """Run in interactive mode, allowing custom queries."""
    
    print("\n" + " AI COUNCIL INTERACTIVE MODE ".center(72, "="))
    print("\nEnter your own query to compare across all execution modes.")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            query = input("Enter query: ").strip()
            
            if query.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            
            if not query:
                print("Please enter a query or 'exit' to quit.")
                continue
            
            results = compare_execution_modes(query)
            print_comparison_report(results, query)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compare AI Council execution modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mode_comparison_example.py                    # Run demo
  python mode_comparison_example.py --interactive     # Interactive mode
  python mode_comparison_example.py --query "Your question here"
        """
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Specific query to compare"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = "DEBUG" if args.verbose else "WARNING"
    configure_logging(level=log_level, format_json=False)
    
    if args.interactive:
        interactive_mode()
    elif args.query:
        results = compare_execution_modes(args.query)
        print_comparison_report(results, args.query)
    else:
        run_sample_queries()


if __name__ == "__main__":
    main()
