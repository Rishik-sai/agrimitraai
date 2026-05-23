# main.py
"""FastAPI backend for AgriMitra AI Pro — Multi-RAG System.

Provides API endpoints for:
  - Multi-agent RAG chat
  - Agent listing
  - Geographic data
  - Market prices
  - Government schemes
  - Weather advisories
  - Leaf scan analysis (mock)

Serves the React frontend static files in production.
"""

import logging
from pathlib import Path
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Import the Multi-RAG engine
from multi_rag import get_answer, get_all_agents

app = FastAPI(
    title="AgriMitra AI Pro",
    description="Multi-RAG Agricultural Intelligence System",
    version="2.0.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Language Config
# ---------------------------------------------------------------------------
LANG_MAP = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "or": "Odia",
    "pa": "Punjabi",
    "ta": "Tamil",
}

# ---------------------------------------------------------------------------
# LLM Translation Cache & Engine
# ---------------------------------------------------------------------------
TRANSLATION_CACHE = {}  # key: f"{endpoint}_{lang}" -> translated data


def _get_llm():
    """Get a ChatGroq LLM instance (lazy, shared)."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_api_key=api_key,
            temperature=0.2,
        )
    except Exception:
        return None


def translate_json_via_llm(data, lang_full: str, context_hint: str = "agricultural data"):
    """Use Groq LLM to translate a JSON data structure into a target language.
    Preserves numeric values, keys, and structure — only translates string values.
    """
    llm = _get_llm()
    if not llm:
        return data

    try:
        prompt = f"""You are a professional translator specializing in Indian agricultural terminology.
Translate ALL string values in the following JSON into {lang_full}.
This is {context_hint} for Indian farmers.

RULES:
1. Keep all JSON keys EXACTLY as-is (do NOT translate keys).
2. Translate ONLY the string values into {lang_full}.
3. Keep numbers, currency symbols (₹), percentages, and units as-is.
4. Keep proper nouns like scheme names (PM-KISAN, PMFBY, etc.) as-is but translate their descriptions.
5. Keep URLs/links as-is.
6. Output ONLY valid JSON, no markdown formatting or extra text.

INPUT JSON:
{json.dumps(data, ensure_ascii=False, indent=2)}

OUTPUT (valid JSON only, translated to {lang_full}):"""

        response = llm.invoke(prompt)
        content = response.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        logger.error(f"Translation LLM error for {lang_full}: {e}")
        return data


def get_translated(endpoint: str, original_data, lang: str, context_hint: str = ""):
    """Return cached translation or translate via LLM. English returns original data."""
    lang_full = LANG_MAP.get(lang, "English")
    if lang == "en" or lang_full == "English":
        return original_data

    cache_key = f"{endpoint}_{lang}"
    if cache_key in TRANSLATION_CACHE:
        logger.info(f"Translation cache hit: {cache_key}")
        return TRANSLATION_CACHE[cache_key]

    logger.info(f"Translating {endpoint} to {lang_full}...")
    translated = translate_json_via_llm(original_data, lang_full, context_hint)
    TRANSLATION_CACHE[cache_key] = translated
    return translated


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    language: str = Field(default="en", description="User's selected language")


class ChatResponse(BaseModel):
    answer: str
    sources: list
    agents_used: list


# ---------------------------------------------------------------------------
# Chat Endpoint (Multi-RAG)
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle a chat query using the Multi-RAG pipeline.
    Routes the query to specialized agents, retrieves context, and synthesizes an answer.
    """
    logger.info(f"Chat request: {request.query[:80]}... Language: {request.language}")
    try:
        lang_full = LANG_MAP.get(request.language, "English")
        result = get_answer(request.query, language=lang_full)
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            agents_used=result["agents_used"],
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


# ---------------------------------------------------------------------------
# Agents Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/agents")
async def list_agents(lang: str = Query(default="en")):
    """List all available Multi-RAG agents with their metadata."""
    agents = get_all_agents()
    return get_translated("agents", agents, lang, "AI agent names and descriptions")


