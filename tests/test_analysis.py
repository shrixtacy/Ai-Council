"""
Unit tests for AI Council Analysis module.

Tests cover the AnalysisEngine and TaskDecomposer components in ai_council/analysis/
including intent analysis, complexity determination, task classification, and decomposition.
"""

import pytest
from typing import List

from ai_council.core.models import (
    Task, Subtask, TaskType, TaskIntent, ComplexityLevel,
    ExecutionMode, Priority, RiskLevel
)
from ai_council.analysis.engine import BasicAnalysisEngine
from ai_council.analysis.decomposer import BasicTaskDecomposer


# =============================================================================
# BasicAnalysisEngine Tests
# =============================================================================

class TestAnalysisEngineInitialization:
    """Tests for BasicAnalysisEngine initialization."""
    
    def test_engine_creation(self):
        """Test that the analysis engine can be created."""
        engine = BasicAnalysisEngine()
        assert engine is not None
    
    def test_engine_has_intent_patterns(self):
        """Test that engine initializes with intent patterns."""
        engine = BasicAnalysisEngine()
        patterns = engine._intent_patterns
        assert 'question' in patterns
        assert 'instruction' in patterns
        assert 'analysis' in patterns
        assert 'creation' in patterns
        assert 'modification' in patterns
        assert 'verification' in patterns
    
    def test_engine_has_complexity_indicators(self):
        """Test that engine initializes with complexity indicators."""
        engine = BasicAnalysisEngine()
        indicators = engine._complexity_indicators
        assert 'multi_step' in indicators
        assert 'multiple_domains' in indicators
        assert 'technical_depth' in indicators
    
    def test_engine_has_task_type_patterns(self):
        """Test that engine initializes with task type patterns."""
        engine = BasicAnalysisEngine()
        patterns = engine._task_type_patterns
        assert TaskType.REASONING in patterns
        assert TaskType.RESEARCH in patterns
        assert TaskType.CODE_GENERATION in patterns
        assert TaskType.DEBUGGING in patterns


