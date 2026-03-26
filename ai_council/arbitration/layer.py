"""Implementation of the ArbitrationLayer for conflict resolution between agent responses."""

from difflib import SequenceMatcher


from ai_council.core.logger import get_logger
from typing import List, Dict, Set, Optional
from datetime import datetime

from ..core.interfaces import ArbitrationLayer, Conflict, Resolution, ArbitrationResult
from ..core.models import AgentResponse, RiskLevel


logger = get_logger(__name__)
class ArbitrationExplanation:
    def __init__(self, models_used, conflicts, decisions):
        self.models_used = models_used
        self.conflicts = conflicts
        self.decisions = decisions
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            "models_used": self.models_used,
            "conflicts": self.conflicts,
            "decisions": self.decisions,
            "timestamp": str(self.timestamp),
            "extra": getattr(self, "extra", None)
        }


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
        logger.info("ArbitrationLayer initialized", extra={"confidence_threshold": confidence_threshold, "quality_weight": quality_weight})
    
    def _calculate_similarity(self, responses):
        scores = []
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                s = SequenceMatcher(None, responses[i].content, responses[j].content).ratio()
                scores.append(s)
        return sum(scores) / len(scores) if scores else 1.0

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
                logger.info("Single response validated successfully", extra={"subtask_id": response.subtask_id})
                return ArbitrationResult(validated_responses=[response], conflicts_resolved=[])
            else:
                logger.warning("Single response failed quality validation", extra={"subtask_id": response.subtask_id})
                return ArbitrationResult(validated_responses=[], conflicts_resolved=[])
        
        logger.info("Starting arbitration for", extra={"count": len(responses)})
        
        # ✅ Capture models used for explainability
        models_used = [r.model_used for r in responses]
        # ✅ Remove duplicates
        models_used = list(set(models_used))

        # ✅ Confidence scores per model
        confidence_scores = [
            {
                "model": r.model_used,
                "confidence": r.self_assessment.confidence_score if r.self_assessment else 0.5
            }
            for r in responses
        ]

        # ✅ Similarity score
        similarity_score = self._calculate_similarity(responses)

        
        # Step 1: Detect conflicts between responses
        conflicts = await self.detect_conflicts(responses)
        conflict_detected = len(conflicts) > 0

        logger.info("Detected", extra={"count": len(conflicts)})
        # ✅ Prepare conflict info for explainability
        conflict_info = [
            {
                "type": c.conflict_type,
                "description": c.description,
                "responses": c.response_ids
            }
            for c in conflicts
        ]


        # Step 2: Resolve each conflict
        resolutions = []
        decisions = []

        for conflict in conflicts:
            try:
                resolution = await self.resolve_contradiction(conflict, responses=responses)
                resolutions.append(resolution)

            # ✅ Track decision details for explainability
                decisions.append({
                    "conflict_type": conflict.conflict_type,
                    "chosen_response": resolution.chosen_response_id,
                    "reason": resolution.reasoning,
                    "confidence": resolution.confidence
                })

                logger.info("Resolved conflict", extra={"conflict_type": conflict.conflict_type})
            except Exception as e:
                logger.error(
                    "Failed to resolve conflict", 
                    extra={"conflict_type": conflict.conflict_type, "error": str(e)}
                )
                
        
        # Step 3: Build validated response list based on resolutions
        validated_responses = self._build_validated_responses(responses, conflicts, resolutions)

        selected_response = validated_responses[0] if validated_responses else None
        selected_model = selected_response.model_used if selected_response else None


        extra_explanation = None
        if selected_response:
            extra_explanation = self.build_explanation(responses, selected_response)

        
        logger.info(
            "Arbitration complete", 
            extra={"validated_responses": len(validated_responses), "resolutions": len(resolutions)}
        )
    
        # ✅ Create explanation object
        explanation = ArbitrationExplanation(
            models_used=models_used,
            conflicts=conflict_info,
            decisions=decisions
        )

        # 🔥 ADD THESE NEW FIELDS
        explanation.similarity_score = round(similarity_score, 3)
        explanation.conflict_detected = conflict_detected
        explanation.confidence_scores = confidence_scores
        explanation.selected_model = selected_model

        explanation.extra = extra_explanation
    
        # ✅ Return ArbitrationResult with explanation
        return ArbitrationResult(
            validated_responses=validated_responses,
            conflicts_resolved=resolutions,
            explanation=explanation
        )

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
    
    async def resolve_contradiction(self, conflict: Conflict, responses: Optional[List[AgentResponse]] = None) -> Resolution:
        """
        Resolve a specific contradiction between responses.
        
        Args:
            conflict: The conflict to resolve
            responses: Optional list of responses used to evaluate conflict
            
        Returns:
            Resolution: The resolution decision
        """
        if conflict.conflict_type == "content_contradiction":
            return await self._resolve_content_contradiction(conflict, responses)
        elif conflict.conflict_type == "confidence_conflict":
            return await self._resolve_confidence_conflict(conflict, responses)
        elif conflict.conflict_type == "quality_conflict":
            return await self._resolve_quality_conflict(conflict, responses)
        else:
            # Unknown conflict type: still attempt score-based fallback when possible
            logger.warning("Unknown conflict type", extra={"conflict_type": conflict.conflict_type})
            best_resp = self._select_best_response_for_conflict(conflict, responses)
            chosen_response_id = best_resp.subtask_id + "_" + best_resp.model_used if best_resp else conflict.response_ids[0]
            return Resolution(
                chosen_response_id=chosen_response_id,
                reasoning=(
                    f"Unknown conflict type '{conflict.conflict_type}', "
                    "selected best available response by composite quality score"
                    if best_resp
                    else f"Unknown conflict type '{conflict.conflict_type}', defaulted to first response"
                ),
                confidence=0.55 if best_resp else 0.5
            )

    def _select_best_response_for_conflict(
        self,
        conflict: Conflict,
        responses: Optional[List[AgentResponse]] = None,
    ) -> Optional[AgentResponse]:
        """Select best response for a conflict using confidence + quality scoring.

        Selection order:
        1. Responses matching conflict IDs exactly (`subtask_model` format)
        2. Best-effort matching by model ID token from conflict IDs
        3. Fallback to all successful responses
        """
        if not responses:
            return None

        successful = [r for r in responses if r.success]
        if not successful:
            return None

        response_map = {
            f"{r.subtask_id}_{r.model_used}": r
            for r in successful
        }

        # 1) Exact conflict-id matches
        candidates = [response_map[rid] for rid in conflict.response_ids if rid in response_map]

        # 2) Best-effort model-id matching when IDs are malformed/partial
        if not candidates:
            model_tokens = {rid.split("_", 1)[-1] for rid in conflict.response_ids if "_" in rid}
            if model_tokens:
                candidates = [r for r in successful if r.model_used in model_tokens]

        # 3) Final fallback to all successful responses
        if not candidates:
            candidates = successful

        return max(
            candidates,
            key=lambda r: (
                self._calculate_quality_score(r),
                r.self_assessment.confidence_score if r.self_assessment else 0.0,
            ),
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
        
        valid_responses = [r for r in responses if r.success]
        if len(valid_responses) < 2:
            return conflicts
            
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            logger.error("sentence_transformers not installed for content contradiction detection.")
            return conflicts
            
        if getattr(self, '_encoder', None) is None:
            self._encoder = SentenceTransformer('all-MiniLM-L6-v2')
            
        contents = [str(r.content).strip() for r in valid_responses]
        response_ids = [r.subtask_id + "_" + r.model_used for r in valid_responses]
        
        embeddings = self._encoder.encode(contents, convert_to_tensor=True)
        sim_matrix = util.cos_sim(embeddings, embeddings)
        
        conflict_detected = False
        min_sim = 1.0
        
        for i in range(len(valid_responses)):
            for j in range(i + 1, len(valid_responses)):
                sim = sim_matrix[i][j].item()
                min_sim = min(min_sim, sim)
                if sim < 0.8:
                    conflict_detected = True
                    
        if conflict_detected:
            conflicts.append(Conflict(
                response_ids=response_ids,
                conflict_type="content_contradiction",
                description=f"Semantic contradiction detected (min similarity: {min_sim:.2f})"
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
    
    async def _resolve_content_contradiction(self, conflict: Conflict, responses: Optional[List[AgentResponse]] = None) -> Resolution:
        """Resolve content contradictions by choosing the most reliable response."""
        best_resp = self._select_best_response_for_conflict(conflict, responses)
        if not best_resp:
            return Resolution(
                chosen_response_id=conflict.response_ids[0],
                reasoning="Resolved content contradiction by default (no responses context)",
                confidence=0.7
            )

        return Resolution(
            chosen_response_id=best_resp.subtask_id + "_" + best_resp.model_used,
            reasoning="Resolved content contradiction by selecting response with highest composite score",
            confidence=0.7
        )
    
    async def _resolve_confidence_conflict(self, conflict: Conflict, responses: Optional[List[AgentResponse]] = None) -> Resolution:
        """Resolve confidence conflicts by choosing the most confident response."""
        best_resp = self._select_best_response_for_conflict(conflict, responses)
        if not best_resp:
            return Resolution(
                chosen_response_id=conflict.response_ids[0],
                reasoning="Resolved confidence conflict by default (no responses context)",
                confidence=0.8
            )

        return Resolution(
            chosen_response_id=best_resp.subtask_id + "_" + best_resp.model_used,
            reasoning="Resolved confidence conflict by selecting response with highest confidence score",
            confidence=0.8
        )
    
    async def _resolve_quality_conflict(self, conflict: Conflict, responses: Optional[List[AgentResponse]] = None) -> Resolution:
        """Resolve quality conflicts by choosing the highest quality response."""
        best_resp = self._select_best_response_for_conflict(conflict, responses)
        if not best_resp:
            return Resolution(
                chosen_response_id=conflict.response_ids[0],
                reasoning="Resolved quality conflict by default (no responses context)",
                confidence=0.75
            )

        return Resolution(
            chosen_response_id=best_resp.subtask_id + "_" + best_resp.model_used,
            reasoning="Resolved quality conflict by selecting response with highest quality score",
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
    
    def build_explanation(self, responses, selected_response):
        models_compared = []

        for resp in responses:
            models_compared.append({
                "model": resp.model_used,
                "confidence": (
                    resp.self_assessment.confidence_score
                    if resp.self_assessment else 0.5
                ),
                "content": resp.content[:100]
            })
        
        similarity = None

        if len(responses) >= 2:
            similarity = self.simple_similarity(
            responses[0].content,
            responses[1].content
        )

        explanation = {
            "selected_model": selected_response.model_used,
            "reason": "Highest confidence score",
            "models_compared": models_compared,
            "similarity_score": similarity,
            "conflict_detected": True if len(responses) > 1 else False

        }

        return explanation
    

    def simple_similarity(self, text1, text2):
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        common = words1.intersection(words2)
        total = words1.union(words2)

        if not total:
            return 0

        return len(common) / len(total)




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
        logger.info("NoOpArbitrationLayer: passing through", extra={"count": len(validated_responses)})
        
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
    
    async def resolve_contradiction(self, conflict: Conflict, responses: Optional[List[AgentResponse]] = None) -> Resolution:
        """
        Return default resolution - should not be called in no-op mode.
        
        Args:
            conflict: The conflict to resolve
            responses: Optional list of responses used to evaluate conflict
            
        Returns:
            Default resolution choosing first response
        """
        logger.warning("resolve_contradiction called on NoOpArbitrationLayer")
        return Resolution(
            chosen_response_id=conflict.response_ids[0] if conflict.response_ids else "",
            reasoning="No-op arbitration layer - no resolution performed",
            confidence=1.0
        )