# ---------------------------------------------------------------------------
# Geographic Data
# ---------------------------------------------------------------------------
@app.get("/api/geo-data")
async def geo_data():
    """Return geographic and agricultural data for supported states."""
    return {
        "Andhra Pradesh": {
            "districts": ["Guntur", "Krishna", "Prakasam", "Nellore", "Visakhapatnam", "East Godavari", "West Godavari"],
            "soils": ["Black Cotton Soil", "Red Soil", "Alluvial Soil", "Laterite"],
            "seasons": ["Kharif", "Rabi", "Zaid"],
            "major_crops": ["Paddy", "Cotton", "Chillies", "Groundnut", "Tobacco"],
        },
        "Telangana": {
            "districts": ["Hyderabad", "Warangal", "Karimnagar", "Nizamabad", "Nalgonda", "Medak", "Adilabad"],
            "soils": ["Red Soil", "Black Soil", "Alluvial", "Laterite"],
            "seasons": ["Kharif", "Rabi"],
            "major_crops": ["Cotton", "Paddy", "Maize", "Turmeric", "Soybean"],
        },
        "Tamil Nadu": {
            "districts": ["Thanjavur", "Nagapattinam", "Cuddalore", "Coimbatore", "Madurai", "Salem"],
            "soils": ["Alluvial Soil", "Red Soil", "Black Soil", "Laterite"],
            "seasons": ["Samba", "Kuruvai", "Navarai"],
            "major_crops": ["Paddy", "Sugarcane", "Cotton", "Coconut", "Groundnut"],
        },
        "Karnataka": {
            "districts": ["Dharwad", "Shimoga", "Gulbarga", "Bellary", "Mysore", "Mandya"],
            "soils": ["Red Soil", "Black Soil", "Laterite", "Alluvial"],
            "seasons": ["Kharif", "Rabi"],
            "major_crops": ["Paddy", "Jowar", "Cotton", "Groundnut", "Sugarcane"],
        },
    }


# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------
def _get_market_data():
    """Return raw market data in English."""
    return {
        "Paddy": {
            "currentRange": "₹2,100 – ₹2,450",
            "msp": 2183,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+3.2%",
        },
        "Cotton": {
            "currentRange": "₹6,800 – ₹7,500",
            "msp": 6620,
            "unit": "per Quintal",
            "demand": "Medium",
            "trend": "stable",
            "change": "+0.8%",
        },
        "Chillies": {
            "currentRange": "₹16,000 – ₹22,000",
            "msp": 7000,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+5.1%",
        },
        "Groundnut": {
            "currentRange": "₹6,500 – ₹7,200",
            "msp": 6377,
            "unit": "per Quintal",
            "demand": "Low",
            "trend": "down",
            "change": "-1.4%",
        },
        "Maize": {
            "currentRange": "₹2,100 – ₹2,350",
            "msp": 2090,
            "unit": "per Quintal",
            "demand": "Medium",
            "trend": "stable",
            "change": "+0.3%",
        },
        "Wheat": {
            "currentRange": "₹2,200 – ₹2,500",
            "msp": 2275,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+2.7%",
        },
        "Turmeric": {
            "currentRange": "₹12,000 – ₹15,500",
            "msp": None,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+8.3%",
        },
    }


@app.get("/api/market")
async def market_data(lang: str = Query(default="en")):
    """Return current market pricing data for major crops."""
    data = _get_market_data()
    return get_translated("market", data, lang, "crop market prices for farmers")