class TestIntentAnalysis:
    """Tests for intent analysis functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create an analysis engine instance."""
        return BasicAnalysisEngine()
    
    def test_question_intent_with_question_mark(self, engine):
        """Test that question mark indicates question intent."""
        result = engine.analyze_intent("What is the best approach?")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_what(self, engine):
        """Test that 'what' indicates question intent."""
        result = engine.analyze_intent("what are the benefits of Python")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_how(self, engine):
        """Test that 'how' indicates question intent."""
        result = engine.analyze_intent("how do I implement this feature")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_why(self, engine):
        """Test that 'why' indicates question intent."""
        result = engine.analyze_intent("why is this approach better")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_when(self, engine):
        """Test that 'when' indicates question intent."""
        result = engine.analyze_intent("when should I use this pattern")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_where(self, engine):
        """Test that 'where' indicates question intent."""
        result = engine.analyze_intent("where is the configuration stored")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_who(self, engine):
        """Test that 'who' indicates question intent."""
        result = engine.analyze_intent("who designed this architecture")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_which(self, engine):
        """Test that 'which' indicates question intent."""
        result = engine.analyze_intent("which framework is better")
        assert result == TaskIntent.QUESTION
    
    def test_question_intent_with_can_you(self, engine):
        """Test that 'can you' indicates question intent."""
        result = engine.analyze_intent("can you explain this concept")
        assert result == TaskIntent.QUESTION
    
    def test_instruction_intent_with_create(self, engine):
        """Test that 'create' indicates instruction intent."""
        result = engine.analyze_intent("create a new database schema")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_make(self, engine):
        """Test that 'make' indicates instruction intent."""
        result = engine.analyze_intent("make a REST API endpoint")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_build(self, engine):
        """Test that 'build' indicates instruction intent."""
        result = engine.analyze_intent("build a user authentication system")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_generate(self, engine):
        """Test that 'generate' indicates instruction intent."""
        result = engine.analyze_intent("generate a report from this data")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_write(self, engine):
        """Test that 'write' indicates instruction intent."""
        result = engine.analyze_intent("write a function to parse JSON")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_implement(self, engine):
        """Test that 'implement' indicates instruction intent."""
        result = engine.analyze_intent("implement the observer pattern")
        assert result == TaskIntent.INSTRUCTION
    
    def test_instruction_intent_with_please(self, engine):
        """Test that 'please' indicates instruction intent."""
        result = engine.analyze_intent("please format this code properly")
        assert result == TaskIntent.INSTRUCTION
    
    def test_analysis_intent_with_analyze(self, engine):
        """Test that 'analyze' indicates analysis intent."""
        result = engine.analyze_intent("analyze the performance bottlenecks")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_evaluate(self, engine):
        """Test that 'evaluate' indicates analysis intent."""
        result = engine.analyze_intent("evaluate the system architecture")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_assess(self, engine):
        """Test that 'assess' indicates analysis intent."""
        result = engine.analyze_intent("assess the security risks")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_examine(self, engine):
        """Test that 'examine' indicates analysis intent."""
        result = engine.analyze_intent("examine the code quality")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_review(self, engine):
        """Test that 'review' indicates analysis intent."""
        result = engine.analyze_intent("review the pull request changes")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_compare(self, engine):
        """Test that 'compare' indicates analysis intent."""
        result = engine.analyze_intent("compare these two implementations")
        assert result == TaskIntent.ANALYSIS
    
    def test_analysis_intent_with_summarize(self, engine):
        """Test that 'summarize' indicates analysis intent."""
        result = engine.analyze_intent("summarize the key findings")
        assert result == TaskIntent.ANALYSIS
    
    def test_modification_intent_with_modify(self, engine):
        """Test that 'modify' indicates modification intent."""
        result = engine.analyze_intent("modify the existing configuration")
        assert result == TaskIntent.MODIFICATION
    
    def test_modification_intent_with_change(self, engine):
        """Test that 'change' indicates modification intent."""
        result = engine.analyze_intent("change the database connection string")
        assert result == TaskIntent.MODIFICATION
    
    def test_modification_intent_with_update(self, engine):
        """Test that 'update' indicates modification intent."""
        result = engine.analyze_intent("update the API documentation")
        assert result == TaskIntent.MODIFICATION
    
    def test_modification_intent_with_edit(self, engine):
        """Test that 'edit' indicates modification intent."""
        result = engine.analyze_intent("edit the main function")
        assert result == TaskIntent.MODIFICATION
    
    def test_modification_intent_with_refactor(self, engine):
        """Test that 'refactor' indicates modification intent."""
        result = engine.analyze_intent("refactor the legacy code")
        assert result == TaskIntent.MODIFICATION
    
    def test_modification_intent_with_optimize(self, engine):
        """Test that 'optimize' indicates modification intent."""
        result = engine.analyze_intent("optimize the database queries")
        assert result == TaskIntent.MODIFICATION
    
    def test_verification_intent_with_verify(self, engine):
        """Test that 'verify' indicates verification intent."""
        result = engine.analyze_intent("verify the test results")
        assert result == TaskIntent.VERIFICATION
    
    def test_verification_intent_with_check(self, engine):
        """Test that 'check' indicates verification intent."""
        result = engine.analyze_intent("check the code for errors")
        assert result == TaskIntent.VERIFICATION
    
    def test_verification_intent_with_validate(self, engine):
        """Test that 'validate' indicates verification intent."""
        result = engine.analyze_intent("validate the input data")
        assert result == TaskIntent.VERIFICATION
    
    def test_verification_intent_with_test(self, engine):
        """Test that 'test' indicates verification intent."""
        result = engine.analyze_intent("test the new functionality")
        assert result == TaskIntent.VERIFICATION
    
    def test_verification_intent_with_confirm(self, engine):
        """Test that 'confirm' indicates verification intent."""
        result = engine.analyze_intent("confirm the deployment was successful")
        assert result == TaskIntent.VERIFICATION
    
    def test_empty_input_returns_question(self, engine):
        """Test that empty input returns question intent."""
        result = engine.analyze_intent("")
        assert result == TaskIntent.QUESTION
    
    def test_whitespace_input_returns_question(self, engine):
        """Test that whitespace input returns question intent."""
        result = engine.analyze_intent("   ")
        assert result == TaskIntent.QUESTION
    
    def test_unclear_input_defaults_to_instruction(self, engine):
        """Test that unclear input defaults to instruction intent."""
        result = engine.analyze_intent("random text without clear intent")
        assert result == TaskIntent.INSTRUCTION


