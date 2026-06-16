# multi_rag.py
"""LangGraph CRAG Engine for AgriMitra AI.

Implements a Corrective RAG (CRAG) pipeline using LangGraph StateGraph:
  1. Route   — keyword-match the query to 1-3 specialized agents
  2. Retrieve — FAISS similarity search per agent
  3. Evaluate — LLM scores retrieval relevance (0-1)
  4. Conditional — if score < 0.6 → web search, else → synthesize
  5. Synthesize — LLM generates the final answer
  6. Reflect  — LLM checks answer quality before returning

Conversation memory is persisted per session via SqliteSaver checkpointer.
"""

import os
import json
import logging
import asyncio
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import structlog
import time

load_dotenv()

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# AgriState — Typed state flowing through the LangGraph
# ---------------------------------------------------------------------------
class AgriState(TypedDict):
    query: str
    retrieved_docs: List[Dict]
    retrieval_score: float
    needs_web_search: bool
    answer: str
    conversation_history: List[Dict]
    # Operational fields used internally by nodes
    agents_used: List[str]
    sources: List[str]
    web_context: str
    language: str
    answer_quality: str
    quality_note: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FAISS_INDEX_PATH = Path(__file__).parent / "faiss_index"
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

LLM_AVAILABLE = False
LLM = None
EMBEDDINGS = None
VECTORDB = None
CROSS_ENCODER = None


def _init_components():
    """Lazy initialization of LLM, embeddings, and vector store."""
    global LLM_AVAILABLE, LLM, EMBEDDINGS, VECTORDB, CROSS_ENCODER

    if EMBEDDINGS is not None:
        return  # Already initialized

    try:
        import torch
        torch.set_num_threads(1)  # Reduce memory usage on Render's 512MB free tier
        from langchain_community.embeddings import HuggingFaceEmbeddings
        EMBEDDINGS = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={'device': 'cpu'}
        )
        logger.info(f"Loaded embedding model: {EMBEDDING_MODEL_NAME}")
    except Exception as e:
        logger.error(f"Failed to load embeddings: {e}")
        return

    if CROSS_ENCODER is None:
        pass # Disabled to save memory on Render's 512MB free tier
        # try:
        #     from sentence_transformers import CrossEncoder
        #     CROSS_ENCODER = CrossEncoder(CROSS_ENCODER_MODEL_NAME)
        #     logger.info(f"Loaded CrossEncoder model: {CROSS_ENCODER_MODEL_NAME}")
        # except Exception as e:
        #     logger.error(f"Failed to load CrossEncoder: {e}")

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
from dataclasses import dataclass

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
# Core Logic (used by nodes and kept as public API for tests)
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


def agent_retrieve(agent_id: str, query: str) -> List[Dict]:
    """Retrieve relevant document chunks for a specific agent."""
    _init_components()
    config = AGENTS[agent_id]
    results = []

    if VECTORDB is None:
        return results

    try:
        docs = VECTORDB.similarity_search(query, k=20)
        
        if CROSS_ENCODER is not None and docs:
            pairs = [[query, doc.page_content] for doc in docs]
            scores = CROSS_ENCODER.predict(pairs)
            doc_score_pairs = list(zip(docs, scores))
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
            top_docs = [doc for doc, score in doc_score_pairs[:5]]
        else:
            top_docs = docs[:5]

        for doc in top_docs:
            results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "agent": agent_id,
            })
    except Exception as e:
        logger.error(f"Agent {agent_id} retrieval error: {e}")

    return results


