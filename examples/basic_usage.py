#!/usr/bin/env python3
"""
Basic usage example for AI Council.

This example demonstrates how to use the core data models and configuration
system. Note that this is just the infrastructure - the actual orchestration
components will be implemented in later tasks.

Improved by: [Your Name/Contributor]
Changes: Added robust error handling, cost aggregation, and accuracy validation.
"""

import sys
import logging
from ai_council.core.models import (
    Task, Subtask, SelfAssessment, AgentResponse, FinalResponse,
    TaskType, ExecutionMode, RiskLevel, Priority
)
from ai_council.utils.config import create_default_config, load_config
from ai_council.utils.logging import configure_logging, get_logger


def main():
    """Demonstrate basic AI Council infrastructure usage with robust metrics."""
    # 1. Configure logging
    configure_logging(level="INFO", format_json=False)
    logger = get_logger(__name__)
    
    logger.info("Starting AI Council infrastructure demo")
    
    # 2. Robust Configuration Loading
    # Added try-except to handle missing config files gracefully
    try:
        config = load_config()
        logger.info(f"Loaded configuration with {len(config.models)} models")
    except (FileNotFoundError, Exception) as e:
        logger.warning(f"Custom configuration not found ({e}). Falling back to defaults.")
        config = create_default_config()
    
    # 3. Create a sample task
    task = Task(
        content="Analyze the benefits and drawbacks of renewable energy adoption",
        execution_mode=ExecutionMode.BALANCED
    )
    logger.info(f"Created task: {task.id}")
    
    # 4. Create sample subtasks with specific requirements
    subtasks = [
        Subtask(
            parent_task_id=task.id,
            content="Research current renewable energy technologies",
            task_type=TaskType.RESEARCH,
            priority=Priority.HIGH,
            accuracy_requirement=0.9
        ),
        Subtask(
            parent_task_id=task.id,
            content="Analyze economic impact of renewable energy",
            task_type=TaskType.REASONING,
            priority=Priority.MEDIUM,
            accuracy_requirement=0.8
        ),
        Subtask(
            parent_task_id=task.id,
            content="Evaluate environmental benefits",
            task_type=TaskType.FACT_CHECKING,
            priority=Priority.HIGH,
            accuracy_requirement=0.95
        )
    ]
    
    logger.info(f"Created {len(subtasks)} subtasks")
    
    # 5. Create sample self-assessments and responses with aggregation
    responses = []
    total_cost = 0.0
    total_tokens = 0
    
    for i, subtask in enumerate(subtasks):
        # Simulated metrics
        conf_score = 0.85 + (i * 0.05)
        est_cost = 0.05 + (i * 0.02)
        tokens = 150 + (i * 50)
        
        # LOGIC CHECK: Accuracy Validation
        # Proactively check if the model meets the subtask's requirement
        if conf_score < subtask.accuracy_requirement:
            logger.warning(
                f"Accuracy Gap in subtask {i+1}: Actual {conf_score:.2f} < "
                f"Required {subtask.accuracy_requirement}"
            )
        
        assessment = SelfAssessment(
            confidence_score=conf_score,
            assumptions=[f"Assumption {i+1} for subtask validation"],
            risk_level=RiskLevel.LOW,
            estimated_cost=est_cost,
            token_usage=tokens,
            execution_time=2.0 + (i * 0.5),
            model_used=f"model-{i+1}"
        )
        
        response = AgentResponse(
            subtask_id=subtask.id,
            model_used=f"model-{i+1}",
            content=f"Sample response for subtask {i+1}: {subtask.content}",
            self_assessment=assessment,
            success=True
        )
        responses.append(response)
        
        # Aggregate metrics for the final summary
        total_cost += est_cost
        total_tokens += tokens
    
    logger.info(f"Created {len(responses)} agent responses and aggregated metrics")
    
    # 6. Create final response with calculated overall confidence
    avg_confidence = sum(r.self_assessment.confidence_score for r in responses) / len(responses)
    
    final_response = FinalResponse(
        content="Renewable energy adoption offers significant environmental benefits "
                "and long-term economic advantages, though initial costs and "
                "infrastructure challenges must be considered.",
        overall_confidence=avg_confidence,
        models_used=[f"model-{i+1}" for i in range(len(subtasks))],
        success=True
    )
    
    logger.info("Created final response")
    
    # 7. Display Results (Enhanced UI)
    print("\n" + "="*60)
    print("AI COUNCIL INFRASTRUCTURE DEMO")
    print("="*60)
    
    print(f"\n[ORIGINAL TASK]: {task.content}")
    print(f"Execution Mode: {task.execution_mode.value}")
    print(f"Task ID: {task.id}")
    
    print(f"\n[SUBTASKS] ({len(subtasks)}):")
    for i, subtask in enumerate(subtasks, 1):
        print(f"  {i}. [{subtask.task_type.value}] {subtask.content}")
        print(f"     Priority: {subtask.priority.value}, Accuracy Req: {subtask.accuracy_requirement}")
    
    print(f"\n[AGENT RESPONSES] ({len(responses)}):")
    for i, response in enumerate(responses, 1):
        print(f"  {i}. Model: {response.model_used}")
        print(f"     Confidence: {response.self_assessment.confidence_score:.2f}")
        print(f"     Cost: ${response.self_assessment.estimated_cost:.3f} | Tokens: {response.self_assessment.token_usage}")
    
    print(f"\n[METRICS SUMMARY]:")
    print(f"  - Total Estimated Cost: ${total_cost:.4f}")
    print(f"  - Total Token Usage: {total_tokens}")
    print(f"  - Overall Confidence Score: {final_response.overall_confidence:.2f}")
    
    print(f"\n[FINAL OUTPUT]:")
    print(f"  Content: {final_response.content}")
    print(f"  Models Used: {', '.join(final_response.models_used)}")
    
    print(f"\n[CONFIGURATION]:")
    print(f"  Default Mode: {config.execution.default_mode.value}")
    print(f"  Max Cost Limit: ${config.cost.max_cost_per_request}")
    print(f"  Models Available: {', '.join(config.models.keys())}")
    
    logger.info("Infrastructure demo completed successfully")
    print("\n" + "="*60)
    print("Infrastructure is ready for orchestration components!")
    print("="*60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting demo... Cleanup complete.")
        sys.exit(0)