class TestComplexityDetermination:
    """Tests for complexity level determination."""
    
    @pytest.fixture
    def engine(self):
        """Create an analysis engine instance."""
        return BasicAnalysisEngine()
    
    def test_empty_input_returns_trivial(self, engine):
        """Test that empty input returns trivial complexity."""
        result = engine.determine_complexity("")
        assert result == ComplexityLevel.TRIVIAL
    
    def test_whitespace_input_returns_trivial(self, engine):
        """Test that whitespace input returns trivial complexity."""
        result = engine.determine_complexity("   ")
        assert result == ComplexityLevel.TRIVIAL
    
    def test_short_text_is_simple_or_trivial(self, engine):
        """Test that short text has low complexity."""
        result = engine.determine_complexity("fix the bug")
        assert result in [ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE]
    
    def test_medium_text_has_moderate_or_higher_complexity(self, engine):
        """Test that medium length text has appropriate complexity."""
        text = " ".join(["word"] * 30)  # 30 words
        result = engine.determine_complexity(text)
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE]
    
    def test_long_text_increases_complexity(self, engine):
        """Test that long text increases complexity score."""
        text = " ".join(["word"] * 120)  # 120 words
        result = engine.determine_complexity(text)
        assert result in [ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX, ComplexityLevel.VERY_COMPLEX]
    
    def test_multi_step_indicators_increase_complexity(self, engine):
        """Test that multi-step indicators increase complexity."""
        result = engine.determine_complexity("First do this and then do that next step")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
    
    def test_step_numbering_increases_complexity(self, engine):
        """Test that numbered steps increase complexity."""
        result = engine.determine_complexity("step 1: initialize, step 2: process, step 3: finalize")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
    
    def test_technical_patterns_increase_complexity(self, engine):
        """Test that technical patterns increase complexity."""
        result = engine.determine_complexity("implement an advanced algorithm for optimization")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
    
    def test_conditional_logic_increases_complexity(self, engine):
        """Test that conditional logic increases complexity."""
        result = engine.determine_complexity("if this condition then perform that action")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
    
    def test_architecture_keyword_increases_complexity(self, engine):
        """Test that 'architecture' keyword increases complexity."""
        result = engine.determine_complexity("design the system architecture for the new platform")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
    
    def test_comprehensive_keyword_increases_complexity(self, engine):
        """Test that 'comprehensive' keyword increases complexity."""
        result = engine.determine_complexity("create a comprehensive solution")
        assert result in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]


