import pytest
import json
from multi_rag import stream_answer

@pytest.mark.asyncio
async def test_conversation_memory():
    session_id = "test-uuid-memory-1234"
    
    # 1. Ask about Paddy
    chunks1 = []
    async for chunk in stream_answer("What is the MSP of paddy?", session_id=session_id):
        if chunk.startswith("data: ") and not chunk.strip() == "data: [DONE]":
            try:
                data = json.loads(chunk[6:].strip())
                if "chunk" in data:
                    chunks1.append(data["chunk"])
            except:
                pass
    answer1 = "".join(chunks1)
    
    # 2. Ask a follow-up question that relies on context
    chunks2 = []
    async for chunk in stream_answer("What crop did I just ask you about?", session_id=session_id):
        if chunk.startswith("data: ") and not chunk.strip() == "data: [DONE]":
            try:
                data = json.loads(chunk[6:].strip())
                if "chunk" in data:
                    chunks2.append(data["chunk"])
            except:
                pass
    answer2 = "".join(chunks2).lower()
    
    assert "paddy" in answer2 or "msp" in answer2, f"Memory failed. Answer 2: {answer2}"
