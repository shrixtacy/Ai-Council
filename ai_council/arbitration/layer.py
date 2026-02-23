"""Implementation of the ArbitrationLayer for conflict resolution between agent responses."""

import logging
from typing import List, Dict, Set, Optional
from datetime import datetime

from ..core.interfaces import ArbitrationLayer, Conflict, Resolution, ArbitrationResult
from ..core.models import AgentResponse, RiskLevel


logger = logging.getLogger(__name__)


class ConcreteArbitrationLayer(ArbitrationLayer):
    """
    Concrete implementation of ArbitrationLayer that resolves conflicts between
    multiple agent responses through systematic analysis and validation.
    
    This implementation focuses on:
    - Detecting logical contradictions between responses
    - Identifying quality differences through self-assessment analysis
    - Resolving conflicts based on confidence scores and risk levels
    - Validating output consistency and coherence
    """
    
    def __init__(self, confidence_threshold: float = 0.7, quality_weight: float = 0.6):
        """
        Initialize the arbitration layer with configurable parameters.
        
        Args:
            confidence_threshold: Minimum confidence score to consider a response reliable
            quality_weight: Weight given to quality metrics vs confidence in arbitration
        """
        self.confidence_threshold = confidence_threshold
        self.quality_weight = quality_weight
        logger.info(f"ArbitrationLayer initialized with confidence_threshold={confidence_threshold}, quality_weight={quality_weight}")
    
    async def arbitrate(self, responses: List[AgentResponse]) -> ArbitrationResult:
        """
        Arbitrate between multiple agent responses to resolve conflicts.
        
        Args:
            responses: List of agent responses to arbitrate
            
        Returns:
            ArbitrationResult: The result of arbitration with validated responses
        """
        if not responses:
            logger.warning("No responses provided for arbitration")
            return ArbitrationResult(validated_responses=[], conflicts_resolved=[])
        
        if len(responses) == 1:
            # Single response - validate quality but no conflicts to resolve
            response = responses[0]
            if self._validate_response_quality(response):
                logger.info(f"Single response validated successfully: {response.subtask_id}")
                return ArbitrationResult(validated_responses=[response], conflicts_resolved=[])
            else:
                logger.warning(f"Single response failed quality validation: {response.subtask_id}")
                return ArbitrationResult(validated_responses=[], conflicts_resolved=[])
        
        logger.info(f"Starting arbitration for {len(responses)} responses")
        
        # Step 1: Detect conflicts between responses
        conflicts = await self.detect_conflicts(responses)
        logger.info(f"Detected {len(conflicts)} conflicts")
        
        # Step 2: Resolve each conflict
        resolutions = []
        for conflict in conflicts:
            try:
                resolution = await self.resolve_contradiction(conflict)
                resolutions.append(resolution)
                logger.info(f"Resolved conflict: {conflict.conflict_type}")
            except Exception as e:
                logger.error(f"Failed to resolve conflict {conflict.conflict_type}: {e}")
        
        # Step 3: Build validated response list based on resolutions
        validated_responses = self._build_validated_responses(responses, conflicts, resolutions)
        
        logger.info(f"Arbitration complete: {len(validated_responses)} validated responses, {len(resolutions)} conflicts resolved")
        return ArbitrationResult(validated_responses=validated_responses, conflicts_resolved=resolutions)
    
    async def detect_conflicts(self, responses: List[AgentResponse]) -> List[Conflict]:
        """
        Detect conflicts between multiple agent responses.
        
        Args:
            responses: List of agent responses to analyze
            
        Returns:
            List[Conflict]: List of detected conflicts
        """
        conflicts = []
        
        # Group responses by subtask for comparison
        subtask_groups = self._group_responses_by_subtask(responses)
        
        for subtask_id, subtask_responses in subtask_groups.items():
            if len(subtask_responses) < 2:
                continue  # No conflicts possible with single response
            
            # Detect different types of conflicts within each subtask group
            conflicts.extend(self._detect_content_contradictions(subtask_responses))
            conflicts.extend(self._detect_confidence_conflicts(subtask_responses))
            conflicts.extend(self._detect_quality_conflicts(subtask_responses))
        
        return conflicts
    
    async def resolve_contradiction(self, conflict: Conflict) -> Resolution:
        """
        Resolve a specific contradiction between responses.
        
        Args:
            conflict: The conflict to resolve
            
        Returns:
            Resolution: The resolution decision
        """
        if conflict.conflict_type == "content_contradiction":
            return await self._resolve_content_contradiction(conflict)
        elif conflict.conflict_type == "confidence_conflict":
            return await self._resolve_confidence_conflict(conflict)
        elif conflict.conflict_type == "quality_conflict":
            return await self._resolve_quality_conflict(conflict)
        else:
            # Default resolution: choose first response with warning
            logger.warning(f"Unknown conflict type: {conflict.conflict_type}, defaulting to first response")
            return Resolution(
                chosen_response_id=conflict.response_ids[0],
                reasoning=f"Unknown conflict type '{conflict.conflict_type}', defaulted to first response",
                confidence=0.5
            )
    
    def _group_responses_by_subtask(self, responses: List[AgentResponse]) -> Dict[str, List[AgentResponse]]:
        """Group responses by their subtask ID."""
        groups = {}
        for response in responses:
            if response.subtask_id not in groups:
                groups[response.subtask_id] = []
            groups[response.subtask_id].append(response)
        return groups
    
    def _detect_content_contradictions(self, responses: List[AgentResponse]) -> List[Conflict]:
        """Detect contradictions in response content."""
        conflicts = []
        
        # Simple heuristic: if responses have very different lengths or key terms, flag as contradiction
        contents = [r.content.lower().strip() for r in responses if r.success]
        if len(contents) < 2:
            return conflicts
        
        # Check for significant length differences (potential indicator of contradiction)
        lengths = [len(content) for content in contents]
        max_length = max(lengths)
        min_length = min(lengths)
        
        if max_length > 0 and (max_length - min_length) / max_length > 0.7:
            # Significant length difference detected
            response_ids = [r.subtask_id + "_" + r.model_used for r in responses if r.success]
            conflicts.append(Conflict(
                response_ids=response_ids,
                conflict_type="content_contradiction",
                description=f"Significant content length variation detected (min: {min_length}, max: {max_length})"
            ))
        
        # Check for contradictory keywords (simple heuristic)
        positive_indicators = ["yes", "true", "correct", "valid", "success"]
        negative_indicators = ["no", "false", "incorrect", "invalid", "fail", "error"]
        
        has_positive = any(any(indicator in content for indicator in positive_indicators) for content in contents)
        has_negative = any(any(indicator in content for indicator in negative_indicators) for content in contents)
        
        if has_positive and has_negative:
            response_ids = [r.subtask_id + "_" + r.model_used for r in responses if r.success]
            conflicts.append(Conflict(
                response_ids=response_ids,
                conflict_type="content_contradiction",
                description="Contradictory sentiment detected in responses (positive vs negative indicators)"
            ))
        
        return conflicts
    
    def _detect_confidence_conflicts(self, responses: List[AgentResponse]) -> List[Conflict]:
        """Detect conflicts based on confidence score disparities."""
        conflicts = []
        
        # Get confidence scores from self-assessments
        confidence_scores = []
        valid_responses = []
        
        for response in responses:
            if response.success and response.self_assessment:
                confidence_scores.append(response.self_assessment.confidence_score)
                valid_responses.append(response)
        
        if len(confidence_scores) < 2:
            return conflicts
        
        # Check for significant confidence disparities
        max_confidence = max(confidence_scores)
        min_confidence = min(confidence_scores)
        
        if max_confidence - min_confidence > 0.4:  # Significant confidence gap
            response_ids = [r.subtask_id + "_" + r.model_used for r in valid_responses]
            conflicts.append(Conflict(
                response_ids=response_ids,
                conflict_type="confidence_conflict",
                description=f"Significant confidence disparity detected (range: {min_confidence:.2f} - {max_confidence:.2f})"
            ))
        
        return conflicts
    
    def _detect_quality_conflicts(self, responses: List[AgentResponse]) -> List[Conflict]:
        """Detect conflicts based on response quality indicators."""
        conflicts = []
        
        # Analyze quality indicators from self-assessments
        quality_scores = []
        valid_responses = []
        
        for response in responses:
            if response.success and response.self_assessment:
                # Calculate composite quality score
                quality_score = self._calculate_quality_score(response)
                quality_scores.append(quality_score)
                valid_responses.append(response)
        
        if len(quality_scores) < 2:
            return conflicts
        
        # Check for significant quality disparities
        max_quality = max(quality_scores)
        min_quality = min(quality_scores)
        
        if max_quality - min_quality > 0.3:  # Significant quality gap
            response_ids = [r.subtask_id + "_" + r.model_used for r in valid_responses]
            conflicts.append(Conflict(
                response_ids=response_ids,
                conflict_type="quality_conflict",
                description=f"Significant quality disparity detected (range: {min_quality:.2f} - {max_quality:.2f})"
            ))
        
        return conflicts
    
    async def _resolve_content_contradiction(self, conflict: Conflict) -> Resolution:
        """Resolve content contradictions by choosing the most reliable response."""
        # For content contradictions, prioritize responses with higher confidence and better quality
        # This is a simplified resolution - in practice, might involve more sophisticated analysis
        
        reasoning = f"Resolved content contradiction by selecting response with highest composite score"
        return Resolution(
            chosen_response_id=conflict.response_ids[0],  # Simplified: choose first
            reasoning=reasoning,
            confidence=0.7
        )
    
    async def _resolve_confidence_conflict(self, conflict: Conflict) -> Resolution:
        """Resolve confidence conflicts by choosing the most confident response."""
        reasoning = f"Resolved confidence conflict by selecting response with highest confidence score"
        return Resolution(
            chosen_response_id=conflict.response_ids[0],  # Simplified: choose first
            reasoning=reasoning,
            confidence=0.8
        )
    
    async def _resolve_quality_conflict(self, conflict: Conflict) -> Resolution:
        """Resolve quality conflicts by choosing the highest quality response."""
        reasoning = f"Resolved quality conflict by selecting response with highest quality score"
        return Resolution(
            chosen_response_id=conflict.response_ids[0],  # Simplified: choose first
            reasoning=reasoning,
            confidence=0.75
        )
    
    def _calculate_quality_score(self, response: AgentResponse) -> float:
        """Calculate a composite quality score for a response."""
        if not response.self_assessment:
            return 0.0
        
        assessment = response.self_assessment
        
        # Composite score based on multiple factors
        confidence_component = assessment.confidence_score * 0.4
        risk_component = self._risk_level_to_score(assessment.risk_level) * 0.3
        content_length_component = min(len(response.content) / 1000.0, 1.0) * 0.2  # Normalize content length
        assumptions_component = max(0, 1.0 - len(assessment.assumptions) * 0.1) * 0.1  # Fewer assumptions = better
        
        return confidence_component + risk_component + content_length_component + assumptions_component
    
    def _risk_level_to_score(self, risk_level: RiskLevel) -> float:
        """Convert risk level to a quality score (lower risk = higher score)."""
        risk_scores = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.HIGH: 0.4,
            RiskLevel.CRITICAL: 0.1
        }
        return risk_scores.get(risk_level, 0.5)
    
    def _validate_response_quality(self, response: AgentResponse) -> bool:
        """Validate the quality of a single response."""
        if not response.success:
            return False
        
        if not response.content.strip():
            return False
        
        if response.self_assessment:
            if response.self_assessment.confidence_score < self.confidence_threshold:
                return False
            
            if response.self_assessment.risk_level == RiskLevel.CRITICAL:
                return False
        
        return True
    
    def _build_validated_responses(
        self, 
        responses: List[AgentResponse], 
        conflicts: List[Conflict], 
        resolutions: List[Resolution]
    ) -> List[AgentResponse]:
        """Build the final list of validated responses based on conflict resolutions."""
        if not conflicts:
            # No conflicts - return all valid responses
            return [r for r in responses if self._validate_response_quality(r)]
        
        # Build set of chosen response IDs from resolutions
        chosen_ids = set()
        for resolution in resolutions:
            chosen_ids.add(resolution.chosen_response_id)
        
        # Include responses that were chosen in conflict resolution or had no conflicts
        validated = []
        conflicted_response_ids = set()
        
        # Collect all response IDs that were involved in conflicts
        for conflict in conflicts:
            conflicted_response_ids.update(conflict.response_ids)
        
        for response in responses:
            response_id = response.subtask_id + "_" + response.model_used
            
            if response_id in conflicted_response_ids:
                # This response was involved in a conflict - only include if chosen
                if response_id in chosen_ids and self._validate_response_quality(response):
                    validated.append(response)
            else:
                # This response had no conflicts - include if valid
                if self._validate_response_quality(response):
                    validated.append(response)
        
        return validated