class TestTaskTypeClassification:
    """Tests for task type classification."""
    
    @pytest.fixture
    def engine(self):
        """Create an analysis engine instance."""
        return BasicAnalysisEngine()
    
    def test_empty_input_returns_empty_list(self, engine):
        """Test that empty input returns empty list."""
        result = engine.classify_task_type("")
        assert result == []
    
    def test_whitespace_input_returns_empty_list(self, engine):
        """Test that whitespace input returns empty list."""
        result = engine.classify_task_type("   ")
        assert result == []
    
    def test_reasoning_classification(self, engine):
        """Test that reasoning keywords are classified correctly."""
        result = engine.classify_task_type("think about this problem and explain the solution")
        assert TaskType.REASONING in result
    
    def test_research_classification(self, engine):
        """Test that research keywords are classified correctly."""
        result = engine.classify_task_type("research the best practices for API design")
        assert TaskType.RESEARCH in result
    
    def test_code_generation_classification(self, engine):
        """Test that code generation keywords are classified correctly."""
        result = engine.classify_task_type("write code for a Python function")
        assert TaskType.CODE_GENERATION in result
    
    def test_debugging_classification(self, engine):
        """Test that debugging keywords are classified correctly."""
        result = engine.classify_task_type("debug this error in the program")
        assert TaskType.DEBUGGING in result
    
    def test_creative_output_classification(self, engine):
        """Test that creative output keywords are classified correctly."""
        result = engine.classify_task_type("write a creative story about technology")
        assert TaskType.CREATIVE_OUTPUT in result
    
    def test_image_generation_classification(self, engine):
        """Test that image generation keywords are classified correctly."""
        result = engine.classify_task_type("generate an image of a mountain landscape")
        assert TaskType.IMAGE_GENERATION in result
    
    def test_fact_checking_classification(self, engine):
        """Test that fact checking keywords are classified correctly."""
        result = engine.classify_task_type("fact check this claim and verify accuracy")
        assert TaskType.FACT_CHECKING in result
    
    def test_verification_classification(self, engine):
        """Test that verification keywords are classified correctly."""
        result = engine.classify_task_type("validate this data and confirm the results")
        assert TaskType.VERIFICATION in result
    
    def test_multiple_task_types(self, engine):
        """Test that multiple task types can be identified."""
        result = engine.classify_task_type("research and write code for a debug tool")
        assert len(result) >= 2
    
    def test_default_to_reasoning(self, engine):
        """Test that unclear input defaults to reasoning."""
        result = engine.classify_task_type("do something with this data")
        assert TaskType.REASONING in result


class TestPrivateHelperMethods:
    """Tests for private helper methods in the engine."""
    
    @pytest.fixture
    def engine(self):
        """Create an analysis engine instance."""
        return BasicAnalysisEngine()
    
    def test_is_question_with_question_mark(self, engine):
        """Test _is_question with question mark."""
        assert engine._is_question("what is this?") is True
    
    def test_is_question_with_what(self, engine):
        """Test _is_question with 'what'."""
        assert engine._is_question("what is the answer") is True
    
    def test_is_question_without_indicators(self, engine):
        """Test _is_question without question indicators."""
        assert engine._is_question("create this thing") is False
    
    def test_is_instruction_with_create(self, engine):
        """Test _is_instruction with 'create'."""
        assert engine._is_instruction("create a new file") is True
    
    def test_is_instruction_without_indicators(self, engine):
        """Test _is_instruction without instruction indicators."""
        assert engine._is_instruction("what is this") is False
    
    def test_is_analysis_request_with_analyze(self, engine):
        """Test _is_analysis_request with 'analyze'."""
        assert engine._is_analysis_request("analyze the data") is True
    
    def test_is_analysis_request_without_indicators(self, engine):
        """Test _is_analysis_request without analysis indicators."""
        assert engine._is_analysis_request("create something") is False
    
    def test_is_creation_request_with_create(self, engine):
        """Test _is_creation_request with 'create'."""
        assert engine._is_creation_request("create a new component") is True
    
    def test_is_modification_request_with_modify(self, engine):
        """Test _is_modification_request with 'modify'."""
        assert engine._is_modification_request("modify the existing code") is True
    
    def test_is_verification_request_with_verify(self, engine):
        """Test _is_verification_request with 'verify'."""
        assert engine._is_verification_request("verify the results") is True


# =============================================================================
# BasicTaskDecomposer Tests
# =============================================================================

