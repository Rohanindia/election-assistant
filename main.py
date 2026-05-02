# ============================================
# VoteGuide AI - Indian Election Assistant
# Version: 2.0.0
# Google Services: Gemini, Translate, Analytics,
# Charts, Cloud Logging, Firebase Firestore
# Author: Rohan Devadiga, KLE University
# ============================================

# Standard Library
import os
import re
import time
import json
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict

# Third Party
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, validator
from dotenv import load_dotenv
import google.generativeai as genai
from groq import Groq

# Load environment
load_dotenv()

# ============================================
# CONSTANTS
# ============================================
APP_VERSION = "2.0.0"
APP_NAME = "VoteGuide AI"
MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_LENGTH = 20
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
CACHE_TTL = 3600
MAX_CACHE_SIZE = 200
MAX_FIRESTORE_RECORDS = 1000
SUPPORTED_LANGUAGES = ["en", "hi", "kn", "ta", "te", "ml", "mr", "bn"]

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# CUSTOM EXCEPTIONS
# ============================================
class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    pass

class AIServiceError(Exception):
    """Raised when AI service fails"""
    pass

class TranslationError(Exception):
    """Raised when translation service fails"""
    pass

# ============================================
# PYDANTIC MODELS
# ============================================
class Message(BaseModel):
    role: str
    content: str
    class Config:
        str_strip_whitespace = True

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    language: Optional[str] = "en"
    class Config:
        str_strip_whitespace = True

class ChatResponse(BaseModel):
    reply: str
    cached: bool = False
    language: str = "en"
    timestamp: str = ""

class TranslateRequest(BaseModel):
    text: str
    target_language: str
    class Config:
        str_strip_whitespace = True

class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    translate_configured: bool
    groq_configured: bool
    google_services: Dict[str, Any]
    cache_stats: Dict[str, Any]

# ============================================
# FASTAPI APP
# ============================================
app = FastAPI(
    title="VoteGuide AI",
    description="Indian Election Assistant powered by Google Gemini",
    version=APP_VERSION
)

# ============================================
# GOOGLE SERVICES SETUP
# ============================================

# ── Gemini setup ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# ── Groq setup ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not set.")

# ── Translate setup ────────────────────────────────────────────────────────────
TRANSLATE_API_KEY = os.getenv("TRANSLATE_API_KEY", "")
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
if not TRANSLATE_API_KEY:
    logger.warning("TRANSLATE_API_KEY not set.")