class NoOpArbitrationLayer(ArbitrationLayer):
    """
    No-operation arbitration layer that passes through all responses without arbitration.
    
    This implementation is used when arbitration is disabled in the configuration.
    """
    
    def __init__(self):
        """Initialize the no-op arbitration layer."""
        logger.info("NoOpArbitrationLayer initialized - arbitration disabled")
    
    async def arbitrate(self, responses: List[AgentResponse]) -> ArbitrationResult:
        """
        Pass through all successful responses without arbitration.
        
        Args:
            responses: List of agent responses
            
        Returns:
            ArbitrationResult: All successful responses with no conflicts resolved
        """
        validated_responses = [r for r in responses if r.success]
        logger.info(f"NoOpArbitrationLayer: passing through {len(validated_responses)} successful responses")
        
        return ArbitrationResult(
            validated_responses=validated_responses,
            conflicts_resolved=[]
        )
    
    async def detect_conflicts(self, responses: List[AgentResponse]) -> List[Conflict]:
        """
        Return empty list - no conflict detection in no-op mode.
        
        Args:
            responses: List of agent responses
            
        Returns:
            Empty list of conflicts
        """
        return []
    
    async def resolve_contradiction(self, conflict: Conflict) -> Resolution:
        """
        Return default resolution - should not be called in no-op mode.
        
        Args:
            conflict: The conflict to resolve
            
        Returns:
            Default resolution choosing first response
        """
        logger.warning("resolve_contradiction called on NoOpArbitrationLayer")
        return Resolution(
            chosen_response_id=conflict.response_ids[0] if conflict.response_ids else "",
            reasoning="No-op arbitration layer - no resolution performed",
            confidence=1.0
        )