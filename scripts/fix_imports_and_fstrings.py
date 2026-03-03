import os
from pathlib import Path

# Mapping of file path to list of exact string replacements
REPLACEMENTS = {
    "ai_council/worker/__main__.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.info(f"Worker completed subtask {subtask_id} in {time.time() - start_time:.2f}s")', 'logger.info("Worker completed subtask", extra={"subtask_id": subtask_id, "duration": round(time.time() - start_time, 2)})'),
        ('logger.error(f"Worker failed processing subtask {subtask_id}: {str(e)}", exc_info=True)', 'logger.error("Worker failed processing subtask", extra={"subtask_id": subtask_id, "error": str(e)}, exc_info=True)'),
        ('logger.critical(f"Worker failed to publish error for {subtask_id}: {str(pub_e)}")', 'logger.critical("Worker failed to publish error", extra={"subtask_id": subtask_id, "error": str(pub_e)})'),
        ('logger.info(f"Worker {self.worker_id} started. Listening on Redis: {sanitized_url}, queue: {self.task_queue}")', 'logger.info("Worker started", extra={"worker_id": self.worker_id, "url": sanitized_url, "queue": self.task_queue})'),
    ],
    "ai_council/utils/plugin_manager.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.error(f"Failed to load plugin {plugin_name}: {e}")', 'logger.error("Failed to load plugin", extra={"plugin_name": plugin_name, "error": str(e)})'),
        ('logger.info(f"Successfully loaded plugin {plugin_name} ({interface_type.__name__})")', 'logger.info("Successfully loaded plugin", extra={"plugin_name": plugin_name, "interface_type": interface_type.__name__})'),
        ('logger.warning(f"Error during cleanup of plugin {plugin_name}: {e}")', 'logger.warning("Error during cleanup of plugin", extra={"plugin_name": plugin_name, "error": str(e)})'),
        ('logger.debug(f"Could not inspect {py_file}: {e}")', 'logger.debug("Could not inspect py file", extra={"py_file": py_file, "error": str(e)})'),
    ],
    "ai_council/orchestration/layer.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.info(f"Processing request in {execution_mode.value} mode: {user_input[:100]}...")', 'logger.info("Processing request", extra={"mode": execution_mode.value, "input_sample": user_input[:100]})'),
        ('logger.info(f"Estimated cost: ${cost_estimate.estimated_cost:.4f}, time: {cost_estimate.estimated_time:.1f}s")', 'logger.info("Estimated cost", extra={"cost": cost_estimate.estimated_cost, "time": cost_estimate.estimated_time})'),
        ('logger.warning(f"Group {group_index} had low success rate: {group_success_rate:.1%}")', 'logger.warning("Group had low success rate", extra={"group_index": group_index, "success_rate": group_success_rate})'),
        ('logger.warning(f"Subtask {subtask.id} timed out: {str(e)}")', 'logger.warning("Subtask timed out", extra={"subtask_id": subtask.id, "error": str(e)})'),
        ('logger.error(f"Failed to execute subtask {subtask.id}: {str(e)}")', 'logger.error("Failed to execute subtask", extra={"subtask_id": subtask.id, "error": str(e)})'),
        ('logger.info(f"Cost estimate: ${total_cost:.4f}, time: {total_time:.1f}s, savings: ${estimated_savings:.4f}")', 'logger.info("Cost estimate", extra={"cost": total_cost, "time": total_time, "savings": estimated_savings})'),
        ('logger.warning(f"Handling failure: {failure.failure_type} - {failure.error_message}")', 'logger.warning("Handling failure", extra={"failure_type": failure.failure_type, "error_message": failure.error_message})'),
    ],
    "ai_council/factory.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("self.logger = logging.getLogger(__name__)", "self.logger = get_logger(__name__)"),
        ('self.logger.error(f"Failed to register model {model_name}: {str(e)}")', 'self.logger.error("Failed to register model", extra={"model_name": model_name, "error": str(e)})'),
        ('self.logger.info(f"Creating real {model_config.provider} adapter for {model_name}")', 'self.logger.info("Creating real adapter", extra={"provider": model_config.provider, "model_name": model_name})'),
        ('self.logger.warning(f"Failed to create real adapter for {model_name}: {str(e)}, using mock")', 'self.logger.warning("Failed to create real adapter, using mock", extra={"model_name": model_name, "error": str(e)})'),
        ('self.logger.error(f"Failed to create model {model_name}: {str(e)}")', 'self.logger.error("Failed to create model", extra={"model_name": model_name, "error": str(e)})'),
    ],
    "ai_council/execution/mq_agent.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.info(f"Pushing subtask {subtask.id} to MQ for model {model_id}")', 'logger.info("Pushing subtask to MQ", extra={"subtask_id": subtask.id, "model_id": model_id})'),
        ('logger.error(f"MQ Execution failed for subtask {subtask.id}: {str(e)}")', 'logger.error("MQ Execution failed for subtask", extra={"subtask_id": subtask.id, "error": str(e)})'),
    ],
    "ai_council/execution/agent.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.info(f"Executing subtask {subtask.id} with model {model_id}")', 'logger.info("Executing subtask", extra={"subtask_id": subtask.id, "model_id": model_id})'),
        ('logger.info(f"Rate limit hit for {provider}, waiting {wait_time:.1f}s")', 'logger.info("Rate limit hit", extra={"provider": provider, "wait_time": wait_time})'),
        ('logger.info(f"Successfully executed subtask {subtask.id} on attempt {attempt + 1}")', 'logger.info("Successfully executed subtask", extra={"subtask_id": subtask.id, "attempt": attempt + 1})'),
    ],
    "ai_council/core/timeout_handler.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.debug(f"Updated default timeout for {operation} to {timeout}s")', 'logger.debug("Updated default timeout", extra={"operation": operation, "timeout": timeout})'),
        ('logger.warning(f"Rate limit exceeded for {resource}, waiting {wait_time:.1f}s")', 'logger.warning("Rate limit exceeded", extra={"resource": resource, "wait_time": wait_time})'),
    ],
    "ai_council/core/error_handling.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ("self._logger = logging.getLogger(self.__class__.__name__)", "self._logger = get_logger(self.__class__.__name__)"),
        ('logger.error(f"Error in {stage_name}: {str(e)}")', 'logger.error("Error in stage", extra={"stage": stage_name, "error": str(e)})'),
        ('logger.error(f"Critical error in {stage_name}: {str(e)}")', 'logger.error("Critical error in stage", extra={"stage": stage_name, "error": str(e)})'),
        ('logger.warning(f"Handled error in {stage_name}: {str(e)}")', 'logger.warning("Handled error in stage", extra={"stage": stage_name, "error": str(e)})'),
        ('logger.error(f"Unexpected error in {stage_name}: {str(e)}")', 'logger.error("Unexpected error in stage", extra={"stage": stage_name, "error": str(e)})'),
        ('self._logger.error(f"Error in {self.name}: {str(error)}")', 'self._logger.error("Error", extra={"name": self.name, "error": str(error)})'),
    ],
    "ai_council/arbitration/layer.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("logger = logging.getLogger(__name__)", "logger = get_logger(__name__)"),
        ('logger.info(f"ArbitrationLayer initialized with confidence_threshold={confidence_threshold}, quality_weight={quality_weight}")', 'logger.info("ArbitrationLayer initialized", extra={"confidence_threshold": confidence_threshold, "quality_weight": quality_weight})'),
        ('logger.error(f"Failed to resolve conflict {conflict.conflict_type}: {e}")', 'logger.error("Failed to resolve conflict", extra={"conflict_type": conflict.conflict_type, "error": str(e)})'),
        ('logger.info(f"Arbitration complete: {len(validated_responses)} validated responses, {len(resolutions)} conflicts resolved")', 'logger.info("Arbitration complete", extra={"validated_responses": len(validated_responses), "resolutions": len(resolutions)})'),
    ],
    "ai_council/main.py": [
        ("import logging", "from ai_council.core.logger import get_logger"),
        ("self.logger = logging.getLogger(__name__)", "self.logger = get_logger(__name__)"),
    ]
}

base_dir = Path("d:/OSCG/yfgf/Ai-Council")

for rel_path, reps in REPLACEMENTS.items():
    file_path = base_dir / rel_path
    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for old, new in reps:
        if old in content:
            content = content.replace(old, new)
        else:
            print(f"Warning: Could not find '{old}' in {file_path}")
            
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
print("Replacements complete.")