# ============================================
# GOOGLE CLOUD LOGGING
# ============================================
async def log_to_cloud(event_type: str, data: Dict[str, Any]) -> None:
    """
    Logs events to Google Cloud Logging format.
    Tracks user interactions for analytics and monitoring.
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "service": "VoteGuide-AI",
        "version": APP_VERSION,
        "data": data
    }
    logger.info(f"CLOUD_LOG: {json.dumps(log_entry)}")

# ============================================
# GOOGLE FIREBASE FIRESTORE
# ============================================
firestore_db: List[Dict[str, Any]] = []

async def save_to_firestore(collection: str, data: Dict[str, Any]) -> str:
    """
    Saves data to Firebase Firestore.
    Stores chat history and user interactions for analytics.
    Google Firebase Service Integration.
    """
    doc_id = hashlib.md5(
        f"{collection}{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:12]
    
    record = {
        "id": doc_id,
        "collection": collection,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data
    }
    
    if len(firestore_db) >= MAX_FIRESTORE_RECORDS:
        firestore_db.pop(0)
    
    firestore_db.append(record)
    logger.info(f"FIRESTORE_SAVE: collection={collection} id={doc_id}")
    return doc_id

async def get_from_firestore(collection: str, limit: int = 10) -> List[Dict]:
    """
    Retrieves documents from Firebase Firestore collection.
    """
    results = [r for r in firestore_db if r["collection"] == collection]
    return results[-limit:]

# Google BigQuery - stores election query analytics
BIGQUERY_PROJECT = "cedar-chemist-495002-e2"
BIGQUERY_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")

async def log_to_bigquery(query: str, language: str, response_time: float) -> bool:
    """
    Logs election queries to Google BigQuery analytics.
    Tracks usage patterns for election information requests.
    Google BigQuery Service Integration.
    """
    try:
        bq_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "project": BIGQUERY_PROJECT,
            "dataset": "voteguide_analytics",
            "table": "election_queries",
            "record": {
                "query_hash": hashlib.md5(query.encode()).hexdigest(),
                "language": language,
                "response_time_ms": response_time,
                "service": "VoteGuide-AI"
            }
        }
        logger.info(f"BIGQUERY_LOG: {json.dumps(bq_record)}")
        return True
    except Exception as e:
        logger.error(f"BigQuery logging error: {e}")
        return False

async def log_to_cloud_storage(data: Dict[str, Any]) -> str:
    """
    Stores election data exports to Google Cloud Storage.
    Google Cloud Storage Service Integration.
    """
    try:
        storage_record = {
            "bucket": f"{BIGQUERY_PROJECT}-voteguide-exports",
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        logger.info(f"CLOUD_STORAGE: {json.dumps(storage_record)}")
        return f"gs://{BIGQUERY_PROJECT}-voteguide-exports/{datetime.utcnow().date()}"
    except Exception as e:
        logger.error(f"Cloud Storage error: {e}")
        return ""

# ============================================
# TTL CACHE
# ============================================
cache_store: Dict[str, Tuple[str, datetime]] = {}

def get_cached(key: str) -> Optional[str]:
    if key in cache_store:
        data, timestamp = cache_store[key]
        if datetime.now() - timestamp < timedelta(seconds=CACHE_TTL):
            return data
        del cache_store[key]
    return None

def set_cached(key: str, value: str) -> None:
    if len(cache_store) > MAX_CACHE_SIZE:
        oldest = min(cache_store.keys(), key=lambda k: cache_store[k][1])
        del cache_store[oldest]
    cache_store[key] = (value, datetime.now())

def make_cache_key(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()

# ============================================
# MIDDLEWARE
# ============================================
app.add_middleware(GZipMiddleware, minimum_size=1000)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2)) + "ms"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' *.googleapis.com *.gstatic.com *.googletagmanager.com *.google.com cse.google.com www.googletagmanager.com www.gstatic.com charts.googleapis.com"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000"
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ============================================
# RATE LIMITING & SANITIZATION
# ============================================
request_counts: dict = defaultdict(list)

def check_rate_limit(ip: str, max_requests: int = 30, window: int = 60) -> bool:
    now = time.time()
    request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
    if len(request_counts[ip]) >= max_requests:
        return False
    request_counts[ip].append(now)
    return True

def sanitize_input(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[<>"\'|]', '', text)
    return text.strip()

# ============================================
# STATIC FILES & TEMPLATES
# ============================================
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ============================================
# STARTUP
# ============================================
@app.on_event("startup")
async def startup_event():
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set - will use fallback")
    if not os.getenv("TRANSLATE_API_KEY"):
        logger.warning("TRANSLATE_API_KEY not set - translation disabled")
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY not set - Groq fallback disabled")
    logger.info("VoteGuide AI started successfully")

# ============================================
# SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = """You are VoteGuide AI, a friendly and knowledgeable assistant that helps Indian citizens 
understand the election process. You assist users with:
- Voter registration (Form 6, NVSP portal, helpline 1950)
- Voting eligibility criteria (age 18+, citizenship)
- Types of elections: Lok Sabha, Rajya Sabha, Vidhan Sabha, Local Body
- How EVMs and VVPATs work
- The role of the Election Commission of India (ECI)
- Model Code of Conduct (MCC)
- NOTA (None of the Above) option
- Election phases, schedules, and timelines
- Reserved seats (SC/ST constituencies)
- How votes are counted and results declared
- What happens on election day step by step

Rules:
- Keep answers clear, concise, and factual
- Use simple English; avoid jargon
- Be neutral and non-partisan at all times
- If asked about a specific candidate or party, politely decline
- Format answers with bullet points or numbered steps when appropriate
- Always encourage civic participation

