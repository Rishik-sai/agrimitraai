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
from typing import Optional

from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import structlog
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Load environment variables
load_dotenv()

REDIS_CLIENT = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global REDIS_CLIENT
    try:
        import redis.asyncio as redis_async
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        REDIS_CLIENT = redis_async.from_url(redis_url, decode_responses=True)
        await REDIS_CLIENT.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}. Caching disabled.")
        REDIS_CLIENT = None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_key_here":
        logger.error("GROQ_API_KEY environment variable is not set. Failing fast.")
        raise RuntimeError("GROQ_API_KEY environment variable is missing.")
    yield
    if REDIS_CLIENT:
        await REDIS_CLIENT.aclose()

# Configure logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger(__name__)

# Import the Multi-RAG engine
from multi_rag import get_all_agents, stream_answer

app = FastAPI(
    title="AgriMitra AI Pro",
    description="Multi-RAG Agricultural Intelligence System",
    version="2.0.0",
    lifespan=lifespan,
)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIdMiddleware)
Instrumentator().instrument(app).expose(app)

# CORS for local development
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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

        start_time = time.time()
        response = llm.invoke(prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("LLM call completed", llm_node="translation", latency_ms=latency_ms)
        
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
    session_id: Optional[str] = Field(default=None, description="Session UUID for conversation memory")


class ChatResponse(BaseModel):
    answer: str
    sources: list
    agents_used: list


from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# Chat Endpoint (Multi-RAG with Streaming)
# ---------------------------------------------------------------------------
@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    """Handle a chat query using the Multi-RAG pipeline.
    Routes the query to specialized agents, retrieves context (and live web search),
    and streams the synthesized answer via Server-Sent Events (SSE).
    """
    logger.info(f"Chat request: {chat_request.query[:80]}... Language: {chat_request.language} Session: {chat_request.session_id}")
    try:
        lang_full = LANG_MAP.get(chat_request.language, "English")
        
        return StreamingResponse(
            stream_answer(chat_request.query, language=lang_full, session_id=chat_request.session_id),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Chat streaming error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


# ---------------------------------------------------------------------------
# Audio Transcription (Whisper API)
# ---------------------------------------------------------------------------
@app.post("/api/transcribe")
@limiter.limit("10/minute")
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    """Transcribe audio using Groq's Whisper API."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
        
    try:
        contents = await file.read()
        import httpx
        
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        files = {
            "file": (file.filename or "audio.webm", contents, file.content_type or "audio/webm")
        }
        data = {
            "model": "whisper-large-v3",
            "response_format": "json"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, files=files, data=data, timeout=30.0)
            
        if resp.status_code != 200:
            logger.error(f"Groq Whisper API error: {resp.text}")
            raise HTTPException(status_code=500, detail="Failed to transcribe audio.")
            
        result = resp.json()
        return {"text": result.get("text", "")}
        
    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
async def _get_market_data():
    """Fetch live mandi prices from data.gov.in Agmarknet API or via scraping."""
    import httpx
    api_key = os.getenv("DATAGOV_API_KEY")
    
    if api_key:
        try:
            url = f"https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key={api_key}&format=json&limit=50"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                # Map real API data to our format
                data = response.json()
                records = data.get("records", [])
                if records:
                    results = []
                    for rec in records[:10]:
                        crop = rec.get("commodity", "Unknown").title()
                        min_price = rec.get("min_price", 0)
                        max_price = rec.get("max_price", 0)
                        results.append({
                            "crop": crop,
                            "currentRange": f"₹{min_price} – ₹{max_price}",
                            "msp": None,
                            "unit": "per Quintal",
                            "demand": "Unknown",
                            "trend": "stable",
                            "change": "0%",
                        })
                    return results
        except Exception as e:
            logger.error(f"Failed to fetch real market data API: {e}")

    # Scraper fallback attempt
    try:
        url = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                logger.info("Agmarknet simple scraper fetched page successfully, but needs POST data for actual tables. Using fallback.")
    except Exception as e:
        logger.warning(f"Agmarknet scraper attempt failed: {e}")

    logger.info("Returning fallback mock market data.")
    return [
        {
            "crop": "Paddy",
            "currentRange": "₹2,100 – ₹2,450",
            "msp": 2183,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+3.2%",
        },
        {
            "crop": "Cotton",
            "currentRange": "₹6,800 – ₹7,500",
            "msp": 6620,
            "unit": "per Quintal",
            "demand": "Medium",
            "trend": "stable",
            "change": "+0.8%",
        },
        {
            "crop": "Chillies",
            "currentRange": "₹16,000 – ₹22,000",
            "msp": 7000,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+5.1%",
        },
        {
            "crop": "Groundnut",
            "currentRange": "₹6,500 – ₹7,200",
            "msp": 6377,
            "unit": "per Quintal",
            "demand": "Low",
            "trend": "down",
            "change": "-1.4%",
        },
        {
            "crop": "Maize",
            "currentRange": "₹2,100 – ₹2,350",
            "msp": 2090,
            "unit": "per Quintal",
            "demand": "Medium",
            "trend": "stable",
            "change": "+0.3%",
        },
        {
            "crop": "Wheat",
            "currentRange": "₹2,200 – ₹2,500",
            "msp": 2275,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+2.7%",
        },
        {
            "crop": "Turmeric",
            "currentRange": "₹12,000 – ₹15,500",
            "msp": None,
            "unit": "per Quintal",
            "demand": "High",
            "trend": "up",
            "change": "+8.3%",
        },
    ]


@app.get("/api/market")
async def market_data(lang: str = Query(default="en")):
    """Return current market pricing data for major crops with Redis caching."""
    cache_key = "market_data_raw"
    raw_data = None
    
    if REDIS_CLIENT:
        try:
            cached_json = await REDIS_CLIENT.get(cache_key)
            if cached_json:
                raw_data = json.loads(cached_json)
                logger.info("Market data loaded from Redis cache")
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    if not raw_data:
        logger.info("Fetching fresh market data...")
        raw_data = await _get_market_data()
        
        if REDIS_CLIENT:
            try:
                await REDIS_CLIENT.set(cache_key, json.dumps(raw_data), ex=3600)  # 1 hour cache
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

    return get_translated("market", raw_data, lang, "crop market prices for farmers")


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
    """Return weather and risk data for a given state and city using OpenWeatherMap and Groq API."""
    import httpx
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    owm_api_key = os.getenv("OPENWEATHER_API_KEY")
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

    if not owm_api_key:
        logger.warning("OPENWEATHER_API_KEY not set. Returning fallback weather data.")
        if lang != "en":
            return get_translated(f"weather_fallback_{city}", fallback_data, lang, "weather advisory for farmers")
        return fallback_data

    # Fetch real data from OpenWeatherMap
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city},{state},IN&appid={owm_api_key}&units=metric"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            
        if response.status_code != 200:
            # Fallback to just city and IN if state+city fails
            url = f"https://api.openweathermap.org/data/2.5/forecast?q={city},IN&appid={owm_api_key}&units=metric"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                
        if response.status_code != 200:
            logger.error(f"OpenWeatherMap API error: {response.text}")
            return fallback_data

        owm_data = response.json()
        current = owm_data["list"][0]
        
        temp = f"{round(current['main']['temp'])}°C"
        humidity = f"{current['main']['humidity']}%"
        wind = f"{round(current['wind']['speed'] * 3.6)} km/h"
        condition = current['weather'][0]['description'].title()
        
        # Get 5 day forecast (every 24 hours / 8 indices)
        forecast_list = []
        for i in range(0, 40, 8):
            if i < len(owm_data["list"]):
                f = owm_data["list"][i]
                forecast_list.append(f"{round(f['main']['temp'])}°C / {f['weather'][0]['description'].title()}")

        base_weather = {
            "district": city,
            "temp": temp,
            "humidity": humidity,
            "wind": wind,
            "condition": condition,
            "forecast": forecast_list
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch from OpenWeatherMap: {e}")
        return fallback_data

    # Now use LLM to generate agricultural advisory based on REAL weather
    if not groq_api_key:
        logger.warning("GROQ_API_KEY not set. Returning generic advisory.")
        base_weather["risk"] = fallback_data["risk"]
        base_weather["advisory"] = fallback_data["advisory"]
        base_weather["suggested_crops"] = fallback_data["suggested_crops"]
        if lang != "en":
            return get_translated(f"weather_real_{city}", base_weather, lang, "weather advisory for farmers")
        return base_weather

    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_api_key=groq_api_key,
            temperature=0.3,
        )

        lang_instruction = ""
        if lang != "en":
            lang_instruction = f"\nIMPORTANT: ALL string values in the JSON must be written in {lang_full} language. Keep JSON keys in English."

        prompt = f"""You are an agricultural meteorologist. I have the actual real-time weather forecast for {city}, {state}, India:
Temperature: {temp}
Humidity: {humidity}
Wind: {wind}
Condition: {condition}
5-Day Forecast: {', '.join(forecast_list)}

Based on this REAL data, provide an agricultural risk assessment, farmer advisory, and suggested crops.
Output ONLY valid JSON with no markdown formatting or extra text.{lang_instruction}

Required JSON structure:
{{
  "risk": "string (brief sentence about weather risks to crops based on the provided weather)",
  "advisory": "string (brief advisory for farmers based on the provided weather)",
  "suggested_crops": ["Crop Name 1", "Crop Name 2", "Crop Name 3"]
}}"""
        start_time = time.time()
        response = llm.invoke(prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("LLM call completed", llm_node="weather_advisory", latency_ms=latency_ms)
        
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        llm_data = json.loads(content)
        base_weather.update(llm_data)
        return base_weather
        
    except Exception as e:
        logger.error(f"Weather advisory Groq API error: {e}", exc_info=True)
        base_weather["risk"] = fallback_data["risk"]
        base_weather["advisory"] = fallback_data["advisory"]
        base_weather["suggested_crops"] = fallback_data["suggested_crops"]
        return base_weather


# ---------------------------------------------------------------------------
# Leaf Scan (Groq Vision)
# ---------------------------------------------------------------------------
@app.post("/api/scan")
@limiter.limit("5/minute")
async def scan_endpoint(request: Request, file: UploadFile = File(...), lang: str = Query(default="en")):
    """Analyze uploaded leaf image using Groq Vision model and return diagnosis and remedies."""
    # 6. File type validation
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, and WebP are allowed.")
        
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
            
        # 7. File size limit (10MB)
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
            
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
        start_time = time.time()
        response = llm.invoke([message])
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("LLM call completed", llm_node="leaf_scan", latency_ms=latency_ms)
        
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