# ---------------------------------------------------------------------------
# Government Schemes
# ---------------------------------------------------------------------------
def _get_schemes_data():
    """Return raw schemes data in English."""
    return [
        {
            "name": "PM-KISAN",
            "category": "Direct Benefit",
            "description": "₹6,000/year in 3 installments directly to farmer bank accounts",
            "eligibility": "All landholding farmer families",
            "link": "https://pmkisan.gov.in",
        },
        {
            "name": "Rythu Bharosa",
            "category": "State Support",
            "description": "₹13,500/year investment support for AP farmers (includes PM-KISAN)",
            "eligibility": "All farmers in Andhra Pradesh",
            "link": "#",
        },
        {
            "name": "Rythu Bandhu",
            "category": "State Support",
            "description": "₹10,000/acre/year for Telangana farmers before each season",
            "eligibility": "All landholding farmers in Telangana",
            "link": "#",
        },
        {
            "name": "PMFBY",
            "category": "Insurance",
            "description": "Crop insurance at 2% premium (Kharif) / 1.5% (Rabi) against natural calamities",
            "eligibility": "All farmers growing notified crops",
            "link": "https://pmfby.gov.in",
        },
        {
            "name": "Kisan Credit Card",
            "category": "Credit",
            "description": "Short-term crop loans up to ₹3 lakh at 4% interest rate",
            "eligibility": "All cultivators including tenants",
            "link": "#",
        },
        {
            "name": "Soil Health Card",
            "category": "Advisory",
            "description": "Free soil testing and crop-specific fertilizer recommendations every 2 years",
            "eligibility": "All farmers, free of charge",
            "link": "#",
        },
        {
            "name": "PMKSY - Micro Irrigation",
            "category": "Subsidy",
            "description": "55% subsidy on drip and sprinkler irrigation for small farmers",
            "eligibility": "All farmers; higher subsidy for small/marginal/SC/ST",
            "link": "#",
        },
    ]


@app.get("/api/schemes")
async def schemes_data(lang: str = Query(default="en")):
    """Return list of agricultural government schemes."""
    data = _get_schemes_data()
    return get_translated("schemes", data, lang, "government agricultural schemes for farmers")


# ---------------------------------------------------------------------------
# Weather Data
# ---------------------------------------------------------------------------
@app.get("/api/weather/{state}/{city}")
async def weather_data(state: str, city: str, lang: str = Query(default="en")):
    """Return weather and risk data for a given state and city using Groq API."""
    api_key = os.getenv("GROQ_API_KEY")
    lang_full = LANG_MAP.get(lang, "English")

    fallback_data = {
        "district": city,
        "temp": "32°C", "humidity": "70%", "wind": "12 km/h",
        "condition": "Clear",
        "risk": f"No specific real-time data available for {city}, {state}. General conditions favorable.",
        "advisory": "Monitor local weather updates from IMD.",
        "forecast": ["32°C / Clear", "31°C / Partly Cloudy", "30°C / Cloudy", "30°C / Rain", "31°C / Sunny"],
        "suggested_crops": ["Paddy", "Maize", "Cotton"]
    }

    if not api_key:
        logger.warning("GROQ_API_KEY not set. Returning fallback weather data.")
        if lang != "en":
            return get_translated(f"weather_fallback_{city}", fallback_data, lang, "weather advisory for farmers")
        return fallback_data

    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_api_key=api_key,
            temperature=0.3,
        )

        lang_instruction = ""
        if lang != "en":
            lang_instruction = f"\nIMPORTANT: ALL string values in the JSON must be written in {lang_full} language. Keep numbers, units (°C, km/h, %), and JSON keys in English."

        prompt = f"""You are an agricultural meteorologist. Generate a realistic 5-day weather forecast for {city}, {state}, India, typical for the current season. 
Output ONLY valid JSON with no markdown formatting or extra text.{lang_instruction}

Required JSON structure:
{{
  "temp": "string (e.g., '32°C')",
  "humidity": "string (e.g., '70%')",
  "wind": "string (e.g., '12 km/h')",
  "condition": "string (e.g., 'Partly Cloudy')",
  "risk": "string (brief sentence about weather risks to crops)",
  "advisory": "string (brief advisory for farmers based on the weather)",
  "forecast": ["string", "string", "string", "string", "string"],
  "suggested_crops": ["Crop Name 1", "Crop Name 2", "Crop Name 3"]
}}"""
        response = llm.invoke(prompt)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        data["district"] = city
        return data
        
    except Exception as e:
        logger.error(f"Weather Groq API error: {e}", exc_info=True)
        return fallback_data


