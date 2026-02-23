"""Implementation of TaskDecomposer for breaking complex tasks into subtasks."""

import re
from typing import List, Dict, Set, Tuple
from ..core.interfaces import TaskDecomposer
from ..core.models import Task, Subtask, TaskType, Priority, RiskLevel, ComplexityLevel


class BasicTaskDecomposer(TaskDecomposer):
    """Basic implementation of TaskDecomposer using rule-based decomposition."""
    
    def __init__(self):
        """Initialize the task decomposer with decomposition patterns."""
        self._decomposition_patterns = self._build_decomposition_patterns()
        self._priority_indicators = self._build_priority_indicators()
        self._risk_indicators = self._build_risk_indicators()
    
    async def decompose(self, task: Task) -> List[Subtask]:
        """Decompose a complex task into smaller, atomic subtasks.
        
        Args:
            task: The task to decompose
            
        Returns:
            List[Subtask]: List of subtasks that together fulfill the original task
        """
        if not task.content or not task.content.strip():
            return []
        
        # For simple tasks, return a single subtask
        if task.complexity in [ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE]:
            return [self._create_single_subtask(task)]
        
        subtasks = []
        content = task.content.strip()
        
        # Try different decomposition strategies in order of preference
        subtasks.extend(self._decompose_by_explicit_steps(task, content))
        
        # If explicit steps didn't find enough subtasks, try conjunctions
        if len(subtasks) <= 1:
            conjunction_subtasks = self._decompose_by_conjunctions(task, content)
            if len(conjunction_subtasks) > len(subtasks):
                subtasks = conjunction_subtasks
        
        # If still no good decomposition, try by task types
        if len(subtasks) <= 1:
            task_type_subtasks = self._decompose_by_task_types(task, content)
            if len(task_type_subtasks) > len(subtasks):
                subtasks = task_type_subtasks
        
        # If no decomposition found, create a single subtask
        if not subtasks:
            subtasks = [self._create_single_subtask(task)]
        
        # Assign metadata to all subtasks
        for i, subtask in enumerate(subtasks):
            subtasks[i] = await self.assign_metadata(subtask)
        
        return subtasks
    
    async def assign_metadata(self, subtask: Subtask) -> Subtask:
        """Assign metadata to a subtask including priority, risk level, etc.
        
        Args:
            subtask: The subtask to assign metadata to
            
        Returns:
            Subtask: The subtask with updated metadata
        """
        content_lower = subtask.content.lower()
        
        # Assign priority based on content indicators
        subtask.priority = self._determine_priority(content_lower)
        
        # Assign risk level based on content indicators
        subtask.risk_level = self._determine_risk_level(content_lower)
        
        # Assign accuracy requirement based on task type and risk
        subtask.accuracy_requirement = self._determine_accuracy_requirement(
            subtask.task_type, subtask.risk_level
        )
        
        # Estimate cost based on complexity and task type
        subtask.estimated_cost = self._estimate_subtask_cost(subtask)
        
        return subtask
    
    async def validate_decomposition(self, subtasks: List[Subtask]) -> bool:
        """Validate that a decomposition is complete and consistent.
        
        Args:
            subtasks: List of subtasks to validate
            
        Returns:
            bool: True if decomposition is valid, False otherwise
        """
        if not subtasks:
            return False
        
        # Check that all subtasks have the same parent task ID
        parent_ids = {subtask.parent_task_id for subtask in subtasks}
        if len(parent_ids) != 1:
            return False
        
        # Check that all subtasks have content
        for subtask in subtasks:
            if not subtask.content or not subtask.content.strip():
                return False
        
        # Check that all subtasks have valid task types
        for subtask in subtasks:
            if subtask.task_type is None:
                return False
        
        # Check that accuracy requirements are valid
        for subtask in subtasks:
            if not (0.0 <= subtask.accuracy_requirement <= 1.0):
                return False
        
        # Check that estimated costs are non-negative
        for subtask in subtasks:
            if subtask.estimated_cost < 0.0:
                return False
        
        return True
    
    def _create_single_subtask(self, task: Task) -> Subtask:
        """Create a single subtask from a task."""
        # Determine the most appropriate task type
        task_types = self._classify_content_task_types(task.content)
        primary_task_type = task_types[0] if task_types else TaskType.REASONING
        
        return Subtask(
            parent_task_id=task.id,
            content=task.content,
            task_type=primary_task_type,
            priority=Priority.MEDIUM,
            risk_level=RiskLevel.LOW,
            accuracy_requirement=0.8,
            estimated_cost=0.0
        )
    
    def _decompose_by_explicit_steps(self, task: Task, content: str) -> List[Subtask]:
        """Decompose task by explicit step indicators."""
        subtasks = []
        
        # Try numbered steps first (1. 2. 3.)
        numbered_pattern = r'(\d+)\.\s*([^0-9]+?)(?=\s*\d+\.|$)'
        numbered_matches = list(re.finditer(numbered_pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL))
        
        if len(numbered_matches) >= 2:  # Found multiple numbered steps
            for match in numbered_matches:
                step_content = match.group(2).strip()
                step_content = re.sub(r'\s+', ' ', step_content)
                step_content = step_content.strip('.,;')
                
                if len(step_content) > 10:
                    task_types = self._classify_content_task_types(step_content)
                    primary_task_type = task_types[0] if task_types else TaskType.REASONING
                    
                    subtask = Subtask(
                        parent_task_id=task.id,
                        content=step_content,
                        task_type=primary_task_type
                    )
                    subtasks.append(subtask)
            return subtasks
        
        # Try sequence words by splitting sentences
        # Look for sentences that start with sequence indicators
        sentences = re.split(r'\.(?=\s+[A-Z])', content)
        sequence_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and re.match(r'^(first|second|third|then|next|finally)[,:]?\s+', sentence, re.IGNORECASE):
                # Remove the sequence word and clean up
                clean_sentence = re.sub(r'^(first|second|third|then|next|finally)[,:]?\s+', '', sentence, flags=re.IGNORECASE)
                clean_sentence = clean_sentence.strip('.,;')
                
                if len(clean_sentence) > 10:
                    sequence_sentences.append(clean_sentence)
        
        if len(sequence_sentences) >= 2:  # Found multiple sequence steps
            for step_content in sequence_sentences:
                task_types = self._classify_content_task_types(step_content)
                primary_task_type = task_types[0] if task_types else TaskType.REASONING
                
                subtask = Subtask(
                    parent_task_id=task.id,
                    content=step_content,
                    task_type=primary_task_type
                )
                subtasks.append(subtask)
        
        return subtasks
    
    def _decompose_by_conjunctions(self, task: Task, content: str) -> List[Subtask]:
        """Decompose task by conjunction words (and, then, also, etc.)."""
        subtasks = []
        
        # Split by common conjunctions - use word boundaries to avoid partial matches
        conjunction_patterns = [
            r'\s+and\s+then\s+',
            r'\s+and\s+also\s+',
            r'\s+and\s+',
            r'\s+then\s+',
            r'\s+also\s+',
            r'\s+additionally\s+',
            r'\s+furthermore\s+',
            r'\s+moreover\s+'
        ]
        
        parts = [content]
        for pattern in conjunction_patterns:
            new_parts = []
            for part in parts:
                split_parts = re.split(pattern, part, flags=re.IGNORECASE)
                new_parts.extend(split_parts)
            parts = new_parts
        
        # Filter and create subtasks from meaningful parts
        for part in parts:
            part = part.strip()
            # Remove common sentence starters and clean up
            part = re.sub(r'^(and|then|also|additionally|furthermore|moreover)\s+', '', part, flags=re.IGNORECASE)
            
            if len(part) > 15:  # Only meaningful parts
                task_types = self._classify_content_task_types(part)
                primary_task_type = task_types[0] if task_types else TaskType.REASONING
                
                subtask = Subtask(
                    parent_task_id=task.id,
                    content=part,
                    task_type=primary_task_type
                )
                subtasks.append(subtask)
        
        return subtasks
    
    def _decompose_by_task_types(self, task: Task, content: str) -> List[Subtask]:
        """Decompose task by identifying different task types within the content."""
        subtasks = []
        task_types = self._classify_content_task_types(content)
        
        # If multiple task types are identified, create subtasks for each
        if len(task_types) > 1:
            for task_type in task_types:
                # Extract content relevant to this task type
                relevant_content = self._extract_content_for_task_type(content, task_type)
                if relevant_content:
                    subtask = Subtask(
                        parent_task_id=task.id,
                        content=relevant_content,
                        task_type=task_type
                    )
                    subtasks.append(subtask)
        
        return subtasks
    
    def _classify_content_task_types(self, content: str) -> List[TaskType]:
        """Classify what task types are present in the content."""
        content_lower = content.lower()
        task_types = []
        
        # Define patterns for each task type
        task_type_patterns = {
            TaskType.RESEARCH: [
                r'\bresearch\b', r'\bfind\s+information\b', r'\blook\s+up\b', 
                r'\binvestigate\b', r'\bgather\s+data\b'
            ],
            TaskType.CODE_GENERATION: [
                r'\bcode\b', r'\bprogram\b', r'\bscript\b', r'\bfunction\b', 
                r'\bimplement\b', r'\bdevelop\b'
            ],
            TaskType.DEBUGGING: [
                r'\bdebug\b', r'\bfix\b', r'\berror\b', r'\bbug\b', r'\bissue\b'
            ],
            TaskType.CREATIVE_OUTPUT: [
                r'\bcreative\b', r'\bstory\b', r'\bwrite\b', r'\bcompose\b', r'\bimagine\b'
            ],
            TaskType.FACT_CHECKING: [
                r'\bfact\s+check\b', r'\bverify\b', r'\baccurate\b', r'\bcorrect\b'
            ],
            TaskType.VERIFICATION: [
                r'\btest\b', r'\bvalidate\b', r'\bconfirm\b', r'\bensure\b'
            ],
            TaskType.REASONING: [
                r'\banalyze\b', r'\bthink\b', r'\breason\b', r'\bsolve\b', r'\bexplain\b'
            ]
        }
        
        for task_type, patterns in task_type_patterns.items():
            if any(re.search(pattern, content_lower) for pattern in patterns):
                task_types.append(task_type)
        
        # Default to reasoning if no specific type found
        if not task_types:
            task_types.append(TaskType.REASONING)
        
        return task_types
    
    def _extract_content_for_task_type(self, content: str, task_type: TaskType) -> str:
        """Extract content relevant to a specific task type."""
        # For now, return the full content
        # In a more sophisticated implementation, this could extract
        # only the portions relevant to the specific task type
        return content
    
    def _determine_priority(self, content_lower: str) -> Priority:
        """Determine priority based on content indicators."""
        high_priority_indicators = [
            r'\burgent\b', r'\bcritical\b', r'\bimmediate\b', r'\basap\b',
            r'\bhigh\s+priority\b', r'\bimportant\b'
        ]
        
        low_priority_indicators = [
            r'\boptional\b', r'\bnice\s+to\s+have\b', r'\bwhen\s+time\s+permits\b',
            r'\blow\s+priority\b', r'\blater\b'
        ]
        
        if any(re.search(pattern, content_lower) for pattern in high_priority_indicators):
            return Priority.HIGH
        elif any(re.search(pattern, content_lower) for pattern in low_priority_indicators):
            return Priority.LOW
        else:
            return Priority.MEDIUM
    
    def _determine_risk_level(self, content_lower: str) -> RiskLevel:
        """Determine risk level based on content indicators."""
        high_risk_indicators = [
            r'\bproduction\b', r'\blive\b', r'\bcritical\b', r'\bsecurity\b',
            r'\bdata\s+loss\b', r'\bdowntime\b', r'\bfinancial\b'
        ]
        
        medium_risk_indicators = [
            r'\btest\b', r'\bstaging\b', r'\bperformance\b', r'\bintegration\b'
        ]
        
        if any(re.search(pattern, content_lower) for pattern in high_risk_indicators):
            return RiskLevel.HIGH
        elif any(re.search(pattern, content_lower) for pattern in medium_risk_indicators):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _determine_accuracy_requirement(self, task_type: TaskType, risk_level: RiskLevel) -> float:
        """Determine accuracy requirement based on task type and risk level."""
        base_accuracy = {
            TaskType.FACT_CHECKING: 0.95,
            TaskType.VERIFICATION: 0.90,
            TaskType.CODE_GENERATION: 0.85,
            TaskType.DEBUGGING: 0.85,
            TaskType.RESEARCH: 0.80,
            TaskType.REASONING: 0.75,
            TaskType.CREATIVE_OUTPUT: 0.60,
            TaskType.IMAGE_GENERATION: 0.70
        }
        
        risk_multiplier = {
            RiskLevel.CRITICAL: 1.1,
            RiskLevel.HIGH: 1.05,
            RiskLevel.MEDIUM: 1.0,
            RiskLevel.LOW: 0.95
        }
        
        base = base_accuracy.get(task_type, 0.75)
        multiplier = risk_multiplier.get(risk_level, 1.0)
        
        return min(1.0, base * multiplier)
    
    def _estimate_subtask_cost(self, subtask: Subtask) -> float:
        """Estimate the cost of executing a subtask."""
        # Base cost by task type (in arbitrary units)
        base_costs = {
            TaskType.CREATIVE_OUTPUT: 0.8,
            TaskType.CODE_GENERATION: 0.7,
            TaskType.RESEARCH: 0.6,
            TaskType.DEBUGGING: 0.6,
            TaskType.REASONING: 0.5,
            TaskType.FACT_CHECKING: 0.4,
            TaskType.VERIFICATION: 0.4,
            TaskType.IMAGE_GENERATION: 1.0
        }
        
        base_cost = base_costs.get(subtask.task_type, 0.5)
        
        # Adjust for content length
        content_length = len(subtask.content)
        length_multiplier = 1.0 + (content_length / 1000.0)  # +100% for 1000 chars
        
        # Adjust for accuracy requirement
        accuracy_multiplier = 1.0 + (subtask.accuracy_requirement - 0.5)  # Higher accuracy = higher cost
        
        return base_cost * length_multiplier * accuracy_multiplier
    
    def _build_decomposition_patterns(self) -> Dict[str, List[str]]:
        """Build patterns for task decomposition."""
        return {
            'explicit_steps': [
                r'(\d+)\.\s*',
                r'step\s+(\d+)',
                r'first', r'second', r'third', r'then', r'next', r'finally'
            ],
            'conjunctions': [
                r'\s+and\s+', r'\s+then\s+', r'\s+also\s+', r'\s+additionally\s+'
            ]
        }
    
    def _build_priority_indicators(self) -> Dict[Priority, List[str]]:
        """Build indicators for priority assignment."""
        return {
            Priority.HIGH: [
                r'\burgent\b', r'\bcritical\b', r'\bimmediate\b', r'\basap\b'
            ],
            Priority.LOW: [
                r'\boptional\b', r'\bnice\s+to\s+have\b', r'\blater\b'
            ]
        }
    
    def _build_risk_indicators(self) -> Dict[RiskLevel, List[str]]:
        """Build indicators for risk level assignment."""
        return {
            RiskLevel.HIGH: [
                r'\bproduction\b', r'\blive\b', r'\bcritical\b', r'\bsecurity\b'
            ],
            RiskLevel.MEDIUM: [
                r'\btest\b', r'\bstaging\b', r'\bperformance\b'
            ]
        }