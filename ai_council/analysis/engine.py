"""Implementation of the AnalysisEngine for intent analysis and complexity determination."""

import re
from typing import List, Dict, Set
from ..core.interfaces import AnalysisEngine
from ..core.models import TaskIntent, ComplexityLevel, TaskType


class BasicAnalysisEngine(AnalysisEngine):
    """Basic implementation of AnalysisEngine using rule-based analysis."""
    
    def __init__(self):
        """Initialize the analysis engine with keyword patterns."""
        self._intent_patterns = self._build_intent_patterns()
        self._complexity_indicators = self._build_complexity_indicators()
        self._task_type_patterns = self._build_task_type_patterns()
    
    async def analyze_intent(self, input_text: str) -> TaskIntent:
        """Analyze user input to determine the intent of the request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            TaskIntent: The determined intent category
        """
        if not input_text or not input_text.strip():
            return TaskIntent.QUESTION
        
        text_lower = input_text.lower().strip()
        
        # Check for question patterns
        if self._is_question(text_lower):
            return TaskIntent.QUESTION
        
        # Check for instruction patterns
        if self._is_instruction(text_lower):
            return TaskIntent.INSTRUCTION
        
        # Check for analysis patterns
        if self._is_analysis_request(text_lower):
            return TaskIntent.ANALYSIS
        
        # Check for creation patterns
        if self._is_creation_request(text_lower):
            return TaskIntent.CREATION
        
        # Check for modification patterns
        if self._is_modification_request(text_lower):
            return TaskIntent.MODIFICATION
        
        # Check for verification patterns
        if self._is_verification_request(text_lower):
            return TaskIntent.VERIFICATION
        
        # Default to instruction if unclear
        return TaskIntent.INSTRUCTION
    
    async def determine_complexity(self, input_text: str) -> ComplexityLevel:
        """Determine the complexity level of a user request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            ComplexityLevel: The determined complexity level
        """
        if not input_text or not input_text.strip():
            return ComplexityLevel.TRIVIAL
        
        text_lower = input_text.lower().strip()
        complexity_score = 0
        
        # Length-based complexity
        word_count = len(text_lower.split())
        if word_count > 100:
            complexity_score += 3
        elif word_count > 50:
            complexity_score += 2
        elif word_count > 20:
            complexity_score += 1
        
        # Multi-step indicators
        multi_step_patterns = [
            r'\band\s+then\b', r'\bafter\s+that\b', r'\bnext\b', r'\bfirst\b.*\bsecond\b',
            r'\bstep\s+\d+', r'\bphase\s+\d+', r'\bpart\s+\d+', r'\bstage\s+\d+'
        ]
        for pattern in multi_step_patterns:
            if re.search(pattern, text_lower):
                complexity_score += 2
                break
        
        # Multiple task type indicators
        task_types_found = len(await self.classify_task_type(input_text))
        if task_types_found > 3:
            complexity_score += 3
        elif task_types_found > 2:
            complexity_score += 2
        elif task_types_found > 1:
            complexity_score += 1
        
        # Technical complexity indicators
        technical_patterns = [
            r'\balgorithm\b', r'\boptimiz\w+\b', r'\barchitecture\b', r'\bintegrat\w+\b',
            r'\bcomplex\b', r'\badvanced\b', r'\bsophisticated\b', r'\bcomprehensive\b'
        ]
        for pattern in technical_patterns:
            if re.search(pattern, text_lower):
                complexity_score += 1
        
        # Conditional/branching logic
        conditional_patterns = [
            r'\bif\b.*\bthen\b', r'\bdepending\s+on\b', r'\bvarious\s+scenarios\b',
            r'\bmultiple\s+options\b', r'\balternatives\b'
        ]
        for pattern in conditional_patterns:
            if re.search(pattern, text_lower):
                complexity_score += 2
                break
        
        # Map score to complexity level
        if complexity_score >= 8:
            return ComplexityLevel.VERY_COMPLEX
        elif complexity_score >= 6:
            return ComplexityLevel.COMPLEX
        elif complexity_score >= 3:
            return ComplexityLevel.MODERATE
        elif complexity_score >= 1:
            return ComplexityLevel.SIMPLE
        else:
            return ComplexityLevel.TRIVIAL
    
    async def classify_task_type(self, input_text: str) -> List[TaskType]:
        """Classify the types of tasks required to fulfill the request.
        
        Args:
            input_text: Raw user input to analyze
            
        Returns:
            List[TaskType]: List of task types that may be needed
        """
        if not input_text or not input_text.strip():
            return []
        
        text_lower = input_text.lower().strip()
        task_types = set()
        
        # Check each task type pattern
        for task_type, patterns in self._task_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    task_types.add(task_type)
                    break
        
        # If no specific types found, default to reasoning
        if not task_types:
            task_types.add(TaskType.REASONING)
        
        return list(task_types)
    
    def _build_intent_patterns(self) -> Dict[str, List[str]]:
        """Build patterns for intent classification."""
        return {
            'question': [
                r'\?', r'^what\b', r'^how\b', r'^why\b', r'^when\b', r'^where\b', r'^who\b',
                r'^which\b', r'^can\s+you\b', r'^do\s+you\b', r'^is\s+it\b', r'^are\s+there\b'
            ],
            'instruction': [
                r'^create\b', r'^make\b', r'^build\b', r'^generate\b', r'^write\b',
                r'^implement\b', r'^develop\b', r'^design\b', r'^please\b'
            ],
            'analysis': [
                r'\banalyz\w+\b', r'\bevaluat\w+\b', r'\bassess\b', r'\bexamin\w+\b',
                r'\breview\b', r'\bcompare\b', r'\bcontrast\b', r'\bsummariz\w+\b'
            ],
            'creation': [
                r'\bcreate\b', r'\bgenerate\b', r'\bbuild\b', r'\bmake\b', r'\bwrite\b',
                r'\bcompose\b', r'\bdraft\b', r'\bdesign\b'
            ],
            'modification': [
                r'\bmodify\b', r'\bchange\b', r'\bupdate\b', r'\bedit\b', r'\bimprove\b',
                r'\brefactor\b', r'\boptimize\b', r'\benhance\b'
            ],
            'verification': [
                r'\bverify\b', r'\bcheck\b', r'\bvalidate\b', r'\btest\b', r'\bconfirm\b',
                r'\bensure\b', r'\bprove\b'
            ]
        }
    
    def _build_complexity_indicators(self) -> Dict[str, int]:
        """Build indicators for complexity scoring."""
        return {
            'multi_step': 2,
            'multiple_domains': 2,
            'technical_depth': 1,
            'conditional_logic': 2,
            'integration_required': 3
        }
    
    def _build_task_type_patterns(self) -> Dict[TaskType, List[str]]:
        """Build patterns for task type classification."""
        return {
            TaskType.REASONING: [
                r'\bthink\b', r'\breason\b', r'\blogic\b', r'\bsolve\b', r'\bfigure\s+out\b',
                r'\bexplain\b', r'\bunderstand\b', r'\banalyze\b'
            ],
            TaskType.RESEARCH: [
                r'\bresearch\b', r'\bfind\s+information\b', r'\blook\s+up\b', r'\binvestigate\b',
                r'\bgather\s+data\b', r'\bsearch\s+for\b', r'\blearn\s+about\b'
            ],
            TaskType.CODE_GENERATION: [
                r'\bcode\b', r'\bprogram\b', r'\bscript\b', r'\bfunction\b', r'\bclass\b',
                r'\bimplement\b', r'\bdevelop\b', r'\bwrite\s+code\b', r'\bpython\b', r'\bjavascript\b'
            ],
            TaskType.DEBUGGING: [
                r'\bdebug\b', r'\bfix\b', r'\berror\b', r'\bbug\b', r'\bissue\b',
                r'\bproblem\b', r'\btroubleshoot\b', r'\bnot\s+working\b'
            ],
            TaskType.CREATIVE_OUTPUT: [
                r'\bcreative\b', r'\bstory\b', r'\bpoem\b', r'\bwrite\b', r'\bcompose\b',
                r'\bimagine\b', r'\binvent\b', r'\bbrainstorm\b'
            ],
            TaskType.IMAGE_GENERATION: [
                r'\bimage\b', r'\bpicture\b', r'\bphoto\b', r'\bdraw\b', r'\bvisualize\b',
                r'\bgraphic\b', r'\billustration\b', r'\bgenerate\s+image\b'
            ],
            TaskType.FACT_CHECKING: [
                r'\bfact\s+check\b', r'\bverify\b', r'\btrue\s+or\s+false\b', r'\baccurate\b',
                r'\bcorrect\b', r'\bvalidate\b', r'\bconfirm\b'
            ],
            TaskType.VERIFICATION: [
                r'\bverify\b', r'\bcheck\b', r'\bvalidate\b', r'\btest\b', r'\bconfirm\b',
                r'\bensure\b', r'\bprove\b', r'\bcorrect\b'
            ]
        }
    
    def _is_question(self, text: str) -> bool:
        """Check if text is a question."""
        question_patterns = self._intent_patterns['question']
        return any(re.search(pattern, text) for pattern in question_patterns)
    
    def _is_instruction(self, text: str) -> bool:
        """Check if text is an instruction."""
        instruction_patterns = self._intent_patterns['instruction']
        return any(re.search(pattern, text) for pattern in instruction_patterns)
    
    def _is_analysis_request(self, text: str) -> bool:
        """Check if text is an analysis request."""
        analysis_patterns = self._intent_patterns['analysis']
        return any(re.search(pattern, text) for pattern in analysis_patterns)
    
    def _is_creation_request(self, text: str) -> bool:
        """Check if text is a creation request."""
        creation_patterns = self._intent_patterns['creation']
        return any(re.search(pattern, text) for pattern in creation_patterns)
    
    def _is_modification_request(self, text: str) -> bool:
        """Check if text is a modification request."""
        modification_patterns = self._intent_patterns['modification']
        return any(re.search(pattern, text) for pattern in modification_patterns)
    
    def _is_verification_request(self, text: str) -> bool:
        """Check if text is a verification request."""
        verification_patterns = self._intent_patterns['verification']
        return any(re.search(pattern, text) for pattern in verification_patterns)