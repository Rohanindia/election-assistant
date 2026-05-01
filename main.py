"""
India Election Assistant - FastAPI Backend
AI-powered assistant using Google Gemini API + Google Cloud Translation API
Fallback: Groq (Llama3) when Gemini quota is exceeded
Challenge 2: Election Process Assistant
"""

import os
import re
import time
import logging
import httpx
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)

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

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="India Election Assistant",
    description="AI-powered assistant to help users understand Indian elections",
    version="1.0.0",
)

# ── Security Headers Middleware ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' *.googleapis.com *.gstatic.com *.googletagmanager.com *.google.com cse.google.com www.googletagmanager.com www.gstatic.com charts.googleapis.com"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
request_counts: dict = defaultdict(list)

def check_rate_limit(ip: str, max_requests: int = 30, window: int = 60) -> bool:
    now = time.time()
    request_counts[ip] = [t for t in request_counts[ip] if now - t < window]
    if len(request_counts[ip]) >= max_requests:
        return False
    request_counts[ip].append(now)
    return True

# ── Input Sanitization ─────────────────────────────────────────────────────────
def sanitize_input(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[<>"\'|]', '', text)
    return text.strip()

# ── Startup Validation ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set - will use fallback")
    if not os.getenv("TRANSLATE_API_KEY"):
        logger.warning("TRANSLATE_API_KEY not set - translation disabled")
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY not set - Groq fallback disabled")
    logger.info("VoteGuide AI started successfully")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Models ─────────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty.")
        if len(v) > 1000:
            raise ValueError("Message too long (max 1000 characters).")
        return v

class TranslateRequest(BaseModel):
    text: str
    target_language: str

    @field_validator("target_language")
    @classmethod
    def valid_language(cls, v: str) -> str:
        allowed = {"en", "hi", "kn", "ta", "te", "ml"}
        if v not in allowed:
            raise ValueError(f"Language must be one of {allowed}")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Text cannot be empty.")
        if len(v) > 5000:
            raise ValueError("Text too long (max 5000 characters).")
        return v

class ChatResponse(BaseModel):
    reply: str
    source: str

class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str


# ── Fallback keyword responses ─────────────────────────────────────────────────
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


def get_groq_response(message: str, history: list[ChatMessage]) -> str:
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


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "translate_configured": bool(TRANSLATE_API_KEY),
        "google_services": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "translate": bool(os.getenv("TRANSLATE_API_KEY")),
            "analytics": True,
            "charts": True,
            "custom_search": True
        }
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, payload: ChatRequest):
    """
    1. Try Gemini first
    2. If Gemini quota exceeded → fallback to Groq
    3. If both fail → keyword fallback
    """
    # ── Rate limiting & sanitization ───────────────────────────────────────────
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 1 minute.")
    payload.message = sanitize_input(payload.message)
    # ── Try Gemini ─────────────────────────────────────────────────────────────
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=SYSTEM_PROMPT,
            )
            history = [
                {"role": msg.role, "parts": [msg.content]}
                for msg in payload.history
            ]
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(payload.message)
            reply = response.text.strip()
            logger.info("Gemini responded successfully.")
            return ChatResponse(reply=reply, source="gemini")
        except Exception as exc:
            logger.warning("Gemini failed: %s — trying Groq.", exc)

    # ── Try Groq fallback ──────────────────────────────────────────────────────
    if groq_client:
        try:
            reply = get_groq_response(payload.message, payload.history)
            logger.info("Groq responded successfully.")
            return ChatResponse(reply=reply, source="groq")
        except Exception as exc:
            logger.error("Groq failed: %s — using keyword fallback.", exc)

    # ── Keyword fallback ───────────────────────────────────────────────────────
    return ChatResponse(reply=get_fallback_response(payload.message), source="fallback")


@app.post("/translate", response_model=TranslateResponse)
async def translate(payload: TranslateRequest):
    """Translate text using Google Cloud Translation API."""
    if not TRANSLATE_API_KEY:
        raise HTTPException(status_code=503, detail="Translation service not configured.")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TRANSLATE_URL,
                params={"key": TRANSLATE_API_KEY},
                json={"q": payload.text, "target": payload.target_language, "format": "text"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        translation = data["data"]["translations"][0]
        translated_text = translation["translatedText"]
        source_lang = translation.get("detectedSourceLanguage", "en")
        logger.info("Translated to %s successfully.", payload.target_language)
        return TranslateResponse(
            translated_text=translated_text,
            source_language=source_lang,
            target_language=payload.target_language,
        )
    except Exception as exc:
        logger.error("Translate error: %s", exc)
        raise HTTPException(status_code=500, detail="Translation failed.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)