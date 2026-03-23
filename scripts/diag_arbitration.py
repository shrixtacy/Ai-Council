import asyncio
import sys
from ai_council.arbitration.layer import ConcreteArbitrationLayer
from ai_council.core.models import AgentResponse, SelfAssessment, RiskLevel

async def main():
    try:
        layer = ConcreteArbitrationLayer()
        print("Layer initialized")
        
        assessment = SelfAssessment(
            confidence_score=0.9,
            assumptions=[],
            risk_level=RiskLevel.LOW,
            estimated_cost=0.01,
            token_usage=100,
            execution_time=1.0,
            model_used="model-a"
        )
        
        resp = AgentResponse(
            subtask_id="subtask-1",
            model_used="model-a",
            content="Valid content",
            self_assessment=assessment,
            success=True
        )
        
        print("Response created")
        result = await layer.arbitrate([resp])
        print(f"Arbitration result: {len(result.validated_responses)} validated responses")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

if __name__ == "__main__":
    asyncio.run(main())