def _web_search(query: str) -> tuple[str, List[str]]:
    """Use DuckDuckGo to fetch live web data. Returns (context_str, source_list)."""
    try:
        from duckduckgo_search import DDGS
        logger.info(f"CRAG web search for: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
            if not results:
                return "", []

            web_sources = []
            web_context = "\n--- 🌐 Live Web Search (CRAG Corrective Retrieval) ---\n"
            for r in results:
                source_domain = r.get('href', 'web').split('/')[2] if 'href' in r else 'web'
                web_sources.append(source_domain)
                web_context += f"[Source: {source_domain}]\n{r.get('body', '')}\n\n"
            return web_context, web_sources
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return "", []


# ---------------------------------------------------------------------------
# LangGraph Nodes
# ---------------------------------------------------------------------------
def route_node(state: AgriState) -> dict:
    """Node 1: Route the query to the best-matching agents."""
    agents = route_query(state["query"])
    logger.info(f"[route_node] Selected agents: {agents}")
    return {"agents_used": agents}


def retrieve_node(state: AgriState) -> dict:
    """Node 2: Retrieve relevant documents from FAISS for each routed agent."""
    all_docs = []
    all_sources = []

    for agent_id in state["agents_used"]:
        results = agent_retrieve(agent_id, state["query"])
        all_docs.extend(results)
        for r in results:
            source = Path(r["source"]).name if r["source"] != "unknown" else "unknown"
            if source not in all_sources:
                all_sources.append(source)

    logger.info(f"[retrieve_node] Retrieved {len(all_docs)} chunks from {len(all_sources)} sources")
    return {"retrieved_docs": all_docs, "sources": all_sources}


def evaluate_retrieval_node(state: AgriState) -> dict:
    """Node 3 (CRAG): LLM evaluates whether retrieved docs actually answer the query.

    Returns a relevance score (0-1). If score < 0.6, the pipeline
    triggers corrective web search before synthesis.
    """
    _init_components()
    docs = state["retrieved_docs"]

    # If no docs retrieved at all, definitely need web search
    if not docs:
        logger.info("[evaluate_retrieval_node] No docs retrieved → needs_web_search=True")
        return {"retrieval_score": 0.0, "needs_web_search": True}

    # If LLM unavailable, use a simple heuristic
    if not LLM_AVAILABLE or LLM is None:
        score = min(len(docs) / 5.0, 1.0)
        logger.info(f"[evaluate_retrieval_node] Heuristic score: {score:.2f}")
        return {"retrieval_score": score, "needs_web_search": score < 0.6}

    # LLM-based relevance grading (the core of CRAG)
    doc_snippets = "\n\n".join(
        f"[Doc {i+1}]: {d['content'][:300]}" for i, d in enumerate(docs[:5])
    )

    grading_prompt = f"""You are a retrieval evaluator. Score how well the following retrieved documents answer the user's question.

USER QUESTION: {state["query"]}

RETRIEVED DOCUMENTS:
{doc_snippets}

SCORING RULES:
- 1.0 = Documents directly and fully answer the question
- 0.7-0.9 = Documents are highly relevant and partially answer
- 0.4-0.6 = Documents are somewhat related but don't directly answer
- 0.1-0.3 = Documents are barely relevant
- 0.0 = Documents are completely irrelevant

Respond with ONLY a single decimal number between 0.0 and 1.0. Nothing else."""

    try:
        start_time = time.time()
        response = LLM.invoke(grading_prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("LLM call completed", llm_node="evaluate_retrieval", latency_ms=latency_ms)
        score_text = response.content.strip()
        # Parse the score — handle edge cases
        score = float(score_text.split()[0])
        score = max(0.0, min(1.0, score))
    except Exception as e:
        logger.warning(f"[evaluate_retrieval_node] LLM scoring failed: {e}, using heuristic")
        score = min(len(docs) / 5.0, 1.0)

    needs_search = score < 0.6
    logger.info(f"[evaluate_retrieval_node] Relevance score: {score:.2f}, needs_web_search: {needs_search}")
    return {"retrieval_score": score, "needs_web_search": needs_search}


def web_search_node(state: AgriState) -> dict:
    """Node 4 (Conditional): Corrective web search when retrieval is insufficient."""
    web_context, web_sources = _web_search(state["query"])
    updated_sources = list(state.get("sources", [])) + web_sources
    logger.info(f"[web_search_node] Added {len(web_sources)} web sources")
    return {"web_context": web_context, "sources": updated_sources}


def synthesize_node(state: AgriState) -> dict:
    """Node 5: LLM synthesizes retrieved context + web search into a final answer."""
    _init_components()

    # Build context from retrieved docs
    context_parts = []
    agents_used = state.get("agents_used", [])
    docs = state.get("retrieved_docs", [])

    # Group docs by agent
    agent_docs: Dict[str, List[Dict]] = {}
    for doc in docs:
        aid = doc.get("agent", "unknown")
        agent_docs.setdefault(aid, []).append(doc)

    for agent_id in agents_used:
        if agent_id in AGENTS and agent_id in agent_docs:
            config = AGENTS[agent_id]
            agent_context = f"\n--- {config.emoji} {config.name} (Local DB) ---\n"
            for chunk in agent_docs[agent_id]:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                agent_context += f"[Source: {source}]\n{chunk['content']}\n\n"
            context_parts.append(agent_context)

    # Append web context if CRAG triggered it
    web_context = state.get("web_context", "")
    full_context = "\n".join(context_parts) + web_context

    agents_consulted = ", ".join(
        f"{AGENTS[a].emoji} {AGENTS[a].name}" for a in agents_used if a in AGENTS
    )

    if not full_context.strip():
        full_context = "No specific local or web documents retrieved. Answer based on your own knowledge."

    language = state.get("language", "English")

    # Use LLM if available
    if LLM_AVAILABLE and LLM is not None:
        try:
            prompt = SYNTHESIS_PROMPT.format(
                agents_consulted=agents_consulted,
                context=full_context,
                question=state["query"],
                language=language,
            )
            start_time = time.time()
            response = LLM.invoke(prompt)
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info("LLM call completed", llm_node="synthesize", latency_ms=latency_ms)
            answer = response.content
            logger.info(f"[synthesize_node] Generated answer ({len(answer)} chars)")
            return {"answer": answer}
        except Exception as e:
            logger.error(f"[synthesize_node] LLM synthesis failed: {e}")

    # Fallback
    fallback = f"**Agents consulted:** {agents_consulted}\n\n"
    fallback += "**Based on available information:**\n\n"
    for agent_id in agents_used:
        if agent_id in AGENTS and agent_id in agent_docs:
            config = AGENTS[agent_id]
            fallback += f"### {config.emoji} {config.name}\n"
            for chunk in agent_docs[agent_id]:
                source = Path(chunk["source"]).name if chunk["source"] != "unknown" else "unknown"
                content = chunk["content"][:500]
                fallback += f"{content}\n*[Source: {source}]*\n\n"

    return {"answer": fallback}


def reflect_node(state: AgriState) -> dict:
    """Node 6: LLM reviews the generated answer for quality before returning.

    Checks for completeness, accuracy relative to context, and helpfulness.
    If quality is poor, adds a note indicating limitations.
    """
    _init_components()
    answer = state.get("answer", "")

    if not answer or not LLM_AVAILABLE or LLM is None:
        return {"answer_quality": "unverified", "quality_note": ""}

    try:
        reflect_prompt = f"""You are a quality reviewer for an agricultural AI assistant.

USER QUESTION: {state["query"]}

GENERATED ANSWER:
{answer[:2000]}

Evaluate this answer and respond with ONLY valid JSON:
{{
  "quality": "good" or "needs_improvement",
  "note": "Brief explanation if needs_improvement, otherwise empty string"
}}

Criteria:
- Does it address the question directly?
- Is it factually plausible for Indian agriculture?
- Is it actionable and practical for a farmer?

JSON only, no markdown:"""

        start_time = time.time()
        response = LLM.invoke(reflect_prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("LLM call completed", llm_node="reflect", latency_ms=latency_ms)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)
        quality = result.get("quality", "good")
        note = result.get("note", "")

        # If reflection found issues, append a disclaimer to the answer
        if quality == "needs_improvement" and note:
            updated_answer = answer + f"\n\n---\n⚠️ *Note: {note}*"
            logger.info(f"[reflect_node] Quality: {quality} — {note}")
            return {"answer": updated_answer, "answer_quality": quality, "quality_note": note}

        logger.info(f"[reflect_node] Quality: {quality}")
        return {"answer_quality": quality, "quality_note": ""}

    except Exception as e:
        logger.warning(f"[reflect_node] Reflection failed: {e}")
        return {"answer_quality": "unverified", "quality_note": ""}


# ---------------------------------------------------------------------------
# Prompts
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


# ---------------------------------------------------------------------------
# Conditional Edge
# ---------------------------------------------------------------------------
def _should_web_search(state: AgriState) -> str:
    """Conditional edge: route to web_search if retrieval score < 0.6."""
    if state.get("needs_web_search", False):
        logger.info("[conditional] Retrieval insufficient → web_search")
        return "web_search"
    logger.info("[conditional] Retrieval sufficient → synthesize")
    return "synthesize"


# ---------------------------------------------------------------------------
# Build & Compile the LangGraph StateGraph
# ---------------------------------------------------------------------------
workflow = StateGraph(AgriState)

# Add nodes
workflow.add_node("route", route_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("evaluate", evaluate_retrieval_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("synthesize", synthesize_node)
workflow.add_node("reflect", reflect_node)

# Wire edges
workflow.set_entry_point("route")
workflow.add_edge("route", "retrieve")
workflow.add_edge("retrieve", "evaluate")
workflow.add_conditional_edges("evaluate", _should_web_search, {
    "web_search": "web_search",
    "synthesize": "synthesize",
})
workflow.add_edge("web_search", "synthesize")
workflow.add_edge("synthesize", "reflect")
workflow.add_edge("reflect", END)

# Compile base graph (without checkpointer) globally
crag_graph_base = workflow.compile()
DB_PATH = Path(__file__).parent / "checkpoints.db"
logger.info("LangGraph CRAG pipeline base compiled")


# ---------------------------------------------------------------------------
# Streaming Entry Point — stream_answer()
# ---------------------------------------------------------------------------
async def stream_answer(query: str, language: str = "English", session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
    """Process a query through the LangGraph CRAG pipeline and stream the result as SSE.

    Uses astream_events to capture LLM token-level streaming from the
    synthesize node, providing real-time output to the frontend.

    Args:
        query: The user's question.
        language: Target language for the answer.
        session_id: Optional UUID to enable conversation memory via checkpointer.
    """
    logger.info(f"Processing CRAG query: {query[:100]}... (session={session_id})")

    initial_state: AgriState = {
        "query": query,
        "retrieved_docs": [],
        "retrieval_score": 0.0,
        "needs_web_search": False,
        "answer": "",
        "conversation_history": [],
        "agents_used": [],
        "sources": [],
        "web_context": "",
        "language": language,
        "answer_quality": "",
        "quality_note": "",
    }

    # Config with thread_id enables per-session state persistence
    config = {}
    if session_id:
        config = {"configurable": {"thread_id": session_id}}

    final_state = {}
    streamed_synthesis = False

    try:
        async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
            # Recompile graph with the checkpointer for this session
            crag_graph = workflow.compile(checkpointer=checkpointer)
            
            async for event in crag_graph.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event", "")
                
                # Stream LLM tokens ONLY from the synthesize node
                if kind == "on_chat_model_stream":
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if node_name == "synthesize":
                        token = event["data"]["chunk"].content
                        if token:
                            streamed_synthesis = True
                            yield f"data: {json.dumps({'chunk': token}, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.01)

                # Capture final graph output
                if kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "answer" in output:
                        final_state = output

    except Exception as e:
        logger.error(f"CRAG graph execution failed: {e}", exc_info=True)
        yield f"data: {json.dumps({'chunk': f'Error processing query: {str(e)}'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # If astream_events didn't stream tokens (e.g., fallback mode),
    # chunk the completed answer manually
    if not streamed_synthesis and final_state.get("answer"):
        answer = final_state["answer"]
        chunk_size = 20
        for i in range(0, len(answer), chunk_size):
            yield f"data: {json.dumps({'chunk': answer[i:i+chunk_size]}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)

    # Build and yield final metadata
    agents_used = final_state.get("agents_used", [])
    agents_info = []
    for agent_id in agents_used:
        if agent_id in AGENTS:
            config = AGENTS[agent_id]
            docs_for_agent = [d for d in final_state.get("retrieved_docs", []) if d.get("agent") == agent_id]
            agents_info.append({
                "id": config.id,
                "name": config.name,
                "emoji": config.emoji,
                "description": config.description,
                "chunks_retrieved": len(docs_for_agent),
            })

    metadata = {
        "sources": final_state.get("sources", []),
        "agents_used": agents_info,
        "retrieval_score": final_state.get("retrieval_score", 0.0),
        "web_search_used": final_state.get("needs_web_search", False),
        "answer_quality": final_state.get("answer_quality", ""),
    }
    yield f"data: {json.dumps({'metadata': metadata}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Public API (unchanged for main.py and tests)
# ---------------------------------------------------------------------------
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
