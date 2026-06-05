# multi_rag.py
"""Multi-RAG Engine for AgriMitra AI.

Implements a multi-agent RAG (Retrieval-Augmented Generation) architecture with
5 specialized agents that route, retrieve, and synthesize answers from domain-specific
knowledge bases.

Now augmented with Corrective RAG (CRAG) using DuckDuckGo for live web search
and streaming response support.
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FAISS_INDEX_PATH = Path(__file__).parent / "faiss_index"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Try to load Google Gemini/Groq; fall back to a simple echo if unavailable
LLM_AVAILABLE = False
LLM = None
EMBEDDINGS = None
VECTORDB = None


def _init_components():
    """Lazy initialization of LLM, embeddings, and vector store."""
    global LLM_AVAILABLE, LLM, EMBEDDINGS, VECTORDB

    if EMBEDDINGS is not None:
        return  # Already initialized

    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        EMBEDDINGS = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        logger.info(f"Loaded embedding model: {EMBEDDING_MODEL_NAME}")
    except Exception as e:
        logger.error(f"Failed to load embeddings: {e}")
        return

    # Load FAISS index
    if FAISS_INDEX_PATH.exists():
        try:
            from langchain_community.vectorstores import FAISS
            VECTORDB = FAISS.load_local(
                str(FAISS_INDEX_PATH),
                EMBEDDINGS,
                allow_dangerous_deserialization=True,
            )
            logger.info(f"Loaded FAISS index from {FAISS_INDEX_PATH}")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
    else:
        logger.warning(f"FAISS index not found at {FAISS_INDEX_PATH}. Run ingest.py first.")

    # Try Groq LLM
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from langchain_groq import ChatGroq
            LLM = ChatGroq(
                model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                groq_api_key=api_key,
                temperature=0.3,
            )
            LLM_AVAILABLE = True
            logger.info("Groq LLM initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Groq LLM: {e}")
    else:
        logger.warning("GROQ_API_KEY not set. LLM features will use fallback mode.")


# ---------------------------------------------------------------------------
# Agent Definitions
# ---------------------------------------------------------------------------
@dataclass
class AgentConfig:
    """Configuration for a single RAG agent."""
    id: str
    name: str
    emoji: str
    description: str
    keywords: List[str]
    retrieval_k: int = 4  # Number of chunks to retrieve


AGENTS: Dict[str, AgentConfig] = {
    "crop_advisor": AgentConfig(
        id="crop_advisor",
        name="Crop Advisor",
        emoji="🌾",
        description="Expert in crop diseases, pest management, chemical & organic remedies, and cultivation best practices",
        keywords=[
            "crop", "disease", "pest", "fungus", "virus", "bacteria", "blast",
            "bollworm", "armyworm", "leaf", "wilt", "blight", "rot", "spray",
            "fungicide", "pesticide", "insecticide", "remedy", "organic",
            "chemical", "treatment", "symptom", "paddy", "rice", "cotton",
            "maize", "groundnut", "chilli", "wheat", "soybean", "cultivation",
            "sowing", "harvest", "fertilizer", "nitrogen", "phosphorus",
            "potassium", "urea", "DAP", "NPK", "seed", "variety", "hybrid",
            "yield", "irrigation", "plant", "farming",
        ],
        retrieval_k=5,
    ),
    "market_analyst": AgentConfig(
        id="market_analyst",
        name="Market Analyst",
        emoji="📊",
        description="Specialist in MSP rates, mandi prices, market trends, demand forecasts, storage, and export data",
        keywords=[
            "market", "price", "msp", "mandi", "rate", "cost", "sell",
            "buy", "demand", "supply", "export", "import", "trade",
            "quintal", "ton", "rupee", "₹", "storage", "warehouse",
            "cold storage", "apmc", "e-nam", "procurement", "profit",
            "income", "revenue", "value", "premium", "grade", "today", "live"
        ],
        retrieval_k=4,
    ),
    "schemes_expert": AgentConfig(
        id="schemes_expert",
        name="Schemes Expert",
        emoji="🏛️",
        description="Authority on government agricultural schemes, subsidies, eligibility criteria, and application processes",
        keywords=[
            "scheme", "subsidy", "government", "pm-kisan", "kisan", "pmfby",
            "insurance", "loan", "credit", "kcc", "rythu", "bharosa",
            "bandhu", "benefit", "eligibility", "apply", "application",
            "registration", "dbt", "transfer", "support", "assistance",
            "grant", "policy", "niti", "mission", "yojana", "pradhan",
            "mantri", "soil health", "micro irrigation", "horticulture",
        ],
        retrieval_k=4,
    ),
    "weather_analyst": AgentConfig(
        id="weather_analyst",
        name="Weather Analyst",
        emoji="🌦️",
        description="Expert on seasonal weather patterns, climate risks, monsoon forecasts, and agricultural weather advisories",
        keywords=[
            "weather", "rain", "rainfall", "monsoon", "temperature", "heat",
            "cold", "frost", "hail", "cyclone", "flood", "drought",
            "season", "kharif", "rabi", "zaid", "summer", "winter",
            "climate", "wind", "humidity", "forecast", "advisory",
            "risk", "hazard", "storm", "warning", "today", "tomorrow"
        ],
        retrieval_k=4,
    ),
    "leaf_scanner": AgentConfig(
        id="leaf_scanner",
        name="Leaf Scanner",
        emoji="🔬",
        description="Identifies plant diseases from symptom descriptions and provides targeted treatment recommendations",
        keywords=[
            "scan", "identify", "leaf", "spot", "curl", "yellow",
            "brown", "wilt", "deform", "hole", "damage", "image",
            "photo", "upload", "diagnose", "detection", "analysis",
            "appearance", "color", "shape", "pattern", "lesion",
        ],
        retrieval_k=5,
    ),
}


# ---------------------------------------------------------------------------
# Router — Classify query into agent domains
# ---------------------------------------------------------------------------
def route_query(query: str) -> List[str]:
    """Route a query to the most relevant agents using keyword matching."""
    query_lower = query.lower()
    scores: Dict[str, int] = {}

    for agent_id, config in AGENTS.items():
        score = sum(1 for kw in config.keywords if kw in query_lower)
        if score > 0:
            scores[agent_id] = score

    if not scores:
        return ["crop_advisor"]

    sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_agents = [agent_id for agent_id, _score in sorted_agents[:3]]
    logger.info(f"Routed query to agents: {top_agents}")
    return top_agents


# ---------------------------------------------------------------------------
# Agent Retrieval — Each agent retrieves from the shared FAISS index
# ---------------------------------------------------------------------------
def agent_retrieve(agent_id: str, query: str) -> List[Dict]:
    """Retrieve relevant document chunks for a specific agent."""
    _init_components()
    config = AGENTS[agent_id]
    results = []

    if VECTORDB is None:
        return results

    try:
        docs = VECTORDB.similarity_search(query, k=config.retrieval_k)
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "agent": agent_id,
            })
    except Exception as e:
        logger.error(f"Agent {agent_id} retrieval error: {e}")

    return results


# ---------------------------------------------------------------------------
# Corrective RAG (Web Search Augmentation)
# ---------------------------------------------------------------------------
def augment_with_web_search(query: str, all_sources: set) -> str:
    """Use DuckDuckGo to fetch live web data for up-to-date prices, news, or missing context."""
    try:
        from duckduckgo_search import DDGS
        logger.info(f"Augmenting context with DuckDuckGo search for: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
            if not results:
                return ""
            
            web_context = "\n--- 🌐 Live Web Search (Corrective RAG) ---\n"
            for r in results:
                source_domain = r.get('href', 'web').split('/')[2] if 'href' in r else 'web'
                all_sources.add(source_domain)
                web_context += f"[Source: {source_domain}]\n{r.get('body', '')}\n\n"
            return web_context
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Synthesizer — Merge multi-agent results and Stream Answer
# ---------------------------------------------------------------------------
SYNTHESIS_PROMPT = """You are AgriMitra AI, an expert agricultural assistant serving Indian farmers.
You have received information from specialized agents and live web search results.
Synthesize their findings into a single, clear, actionable answer.