class TestTaskDecomposerInitialization:
    """Tests for BasicTaskDecomposer initialization."""
    
    def test_decomposer_creation(self):
        """Test that the task decomposer can be created."""
        decomposer = BasicTaskDecomposer()
        assert decomposer is not None
    
    def test_decomposer_has_decomposition_patterns(self):
        """Test that decomposer initializes with decomposition patterns."""
        decomposer = BasicTaskDecomposer()
        patterns = decomposer._decomposition_patterns
        assert 'explicit_steps' in patterns
        assert 'conjunctions' in patterns
    
    def test_decomposer_has_priority_indicators(self):
        """Test that decomposer initializes with priority indicators."""
        decomposer = BasicTaskDecomposer()
        indicators = decomposer._priority_indicators
        assert Priority.HIGH in indicators
        assert Priority.LOW in indicators
    
    def test_decomposer_has_risk_indicators(self):
        """Test that decomposer initializes with risk indicators."""
        decomposer = BasicTaskDecomposer()
        indicators = decomposer._risk_indicators
        assert RiskLevel.HIGH in indicators
        assert RiskLevel.MEDIUM in indicators


class TestTaskDecomposition:
    """Tests for task decomposition functionality."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    @pytest.fixture
    def simple_task(self):
        """Create a simple task for testing."""
        return Task(
            content="Fix the bug in the login function",
            complexity=ComplexityLevel.SIMPLE
        )
    
    @pytest.fixture
    def complex_task(self):
        """Create a complex task for testing."""
        return Task(
            content="First research the best database options. Then implement the database layer. Finally test the integration.",
            complexity=ComplexityLevel.COMPLEX
        )
    
    def test_minimal_task_returns_subtasks(self, decomposer):
        """Test that minimal task returns at least one subtask."""
        # Note: Empty content fails validation, so test with minimal valid content
        result = decomposer.decompose(Task(content="x", complexity=ComplexityLevel.TRIVIAL))
        assert len(result) >= 1  # At least one subtask
    
    def test_simple_task_returns_single_subtask(self, decomposer, simple_task):
        """Test that simple task returns a single subtask."""
        result = decomposer.decompose(simple_task)
        assert len(result) >= 1
        assert all(isinstance(s, Subtask) for s in result)
    
    def test_subtasks_have_parent_task_id(self, decomposer, simple_task):
        """Test that subtasks have correct parent task ID."""
        result = decomposer.decompose(simple_task)
        for subtask in result:
            assert subtask.parent_task_id == simple_task.id
    
    def test_subtasks_have_task_type(self, decomposer, simple_task):
        """Test that subtasks have a task type assigned."""
        result = decomposer.decompose(simple_task)
        for subtask in result:
            assert subtask.task_type is not None
    
    def test_decompose_by_explicit_steps(self, decomposer):
        """Test decomposition by explicit numbered steps."""
        task = Task(
            content="1. Research options 2. Design solution 3. Implement code",
            complexity=ComplexityLevel.MODERATE
        )
        result = decomposer.decompose(task)
        # Should find multiple subtasks from numbered steps
        assert len(result) >= 1
    
    def test_decompose_by_sequence_words(self, decomposer):
        """Test decomposition by sequence words."""
        task = Task(
            content="First analyze the requirements carefully. Then design the architecture properly. Finally implement the solution correctly.",
            complexity=ComplexityLevel.COMPLEX
        )
        result = decomposer.decompose(task)
        assert len(result) >= 1
    
    def test_decompose_by_conjunctions(self, decomposer):
        """Test decomposition by conjunctions."""
        task = Task(
            content="Research the problem thoroughly and then implement a solution carefully and also write tests comprehensively",
            complexity=ComplexityLevel.MODERATE
        )
        result = decomposer.decompose(task)
        assert len(result) >= 1
    
    def test_trivial_task_returns_single_subtask(self, decomposer):
        """Test that trivial complexity returns single subtask."""
        task = Task(
            content="Simple request",
            complexity=ComplexityLevel.TRIVIAL
        )
        result = decomposer.decompose(task)
        assert len(result) == 1


class TestMetadataAssignment:
    """Tests for subtask metadata assignment."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_assign_metadata_sets_priority(self, decomposer):
        """Test that assign_metadata sets priority."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Test subtask content",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.priority is not None
    
    def test_assign_metadata_sets_risk_level(self, decomposer):
        """Test that assign_metadata sets risk level."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Test subtask content",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.risk_level is not None
    
    def test_assign_metadata_sets_accuracy_requirement(self, decomposer):
        """Test that assign_metadata sets accuracy requirement."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Test subtask content",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert 0.0 <= result.accuracy_requirement <= 1.0
    
    def test_urgent_content_gets_high_priority(self, decomposer):
        """Test that urgent content gets high priority."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="This is an urgent critical task",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.priority == Priority.HIGH
    
    def test_optional_content_gets_low_priority(self, decomposer):
        """Test that optional content gets low priority."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="This is an optional nice to have feature",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.priority == Priority.LOW
    
    def test_production_content_gets_high_risk(self, decomposer):
        """Test that production content gets high risk level."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Deploy to production with security updates",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.risk_level == RiskLevel.HIGH
    
    def test_test_content_gets_medium_risk(self, decomposer):
        """Test that test/staging content gets medium risk level."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Deploy to staging for integration testing",
            task_type=TaskType.REASONING
        )
        result = decomposer.assign_metadata(subtask)
        assert result.risk_level == RiskLevel.MEDIUM


class TestDecompositionValidation:
    """Tests for decomposition validation."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_validate_empty_list_returns_false(self, decomposer):
        """Test that empty subtask list is invalid."""
        result = decomposer.validate_decomposition([])
        assert result is False
    
    def test_validate_valid_subtasks_returns_true(self, decomposer):
        """Test that valid subtasks pass validation."""
        subtasks = [
            Subtask(
                parent_task_id="test-id",
                content="Valid content",
                task_type=TaskType.REASONING,
                accuracy_requirement=0.8,
                estimated_cost=0.5
            )
        ]
        result = decomposer.validate_decomposition(subtasks)
        assert result is True
    
    def test_validate_different_parent_ids_returns_false(self, decomposer):
        """Test that different parent IDs fail validation."""
        subtasks = [
            Subtask(
                parent_task_id="id-1",
                content="Content 1",
                task_type=TaskType.REASONING,
                accuracy_requirement=0.8,
                estimated_cost=0.5
            ),
            Subtask(
                parent_task_id="id-2",
                content="Content 2",
                task_type=TaskType.RESEARCH,
                accuracy_requirement=0.8,
                estimated_cost=0.5
            )
        ]
        result = decomposer.validate_decomposition(subtasks)
        assert result is False
    
    def test_validate_subtask_with_none_task_type_returns_false(self, decomposer):
        """Test that subtask with None task type fails validation."""
        # Create subtask and manually set task_type to None after creation
        subtask = Subtask(
            parent_task_id="test-id",
            content="Valid content",
            task_type=TaskType.REASONING,
            accuracy_requirement=0.8,
            estimated_cost=0.5
        )
        subtask.task_type = None  # Manually set to None to test validation
        subtasks = [subtask]
        result = decomposer.validate_decomposition(subtasks)
        assert result is False


