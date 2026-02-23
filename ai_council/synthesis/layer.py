"""Implementation of the SynthesisLayer for final output generation."""

import re
from typing import List, Dict, Set, Optional
from datetime import datetime

from ..core.interfaces import SynthesisLayer, ExecutionMetadata
from ..core.models import AgentResponse, FinalResponse, CostBreakdown


class SynthesisLayerImpl(SynthesisLayer):
    """Implementation of the SynthesisLayer for producing final coherent responses."""
    
    def __init__(self):
        """Initialize the synthesis layer."""
        self._redundancy_threshold = 0.7  # Similarity threshold for redundancy detection
        self._max_response_length = 5000  # Maximum length for final response
    
    async def synthesize(self, validated_responses: List[AgentResponse]) -> FinalResponse:
        """Synthesize a final response from validated agent responses.
        
        This method combines multiple validated responses into a single coherent output
        by removing redundancy, ensuring consistency, and maintaining alignment with
        the original user intent.
        
        Args:
            validated_responses: List of validated agent responses from arbitration
            
        Returns:
            FinalResponse: The final synthesized response
            
        Raises:
            ValueError: If no validated responses are provided
        """
        if not validated_responses:
            return FinalResponse(
                content="",
                overall_confidence=0.0,
                success=False,
                error_message="No validated responses available for synthesis"
            )
        
        try:
            # Extract content from all responses
            response_contents = [resp.content for resp in validated_responses if resp.success]
            
            if not response_contents:
                return FinalResponse(
                    content="",
                    overall_confidence=0.0,
                    success=False,
                    error_message="No successful responses available for synthesis"
                )
            
            # Remove redundant content
            deduplicated_content = self._remove_redundancy(response_contents)
            
            # Synthesize into coherent response
            synthesized_content = self._synthesize_content(deduplicated_content)
            
            # Normalize the output
            normalized_content = await self.normalize_output(synthesized_content)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(validated_responses)
            
            # Extract models used
            models_used = list(set(resp.model_used for resp in validated_responses))
            
            # Create cost breakdown
            cost_breakdown = self._create_cost_breakdown(validated_responses)
            
            return FinalResponse(
                content=normalized_content,
                overall_confidence=overall_confidence,
                cost_breakdown=cost_breakdown,
                models_used=models_used,
                success=True
            )
            
        except Exception as e:
            return FinalResponse(
                content="",
                overall_confidence=0.0,
                success=False,
                error_message=f"Synthesis failed: {str(e)}"
            )
    
    async def normalize_output(self, content: str) -> str:
        """Normalize output content for consistency in tone and structure.
        
        This method standardizes formatting, removes excessive whitespace,
        and ensures consistent tone throughout the response.
        
        Args:
            content: Raw content to normalize
            
        Returns:
            str: Normalized content with consistent formatting and tone
        """
        if not content:
            return ""
        
        # Remove excessive whitespace and normalize line breaks
        normalized = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        normalized = re.sub(r'[ \t]+', ' ', normalized)
        normalized = normalized.strip()
        
        # Ensure sentences end with proper punctuation
        sentences = normalized.split('. ')
        normalized_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence.endswith(('.', '!', '?', ':')):
                sentence += '.'
            if sentence:
                normalized_sentences.append(sentence)
        
        normalized = '. '.join(normalized_sentences)
        
        # Remove redundant phrases and normalize tone
        normalized = self._normalize_tone(normalized)
        
        # Truncate if too long
        if len(normalized) > self._max_response_length:
            normalized = normalized[:self._max_response_length - 3] + "..."
        
        return normalized
    
    async def attach_metadata(self, response: FinalResponse, metadata: ExecutionMetadata) -> FinalResponse:
        """Attach execution metadata to the final response for explainability.
        
        This method adds detailed execution information to the response,
        enabling users to understand how the response was generated.
        
        Args:
            response: The final response to attach metadata to
            metadata: Execution metadata containing process information
            
        Returns:
            FinalResponse: Response with attached execution metadata
        """
        # Create a new response with the metadata attached
        return FinalResponse(
            content=response.content,
            overall_confidence=response.overall_confidence,
            execution_metadata=metadata,
            cost_breakdown=response.cost_breakdown,
            models_used=response.models_used,
            timestamp=response.timestamp,
            success=response.success,
            error_message=response.error_message
        )
    
    def _remove_redundancy(self, contents: List[str]) -> List[str]:
        """Remove redundant content from multiple responses.
        
        Args:
            contents: List of response contents
            
        Returns:
            List[str]: Deduplicated content list
        """
        if not contents:
            return []
        
        if len(contents) == 1:
            return contents
        
        # Simple redundancy removal based on content similarity
        deduplicated = []
        
        for content in contents:
            is_redundant = False
            content_words = set(content.lower().split())
            
            for existing in deduplicated:
                existing_words = set(existing.lower().split())
                
                # Calculate Jaccard similarity
                intersection = len(content_words & existing_words)
                union = len(content_words | existing_words)
                
                if union > 0:
                    similarity = intersection / union
                    if similarity > self._redundancy_threshold:
                        is_redundant = True
                        break
            
            if not is_redundant:
                deduplicated.append(content)
        
        return deduplicated
    
    def _synthesize_content(self, contents: List[str]) -> str:
        """Synthesize multiple content pieces into a coherent response.
        
        Args:
            contents: List of deduplicated content pieces
            
        Returns:
            str: Synthesized coherent content
        """
        if not contents:
            return ""
        
        if len(contents) == 1:
            return contents[0]
        
        # For multiple contents, combine them logically
        # This is a simple implementation - in production, this could use
        # more sophisticated NLP techniques
        
        # Sort by length to prioritize more comprehensive responses
        sorted_contents = sorted(contents, key=len, reverse=True)
        
        # Start with the most comprehensive response
        synthesized = sorted_contents[0]
        
        # Add unique information from other responses
        for content in sorted_contents[1:]:
            unique_info = self._extract_unique_information(content, synthesized)
            if unique_info:
                synthesized += f"\n\nAdditionally, {unique_info}"
        
        return synthesized
    
    def _extract_unique_information(self, new_content: str, existing_content: str) -> str:
        """Extract unique information from new content that's not in existing content.
        
        Args:
            new_content: New content to analyze
            existing_content: Existing synthesized content
            
        Returns:
            str: Unique information, if any
        """
        # Simple implementation: look for sentences in new_content not in existing_content
        new_sentences = [s.strip() for s in new_content.split('.') if s.strip()]
        existing_sentences = [s.strip() for s in existing_content.split('.') if s.strip()]
        
        unique_sentences = []
        for sentence in new_sentences:
            sentence_words = set(sentence.lower().split())
            is_unique = True
            
            for existing_sentence in existing_sentences:
                existing_words = set(existing_sentence.lower().split())
                
                # Check if sentence is substantially different
                if sentence_words and existing_words:
                    intersection = len(sentence_words & existing_words)
                    union = len(sentence_words | existing_words)
                    similarity = intersection / union if union > 0 else 0
                    
                    if similarity > 0.6:  # Lower threshold for unique info
                        is_unique = False
                        break
            
            if is_unique and len(sentence) > 10:  # Ignore very short sentences
                unique_sentences.append(sentence)
        
        return '. '.join(unique_sentences[:3])  # Limit to 3 unique sentences
    
    def _normalize_tone(self, content: str) -> str:
        """Normalize tone and remove redundant phrases.
        
        Args:
            content: Content to normalize
            
        Returns:
            str: Content with normalized tone
        """
        # Remove common redundant phrases
        redundant_phrases = [
            r'\b(in conclusion|to conclude|in summary|to summarize)\b,?\s*',
            r'\b(as mentioned|as stated|as discussed)\s+(earlier|before|above)\b,?\s*',
            r'\b(it is important to note that|it should be noted that)\b,?\s*',
            r'\b(please note that|note that)\b,?\s*'
        ]
        
        normalized = content
        for phrase_pattern in redundant_phrases:
            normalized = re.sub(phrase_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up any double spaces created by removals
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def _calculate_overall_confidence(self, responses: List[AgentResponse]) -> float:
        """Calculate overall confidence from multiple agent responses.
        
        Args:
            responses: List of agent responses
            
        Returns:
            float: Overall confidence score between 0.0 and 1.0
        """
        if not responses:
            return 0.0
        
        successful_responses = [r for r in responses if r.success and r.self_assessment]
        
        if not successful_responses:
            return 0.0
        
        # Calculate weighted average confidence
        total_confidence = 0.0
        total_weight = 0.0
        
        for response in successful_responses:
            if response.self_assessment:
                confidence = response.self_assessment.confidence_score
                # Weight by inverse of risk level (lower risk = higher weight)
                risk_weights = {'low': 1.0, 'medium': 0.8, 'high': 0.6, 'critical': 0.4}
                weight = risk_weights.get(response.self_assessment.risk_level.value, 0.5)
                
                total_confidence += confidence * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        overall_confidence = total_confidence / total_weight
        
        # Apply penalty for multiple conflicting responses
        if len(successful_responses) > 1:
            # Small penalty for having to synthesize multiple responses
            penalty = min(0.1, (len(successful_responses) - 1) * 0.02)
            overall_confidence = max(0.0, overall_confidence - penalty)
        
        return min(1.0, overall_confidence)
    
    def _create_cost_breakdown(self, responses: List[AgentResponse]) -> CostBreakdown:
        """Create cost breakdown from agent responses.
        
        Args:
            responses: List of agent responses
            
        Returns:
            CostBreakdown: Detailed cost information
        """
        total_cost = 0.0
        model_costs = {}
        token_usage = {}
        total_execution_time = 0.0
        
        for response in responses:
            if response.self_assessment:
                assessment = response.self_assessment
                
                # Accumulate costs
                total_cost += assessment.estimated_cost
                
                # Track per-model costs
                model_id = response.model_used
                if model_id in model_costs:
                    model_costs[model_id] += assessment.estimated_cost
                else:
                    model_costs[model_id] = assessment.estimated_cost
                
                # Track token usage
                if model_id in token_usage:
                    token_usage[model_id] += assessment.token_usage
                else:
                    token_usage[model_id] = assessment.token_usage
                
                # Track execution time
                total_execution_time += assessment.execution_time
        
        return CostBreakdown(
            total_cost=total_cost,
            model_costs=model_costs,
            token_usage=token_usage,
            execution_time=total_execution_time
        )


class NoOpSynthesisLayer(SynthesisLayer):
    """
    No-operation synthesis layer that returns the first response without synthesis.
    
    This implementation is used when synthesis is disabled in the configuration.
    """
    
    def __init__(self):
        """Initialize the no-op synthesis layer."""
        pass
    
    async def synthesize(self, validated_responses: List[AgentResponse]) -> FinalResponse:
        """
        Return the first successful response without synthesis.
        
        Args:
            validated_responses: List of validated agent responses
            
        Returns:
            FinalResponse: The first successful response as final response
        """
        if not validated_responses:
            return FinalResponse(
                content="",
                overall_confidence=0.0,
                success=False,
                error_message="No validated responses available",
                models_used=[]
            )
        
        # Find first successful response
        first_successful = None
        for response in validated_responses:
            if response.success:
                first_successful = response
                break
        
        if not first_successful:
            return FinalResponse(
                content="",
                overall_confidence=0.0,
                success=False,
                error_message="No successful responses available",
                models_used=[]
            )
        
        # Convert AgentResponse to FinalResponse
        confidence = (first_successful.self_assessment.confidence_score 
                     if first_successful.self_assessment else 0.5)
        
        cost_breakdown = None
        if first_successful.self_assessment:
            cost_breakdown = CostBreakdown(
                total_cost=first_successful.self_assessment.estimated_cost,
                execution_time=first_successful.self_assessment.execution_time
            )
        
        return FinalResponse(
            content=first_successful.content,
            overall_confidence=confidence,
            cost_breakdown=cost_breakdown,
            models_used=[first_successful.model_used],
            success=True
        )
    
    async def normalize_output(self, content: str) -> str:
        """
        Return content as-is without normalization.
        
        Args:
            content: Raw content
            
        Returns:
            str: Unchanged content
        """
        return content
    
    async def attach_metadata(self, response: FinalResponse, metadata: ExecutionMetadata) -> FinalResponse:
        """
        Attach metadata to response.
        
        Args:
            response: The final response
            metadata: Execution metadata
            
        Returns:
            FinalResponse: Response with attached metadata
        """
        return FinalResponse(
            content=response.content,
            overall_confidence=response.overall_confidence,
            execution_metadata=metadata,
            cost_breakdown=response.cost_breakdown,
            models_used=response.models_used,
            timestamp=response.timestamp,
            success=response.success,
            error_message=response.error_message
        )