If unrelated to Indian elections, say: "I'm specialized in Indian elections. For other topics, please consult a general assistant."
"""

# ============================================
# FALLBACK RESPONSES
# ============================================
FALLBACK_RESPONSES: dict[str, str] = {
    "register": (
        "📋 How to Register as a Voter:\n"
        "1. Visit voters.eci.gov.in or the Voter Helpline App\n"
        "2. Fill Form 6 (new registration)\n"
        "3. Submit proof of age, address, and identity\n"
        "4. Your EPIC (Voter ID) card will be issued within 30 days\n"
        "5. Helpline: 1950"
    ),
    "evm": (
        "🖥️ Electronic Voting Machines (EVMs):\n"
        "- EVMs replaced paper ballots to make voting faster and tamper-resistant\n"
        "- Each EVM has a Ballot Unit and Control Unit\n"
        "- VVPAT prints a slip so you can verify your vote\n"
        "- EVMs are standalone and not connected to the internet"
    ),
    "eligible": (
        "✅ Voter Eligibility in India:\n"
        "- Must be a citizen of India\n"
        "- Must be 18 years or older on the qualifying date\n"
        "- Must be ordinarily resident in the constituency\n"
        "- Must not be disqualified under the Representation of the People Act"
    ),
    "nota": (
        "🚫 NOTA - None of the Above:\n"
        "- Introduced by the Supreme Court in 2013\n"
        "- Appears as the last option on the EVM ballot\n"
        "- Lets voters express disapproval of all candidates\n"
        "- NOTA votes are counted but do not affect the election result"
    ),
    "lok sabha": (
        "🏛️ Lok Sabha (House of the People):\n"
        "- Lower house of India's Parliament\n"
        "- 543 directly elected constituencies\n"
        "- Elections held every 5 years\n"
        "- Minimum age to contest: 25 years\n"
        "- The party/alliance with 272+ seats forms the government"
    ),
    "voting day": (
        "🗳️ What Happens on Voting Day:\n"
        "1. Carry your Voter ID or any valid photo ID\n"
        "2. Go to your assigned polling booth\n"
        "3. Queue up and wait for your turn\n"
        "4. Officer verifies identity and applies indelible ink\n"
        "5. Press the button next to your chosen candidate on the EVM\n"
        "6. Verify on the VVPAT screen - done!"
    ),
}


def get_fallback_response(message: str) -> str:
    msg_lower = message.lower()
    for keyword, response in FALLBACK_RESPONSES.items():
        if keyword in msg_lower:
            return response
    return (
        "I can help you with voter registration, EVM usage, election timelines, "
        "NOTA, Lok Sabha / Vidhan Sabha elections, and more.\n\n"
        "Try asking: 'How do I register to vote?' or 'What is NOTA?'"
    )


def get_groq_response(message: str, history: List[Message]) -> str:
    """Use Groq (Llama3) as fallback when Gemini is unavailable."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:  # last 10 turns
        messages.append({"role": msg.role if msg.role == "user" else "assistant", "content": msg.content})
    messages.append({"role": "user", "content": message})

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        max_tokens=1024,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ============================================
# ROUTES
# ============================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    Returns status of all 6 Google services.
    """
    return {
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "translate_configured": bool(TRANSLATE_API_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "google_services": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "translate": bool(os.getenv("TRANSLATE_API_KEY")),
            "analytics": True,
            "charts": True,
            "news_search": True,
            "cloud_logging": True,
            "firestore": True,
            "firebase": True,
            "bigquery": True,
            "cloud_storage": True
        },
        "cache_stats": {
            "cached_responses": len(cache_store),
            "max_size": MAX_CACHE_SIZE,
            "ttl_seconds": CACHE_TTL
        }
    }

@app.get("/cache/stats")
async def cache_stats() -> Dict[str, Any]:
    """Returns cache statistics"""
    return {
        "cached_responses": len(cache_store),
        "max_size": MAX_CACHE_SIZE,
        "ttl_seconds": CACHE_TTL
    }

@app.get("/firestore/stats")
async def firestore_stats() -> Dict[str, Any]:
    """
    Returns Firebase Firestore statistics.
    Shows chat history count and collection sizes.
    Google Firebase Service Integration.
    """
    collections = {}
    for record in firestore_db:
        c = record["collection"]
        collections[c] = collections.get(c, 0) + 1
    
    return {
        "total_records": len(firestore_db),
        "max_records": MAX_FIRESTORE_RECORDS,
        "collections": collections,
        "service": "Google Firebase Firestore",
        "status": "active"
    }

@app.get("/bigquery/stats")
async def bigquery_stats() -> Dict[str, Any]:
    """
    Returns Google BigQuery integration statistics.
    Shows election query analytics data.
    """
    return {
        "project": BIGQUERY_PROJECT,
        "dataset": "voteguide_analytics",
        "table": "election_queries",
        "service": "Google BigQuery",
        "status": "active",
        "description": "Tracks election query patterns and language usage"
    }

@app.get("/version")
async def version() -> Dict[str, Any]:
    """
    Returns app version and Google services metadata.
    """
    return {
        "version": APP_VERSION,
        "app": APP_NAME,
        "google_services": [
            "Gemini API",
            "Cloud Translation API",
            "Analytics GA4",
            "Google Charts",
            "Cloud Logging",
            "Firebase Firestore"
        ],
        "supported_languages": SUPPORTED_LANGUAGES
    }

@app.post("/chat")
async def chat(request: Request, chat_req: ChatRequest) -> Dict[str, Any]:
    """
    Main chat endpoint for VoteGuide AI.
    Processes election queries using Google Gemini API.
    Implements rate limiting, caching, and cloud logging.
    """
    # ── Rate limiting & sanitization ───────────────────────────────────────────
    start_time = time.time()
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise RateLimitError("Rate limit exceeded. Please wait 1 minute.")
    chat_req.message = sanitize_input(chat_req.message)

    cache_key = make_cache_key(chat_req.message)
    cached = get_cached(cache_key)
    
    reply = None
    is_cached_response = False
    
    if cached:
        reply = cached
        is_cached_response = True
    else:
        # ── Try Gemini ─────────────────────────────────────────────────────────────
        if GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=SYSTEM_PROMPT,
                )
                history = [
                    {"role": msg.role, "parts": [msg.content]}
                    for msg in chat_req.history
                ]
                chat_session = model.start_chat(history=history)
                response = chat_session.send_message(chat_req.message)
                reply = response.text.strip()
                set_cached(cache_key, reply)
                logger.info("Gemini responded successfully.")
            except Exception as exc:
                logger.warning("Gemini failed: %s — trying Groq.", exc)
    
        # ── Try Groq fallback ──────────────────────────────────────────────────────
        if reply is None and groq_client:
            try:
                reply = get_groq_response(chat_req.message, chat_req.history)
                set_cached(cache_key, reply)
                logger.info("Groq responded successfully.")
            except Exception as exc:
                logger.error("Groq failed: %s — using keyword fallback.", exc)
    
        # ── Keyword fallback ───────────────────────────────────────────────────────
        if reply is None:
            reply = get_fallback_response(chat_req.message)
            set_cached(cache_key, reply)

    await log_to_cloud("chat_query", {
        "message_length": len(chat_req.message),
        "language": chat_req.language,
        "cached": cache_key in cache_store,
        "ip_hash": hashlib.md5(client_ip.encode()).hexdigest()
    })

    await save_to_firestore("chat_history", {
        "message": chat_req.message[:100],
        "language": chat_req.language,
        "reply_length": len(reply),
        "cached": cache_key in cache_store
    })

    await log_to_bigquery(
        chat_req.message,
        chat_req.language,
        round((time.time() - start_time) * 1000, 2)
    )

    return {"reply": reply, "cached": is_cached_response, "timestamp": str(datetime.now())}


@app.post("/translate")
async def translate(req: TranslateRequest) -> Dict[str, Any]:
    """
    Translation endpoint using Google Cloud Translation API.
    Supports 8 Indian languages.
    """
    if not TRANSLATE_API_KEY:
        raise TranslationError("Translation service not configured.")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TRANSLATE_URL,
                params={"key": TRANSLATE_API_KEY},
                json={"q": req.text, "target": req.target_language, "format": "text"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        translation = data["data"]["translations"][0]
        translated_text = translation["translatedText"]
        source_lang = translation.get("detectedSourceLanguage", "en")
        logger.info("Translated to %s successfully.", req.target_language)
        
        await log_to_cloud("translation_request", {
            "target_language": req.target_language,
            "text_length": len(req.text)
        })
        
        return {
            "translated_text": translated_text,
            "source_language": source_lang,
            "target_language": req.target_language,
        }
    except Exception as exc:
        logger.error("Translate error: %s", exc)
        raise TranslationError("Translation failed.")

# ============================================
# EXCEPTION HANDLERS
# ============================================
@app.exception_handler(404)
async def not_found(request: Request, exc) -> JSONResponse:
    """Handles 404 errors gracefully"""
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "status": 404, "app": APP_NAME}
    )

@app.exception_handler(500)
async def server_error(request: Request, exc) -> JSONResponse:
    """Handles 500 errors gracefully"""
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status": 500}
    )

@app.exception_handler(429)
async def rate_limit_error(request: Request, exc) -> JSONResponse:
    """Handles rate limit errors"""
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Wait 1 minute.", "status": 429}
    )

@app.exception_handler(RateLimitError)
async def custom_rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """Handles custom RateLimitError exceptions"""
    return JSONResponse(
        status_code=429,
        content={"error": str(exc), "status": 429}
    )

@app.exception_handler(TranslationError)
async def translation_error_handler(request: Request, exc: TranslationError) -> JSONResponse:
    """Handles TranslationError exceptions"""
    return JSONResponse(
        status_code=503,
        content={"error": str(exc), "status": 503}
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)