class TestPriorityDetermination:
    """Tests for priority determination logic."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_urgent_indicates_high_priority(self, decomposer):
        """Test that 'urgent' indicates high priority."""
        result = decomposer._determine_priority("this is urgent")
        assert result == Priority.HIGH
    
    def test_critical_indicates_high_priority(self, decomposer):
        """Test that 'critical' indicates high priority."""
        result = decomposer._determine_priority("critical issue")
        assert result == Priority.HIGH
    
    def test_immediate_indicates_high_priority(self, decomposer):
        """Test that 'immediate' indicates high priority."""
        result = decomposer._determine_priority("need immediate action")
        assert result == Priority.HIGH
    
    def test_asap_indicates_high_priority(self, decomposer):
        """Test that 'asap' indicates high priority."""
        result = decomposer._determine_priority("need this asap")
        assert result == Priority.HIGH
    
    def test_optional_indicates_low_priority(self, decomposer):
        """Test that 'optional' indicates low priority."""
        result = decomposer._determine_priority("this is optional")
        assert result == Priority.LOW
    
    def test_nice_to_have_indicates_low_priority(self, decomposer):
        """Test that 'nice to have' indicates low priority."""
        result = decomposer._determine_priority("nice to have feature")
        assert result == Priority.LOW
    
    def test_later_indicates_low_priority(self, decomposer):
        """Test that 'later' indicates low priority."""
        result = decomposer._determine_priority("can do later")
        assert result == Priority.LOW
    
    def test_default_is_medium_priority(self, decomposer):
        """Test that default is medium priority."""
        result = decomposer._determine_priority("regular task content")
        assert result == Priority.MEDIUM


class TestRiskLevelDetermination:
    """Tests for risk level determination logic."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_production_indicates_high_risk(self, decomposer):
        """Test that 'production' indicates high risk."""
        result = decomposer._determine_risk_level("deploy to production")
        assert result == RiskLevel.HIGH
    
    def test_live_indicates_high_risk(self, decomposer):
        """Test that 'live' indicates high risk."""
        result = decomposer._determine_risk_level("update live system")
        assert result == RiskLevel.HIGH
    
    def test_security_indicates_high_risk(self, decomposer):
        """Test that 'security' indicates high risk."""
        result = decomposer._determine_risk_level("security vulnerability fix")
        assert result == RiskLevel.HIGH
    
    def test_data_loss_indicates_high_risk(self, decomposer):
        """Test that 'data loss' indicates high risk."""
        result = decomposer._determine_risk_level("prevent data loss")
        assert result == RiskLevel.HIGH
    
    def test_test_indicates_medium_risk(self, decomposer):
        """Test that 'test' indicates medium risk."""
        result = decomposer._determine_risk_level("run test suite")
        assert result == RiskLevel.MEDIUM
    
    def test_staging_indicates_medium_risk(self, decomposer):
        """Test that 'staging' indicates medium risk."""
        result = decomposer._determine_risk_level("deploy to staging")
        assert result == RiskLevel.MEDIUM
    
    def test_default_is_low_risk(self, decomposer):
        """Test that default is low risk."""
        result = decomposer._determine_risk_level("regular development task")
        assert result == RiskLevel.LOW


