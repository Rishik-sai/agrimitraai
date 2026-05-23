# multi_rag.py
"""Multi-RAG Engine for AgriMitra AI.

Implements a multi-agent RAG (Retrieval-Augmented Generation) architecture with
5 specialized agents that route, retrieve, and synthesize answers from domain-specific
knowledge bases.

Agents:
  1. Crop Advisor      — diseases, pests, remedies, cultivation practices
  2. Market Analyst    — MSP, mandi prices, demand, storage, export
  3. Schemes Expert    — government schemes, subsidies, eligibility, applications
  4. Weather Analyst   — seasonal advisories, weather risks, climate management
  5. Leaf Scanner      — disease identification from symptom descriptions

Architecture:
  Query → Router → [Selected Agents] → Parallel Retrieval → Synthesizer → Response
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FAISS_INDEX_PATH = Path(__file__).parent / "faiss_index"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Try to load Google Gemini; fall back to a simple echo if unavailable
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
            "income", "revenue", "value", "premium", "grade",
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
            "risk", "hazard", "storm", "warning",
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
    """Route a query to the most relevant agents using keyword matching.

    Returns a list of agent IDs sorted by relevance score (highest first).
    Always returns at least one agent (crop_advisor as default).
    """
    query_lower = query.lower()
    scores: Dict[str, int] = {}

    for agent_id, config in AGENTS.items():
        score = sum(1 for kw in config.keywords if kw in query_lower)
        if score > 0:
            scores[agent_id] = score

    if not scores:
        # Default to crop_advisor if no keywords match
        return ["crop_advisor"]

    # Sort by score descending, take top 3 agents
    sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_agents = [agent_id for agent_id, _score in sorted_agents[:3]]

    logger.info(f"Routed query to agents: {top_agents} (scores: {dict(sorted_agents[:3])})")
    return top_agents


# ---------------------------------------------------------------------------
# Agent Retrieval — Each agent retrieves from the shared FAISS index
# ---------------------------------------------------------------------------
def agent_retrieve(agent_id: str, query: str) -> List[Dict]:
    """Retrieve relevant document chunks for a specific agent.

    Returns a list of dicts with 'content', 'source', and 'agent' fields.
    """
    _init_components()

    config = AGENTS[agent_id]
    results = []

    if VECTORDB is None:
        logger.warning("No vector store available. Returning empty results.")
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
# Synthesizer — Merge multi-agent results into a coherent answer
# ---------------------------------------------------------------------------
SYNTHESIS_PROMPT = """You are AgriMitra AI, an expert agricultural assistant serving Indian farmers.
You have received information from multiple specialized agents. Synthesize their findings into
a single, clear, actionable answer.

AGENTS CONSULTED: {agents_consulted}

RETRIEVED CONTEXT:
{context}

USER QUESTION: {question}

INSTRUCTIONS:
1. Provide a comprehensive answer using ONLY the retrieved context above.
2. Cite sources in square brackets, e.g., [icar_guidelines.txt].
3. Organize your answer with clear sections if multiple topics are covered.
4. Include specific numbers (prices, dosages, dates) when available.
5. If the context doesn't contain enough information, say so honestly.
6. Keep the tone helpful and practical for farmers.
7. CRITICAL: You must provide the final answer entirely in the following language: {language}.

ANSWER:"""


def synthesize_answer(query: str, agent_results: Dict[str, List[Dict]], agents_used: List[str], language: str = "English") -> str:
    """Synthesize retrieved chunks from multiple agents into a final answer."""
    _init_components()

    # Build context from all agent results
    context_parts = []
    for agent_id in agents_used:
        config = AGENTS[agent_id]
        chunks = agent_results.get(agent_id, [])
        if chunks:
            agent_context = f"\n--- {config.emoji} {config.name} ---\n"
            for chunk in chunks:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                agent_context += f"[Source: {source}]\n{chunk['content']}\n\n"
            context_parts.append(agent_context)

    full_context = "\n".join(context_parts)
    agents_consulted = ", ".join(f"{AGENTS[a].emoji} {AGENTS[a].name}" for a in agents_used)

    if not full_context.strip():
        return "I don't have enough information in my knowledge base to answer that question. Please try rephrasing or ask about Indian agriculture topics like crops, market prices, government schemes, or weather advisories."

    # Use LLM if available
    if LLM_AVAILABLE and LLM is not None:
        try:
            prompt = SYNTHESIS_PROMPT.format(
                agents_consulted=agents_consulted,
                context=full_context,
                question=query,
                language=language
            )
            response = LLM.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Fall through to fallback

    # Fallback: return context directly with formatting
    fallback = f"**Agents consulted:** {agents_consulted}\n\n"
    fallback += "**Based on available information:**\n\n"
    for agent_id in agents_used:
        config = AGENTS[agent_id]
        chunks = agent_results.get(agent_id, [])
        if chunks:
            fallback += f"### {config.emoji} {config.name}\n"
            for chunk in chunks:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                # Trim to most relevant excerpt
                content = chunk["content"][:500]
                fallback += f"{content}\n*[Source: {source}]*\n\n"
    return fallback


# ---------------------------------------------------------------------------
# Main Entry Point — get_answer()
# ---------------------------------------------------------------------------
def get_answer(query: str, language: str = "English") -> Dict:
    """Process a query through the Multi-RAG pipeline.

    Steps:
      1. Route query to relevant agents
      2. Each agent retrieves from FAISS
      3. Synthesize all results into a unified answer

    Returns:
      dict with keys: answer, sources, agents_used
    """
    logger.info(f"Processing query: {query[:100]}...")

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

    # Step 3: Synthesize
    answer = synthesize_answer(query, agent_results, agents_used, language)

    # Build agent info for response
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

    return {
        "answer": answer,
        "sources": list(all_sources),
        "agents_used": agents_info,
    }


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


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print(f"{'='*60}\n")

        result = get_answer(q)

        print(f"Agents Used: {', '.join(a['emoji'] + ' ' + a['name'] for a in result['agents_used'])}")
        print(f"Sources: {', '.join(result['sources'])}")
        print(f"\n{'='*60}")
        print(f"Answer:\n{result['answer']}")
        print(f"{'='*60}\n")
    else:
        print("Usage: python multi_rag.py <your question>")
        print("Example: python multi_rag.py What is the MSP of paddy?")
