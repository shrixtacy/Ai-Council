import pytest
from ai_council.synthesis.layer import SynthesisLayerImpl


@pytest.mark.asyncio
async def test_code_block_preserved():
    layer = SynthesisLayerImpl()

    input_text = """Here is code:
```python
def hello():
    print("hello")
```

End of response.
"""

    result = await layer.normalize_output(input_text)

    assert "def hello()" in result
    assert "print(\"hello\")" in result
    assert "```" in result