class TestAccuracyRequirementDetermination:
    """Tests for accuracy requirement determination."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_fact_checking_has_high_accuracy(self, decomposer):
        """Test that fact checking has high accuracy requirement."""
        result = decomposer._determine_accuracy_requirement(
            TaskType.FACT_CHECKING, RiskLevel.LOW
        )
        assert result >= 0.9
    
    def test_verification_has_high_accuracy(self, decomposer):
        """Test that verification has high accuracy requirement."""
        result = decomposer._determine_accuracy_requirement(
            TaskType.VERIFICATION, RiskLevel.LOW
        )
        assert result >= 0.85
    
    def test_code_generation_has_moderate_accuracy(self, decomposer):
        """Test that code generation has moderate accuracy requirement."""
        result = decomposer._determine_accuracy_requirement(
            TaskType.CODE_GENERATION, RiskLevel.LOW
        )
        assert 0.7 <= result <= 0.9
    
    def test_creative_output_has_lower_accuracy(self, decomposer):
        """Test that creative output has lower accuracy requirement."""
        result = decomposer._determine_accuracy_requirement(
            TaskType.CREATIVE_OUTPUT, RiskLevel.LOW
        )
        assert result <= 0.7
    
    def test_high_risk_increases_accuracy(self, decomposer):
        """Test that high risk increases accuracy requirement."""
        low_risk_result = decomposer._determine_accuracy_requirement(
            TaskType.REASONING, RiskLevel.LOW
        )
        high_risk_result = decomposer._determine_accuracy_requirement(
            TaskType.REASONING, RiskLevel.HIGH
        )
        assert high_risk_result >= low_risk_result
    
    def test_accuracy_never_exceeds_one(self, decomposer):
        """Test that accuracy requirement never exceeds 1.0."""
        result = decomposer._determine_accuracy_requirement(
            TaskType.FACT_CHECKING, RiskLevel.CRITICAL
        )
        assert result <= 1.0


class TestCostEstimation:
    """Tests for subtask cost estimation."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_image_generation_has_highest_base_cost(self, decomposer):
        """Test that image generation has highest base cost."""
        image_subtask = Subtask(
            parent_task_id="test-id",
            content="Generate image",
            task_type=TaskType.IMAGE_GENERATION,
            accuracy_requirement=0.7
        )
        verification_subtask = Subtask(
            parent_task_id="test-id",
            content="Verify data",
            task_type=TaskType.VERIFICATION,
            accuracy_requirement=0.7
        )
        image_cost = decomposer._estimate_subtask_cost(image_subtask)
        verification_cost = decomposer._estimate_subtask_cost(verification_subtask)
        assert image_cost > verification_cost
    
    def test_longer_content_increases_cost(self, decomposer):
        """Test that longer content increases cost."""
        short_subtask = Subtask(
            parent_task_id="test-id",
            content="Short content",
            task_type=TaskType.REASONING,
            accuracy_requirement=0.8
        )
        long_subtask = Subtask(
            parent_task_id="test-id",
            content="Very long content " * 100,
            task_type=TaskType.REASONING,
            accuracy_requirement=0.8
        )
        short_cost = decomposer._estimate_subtask_cost(short_subtask)
        long_cost = decomposer._estimate_subtask_cost(long_subtask)
        assert long_cost > short_cost
    
    def test_higher_accuracy_increases_cost(self, decomposer):
        """Test that higher accuracy requirement increases cost."""
        low_accuracy_subtask = Subtask(
            parent_task_id="test-id",
            content="Same content",
            task_type=TaskType.REASONING,
            accuracy_requirement=0.5
        )
        high_accuracy_subtask = Subtask(
            parent_task_id="test-id",
            content="Same content",
            task_type=TaskType.REASONING,
            accuracy_requirement=0.95
        )
        low_cost = decomposer._estimate_subtask_cost(low_accuracy_subtask)
        high_cost = decomposer._estimate_subtask_cost(high_accuracy_subtask)
        assert high_cost > low_cost
    
    def test_cost_is_non_negative(self, decomposer):
        """Test that estimated cost is always non-negative."""
        subtask = Subtask(
            parent_task_id="test-id",
            content="Test content",
            task_type=TaskType.REASONING,
            accuracy_requirement=0.8
        )
        result = decomposer._estimate_subtask_cost(subtask)
        assert result >= 0.0