# ---------------------------------------------------------------------------
# Leaf Scan (Groq Vision)
# ---------------------------------------------------------------------------
@app.post("/api/scan")
async def scan_endpoint(file: UploadFile = File(...), lang: str = Query(default="en")):
    """Analyze uploaded leaf image using Groq Vision model and return diagnosis and remedies."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set. Returning mock scan results.")
        mock_data = {
            "disease": "Rice Blast (Magnaporthe oryzae) [Demo]",
            "confidence": 87,
            "severity": "Medium",
            "affected_area": "~30% of leaf surface",
            "recommendations": [
                "Demo Mode: Please set GROQ_API_KEY for real analysis.",
                "Spray Tricyclazole 75% WP @ 0.6g/L water immediately",
                "Reduce nitrogen fertilizer application",
                "Improve field drainage to reduce humidity",
            ],
            "preventive_measures": [
                "Use blast-resistant varieties (BPT-5204, MTU-1010)",
                "Maintain recommended plant spacing",
            ]
        }
        return {"analysis": get_translated("mock_scan", mock_data, lang, "leaf disease analysis")}

    try:
        # Read file contents and encode to base64
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
            
        import base64
        encoded = base64.b64encode(contents).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"
        
        # Prepare LangChain components
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage
        
        # Use meta-llama/llama-4-scout-17b-16e-instruct for multimodal tasks
        llm = ChatGroq(
            model_name="meta-llama/llama-4-scout-17b-16e-instruct",
            groq_api_key=api_key,
            temperature=0.2,
        )
        
        prompt = """You are an expert plant pathologist specializing in crop disease diagnosis.
Analyze this crop leaf image and identify if there is any disease, pest infestation, or nutrient deficiency.
Provide a detailed analysis in valid JSON format.
Your analysis must strictly follow this JSON schema:
{
  "disease": "Name of the disease, pest, deficiency, or 'Healthy' if no issues found. Include scientific name in parentheses if applicable.",
  "confidence": 80, // integer between 0 and 100 representing confidence level
  "severity": "High", // 'High', 'Medium', 'Low', or 'None'
  "affected_area": "~30% of leaf surface", // estimated percentage or description of affected area, or 'None'
  "recommendations": ["treatment recommendation 1", "treatment recommendation 2"], // 3-4 specific treatment recommendations (chemical, organic, cultural remedies)
  "preventive_measures": ["preventive measure 1", "preventive measure 2"] // 2-3 preventive measures to avoid recurrence
}

Output ONLY valid JSON, with no markdown code blocks or extra text."""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                },
            ]
        )
        
        logger.info(f"Sending leaf scan request ({file.filename}) to Groq Vision model...")
        response = llm.invoke([message])
        content = response.content.strip()
        
        # Clean up JSON formatting if LLM wrapped it in markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            analysis_data = json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse LLM scan response as JSON. Content: {content}. Error: {e}")
            raise HTTPException(status_code=500, detail="Invalid analysis output format from AI model.")

        # Translate output to the requested language
        translated_analysis = get_translated(f"scan_{file.filename}", analysis_data, lang, "leaf disease analysis and remedies")
        return {"analysis": translated_analysis}

    except Exception as e:
        logger.error(f"Leaf scan analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Leaf scan analysis failed: {str(e)}")


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "system": "AgriMitra Multi-RAG",
        "agents_available": len(get_all_agents()),
    }


# ---------------------------------------------------------------------------
# Serve static files (React build) in production
# ---------------------------------------------------------------------------
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