AGENTS CONSULTED: {agents_consulted}

RETRIEVED CONTEXT (Local DB & Live Web):
{context}

USER QUESTION: {question}

INSTRUCTIONS:
1. Provide a comprehensive answer using the retrieved context above.
2. If the retrieved context doesn't contain the exact answer, use your own general knowledge to assist the user, but specify what is from your knowledge.
3. Cite sources in square brackets if used, e.g., [icar_guidelines.txt] or [domain.com].
4. Organize your answer with clear sections if multiple topics are covered.
5. Include specific numbers (prices, dosages, dates) when available.
6. Keep the tone helpful and practical.
7. CRITICAL: You must provide the final answer entirely in the following language: {language}.

ANSWER:"""


async def synthesize_answer_stream(query: str, agent_results: Dict[str, List[Dict]], agents_used: List[str], all_sources: set, language: str = "English") -> AsyncGenerator[str, None]:
    """Synthesize retrieved chunks and web search into a streaming final answer."""
    _init_components()

    # Build context from all agent results
    context_parts = []
    for agent_id in agents_used:
        config = AGENTS[agent_id]
        chunks = agent_results.get(agent_id, [])
        if chunks:
            agent_context = f"\n--- {config.emoji} {config.name} (Local DB) ---\n"
            for chunk in chunks:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                agent_context += f"[Source: {source}]\n{chunk['content']}\n\n"
            context_parts.append(agent_context)

    # Corrective RAG: Always augment with live web search for maximum freshness
    web_context = augment_with_web_search(query, all_sources)
    
    full_context = "\n".join(context_parts) + web_context
    agents_consulted = ", ".join(f"{AGENTS[a].emoji} {AGENTS[a].name}" for a in agents_used)

    if not full_context.strip():
        # Even if context is empty, allow the LLM to answer using its own knowledge
        full_context = "No specific local or web documents retrieved. Answer based on your own knowledge."

    # Use LLM if available
    if LLM_AVAILABLE and LLM is not None:
        try:
            prompt = SYNTHESIS_PROMPT.format(
                agents_consulted=agents_consulted,
                context=full_context,
                question=query,
                language=language
            )
            # Stream the response
            async for chunk in LLM.astream(prompt):
                if chunk.content:
                    yield chunk.content
            return
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Fall through to fallback

    # Fallback if LLM fails
    fallback = f"**Agents consulted:** {agents_consulted}\n\n"
    fallback += "**Based on available information:**\n\n"
    for agent_id in agents_used:
        config = AGENTS[agent_id]
        chunks = agent_results.get(agent_id, [])
        if chunks:
            fallback += f"### {config.emoji} {config.name}\n"
            for chunk in chunks:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                content = chunk["content"][:500]
                fallback += f"{content}\n*[Source: {source}]*\n\n"
    yield fallback


# ---------------------------------------------------------------------------
# Streaming Entry Point — stream_answer()
# ---------------------------------------------------------------------------
async def stream_answer(query: str, language: str = "English") -> AsyncGenerator[str, None]:
    """Process a query through the Multi-RAG pipeline and stream the result as SSE."""
    logger.info(f"Processing streaming query: {query[:100]}...")

    # Step 1: Route
    agents_used = route_query(query)
    logger.info(f"Selected agents: {agents_used}")

    # Step 2: Retrieve (from each agent)
    agent_results: Dict[str, List[Dict]] = {}
    all_sources = set()
    for agent_id in agents_used:
        results = agent_retrieve(agent_id, query)
        agent_results[agent_id] = results
        for r in results:
            source = Path(r["source"]).name if r["source"] != "unknown" else "unknown"
            all_sources.add(source)

    # Step 3: Synthesize and Stream
    async for text_chunk in synthesize_answer_stream(query, agent_results, agents_used, all_sources, language):
        # Yield as Server-Sent Event with ensure_ascii=False to support native unicode characters
        yield f"data: {json.dumps({'chunk': text_chunk}, ensure_ascii=False)}\n\n"
        # Small sleep to allow event loop to breathe
        await asyncio.sleep(0.01)

    # Step 4: Build and yield final metadata
    agents_info = []
    for agent_id in agents_used:
        config = AGENTS[agent_id]
        agents_info.append({
            "id": config.id,
            "name": config.name,
            "emoji": config.emoji,
            "description": config.description,
            "chunks_retrieved": len(agent_results.get(agent_id, [])),
        })

    metadata = {
        "sources": list(all_sources),
        "agents_used": agents_info,
    }
    yield f"data: {json.dumps({'metadata': metadata}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def get_all_agents() -> List[Dict]:
    """Return metadata for all available agents."""
    return [
        {
            "id": config.id,
            "name": config.name,
            "emoji": config.emoji,
            "description": config.description,
        }
        for config in AGENTS.values()
    ]