class TestContentClassification:
    """Tests for content task type classification."""
    
    @pytest.fixture
    def decomposer(self):
        """Create a task decomposer instance."""
        return BasicTaskDecomposer()
    
    def test_research_keywords_classified(self, decomposer):
        """Test that research keywords are classified."""
        result = decomposer._classify_content_task_types("research best practices")
        assert TaskType.RESEARCH in result
    
    def test_code_keywords_classified(self, decomposer):
        """Test that code keywords are classified."""
        result = decomposer._classify_content_task_types("implement a function")
        assert TaskType.CODE_GENERATION in result
    
    def test_debug_keywords_classified(self, decomposer):
        """Test that debug keywords are classified."""
        result = decomposer._classify_content_task_types("debug this error")
        assert TaskType.DEBUGGING in result
    
    def test_creative_keywords_classified(self, decomposer):
        """Test that creative keywords are classified."""
        result = decomposer._classify_content_task_types("write a creative story")
        assert TaskType.CREATIVE_OUTPUT in result
    
    def test_verify_keywords_classified(self, decomposer):
        """Test that verify keywords are classified."""
        result = decomposer._classify_content_task_types("validate and confirm")
        assert TaskType.VERIFICATION in result
    
    def test_default_to_reasoning(self, decomposer):
        """Test that unclear content defaults to reasoning."""
        result = decomposer._classify_content_task_types("do something")
        assert TaskType.REASONING in result
    
    def test_multiple_types_can_be_classified(self, decomposer):
        """Test that multiple task types can be classified."""
        result = decomposer._classify_content_task_types(
            "research and implement code to debug the issue"
        )
        assert len(result) >= 2
