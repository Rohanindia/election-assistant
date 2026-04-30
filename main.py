"""
India Election Assistant - FastAPI Backend
AI-powered assistant using Google Gemini API
Challenge 2: Election Process Assistant
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")
logger = logging.getLogger(__name__)

# ── Gemini setup ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set – AI responses will be unavailable.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """You are VoteGuide AI, a friendly and knowledgeable assistant that helps Indian citizens 
understand the election process. You assist users with:

- Voter registration (how to register, Form 6, NVSP portal, helpline 1950)
- Voting eligibility criteria (age 18+, citizenship, etc.)
- Types of elections: Lok Sabha (General), Rajya Sabha, Vidhan Sabha (State), Local Body
- How EVMs (Electronic Voting Machines) and VVPATs work
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
- If asked about a specific candidate or party, politely decline and redirect to process-based info
- Format answers with bullet points or numbered steps when appropriate
- Always encourage civic participation

If a question is unrelated to Indian elections, politely say: 
"I'm specialized in Indian elections. For other topics, please consult a general assistant."
"""

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="India Election Assistant",
    description="AI-powered assistant to help users understand Indian elections",
    version="1.0.0",
)

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
    role: str       # "user" or "model"
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


class ChatResponse(BaseModel):
    reply: str
    source: str  # "gemini" | "fallback"


# ── Fallback keyword responses ─────────────────────────────────────────────────
FALLBACK_RESPONSES: dict[str, str] = {
    "register": (
        "📋 **How to Register as a Voter:**\n"
        "1. Visit voters.eci.gov.in or the Voter Helpline App\n"
        "2. Fill Form 6 (new registration)\n"
        "3. Submit proof of age, address, and identity\n"
        "4. Your EPIC (Voter ID) card will be issued within 30 days\n"
        "5. Helpline: **1950**"
    ),
    "evm": (
        "🖥️ **Electronic Voting Machines (EVMs):**\n"
        "- EVMs replaced paper ballots to make voting faster and tamper-resistant\n"
        "- Each EVM has a Ballot Unit and Control Unit\n"
        "- VVPAT (Voter Verifiable Paper Audit Trail) prints a slip so you can verify your vote\n"
        "- EVMs are standalone – not connected to the internet"
    ),
    "eligible": (
        "✅ **Voter Eligibility in India:**\n"
        "- Must be a citizen of India\n"
        "- Must be 18 years or older on the qualifying date\n"
        "- Must be ordinarily resident in the constituency\n"
        "- Must not be disqualified under the Representation of the People Act"
    ),
    "nota": (
        "🚫 **NOTA – None of the Above:**\n"
        "- Introduced by the Supreme Court in 2013\n"
        "- Appears as the last option on the EVM ballot\n"
        "- Lets voters express disapproval of all candidates\n"
        "- NOTA votes are counted but do not affect the election result"
    ),
    "lok sabha": (
        "🏛️ **Lok Sabha (House of the People):**\n"
        "- Lower house of India's Parliament\n"
        "- 543 directly elected constituencies\n"
        "- Elections held every 5 years\n"
        "- Minimum age to contest: 25 years\n"
        "- The party/alliance with 272+ seats forms the government"
    ),
    "voting day": (
        "🗳️ **What Happens on Voting Day:**\n"
        "1. Carry your Voter ID or any valid photo ID\n"
        "2. Go to your assigned polling booth (find it at electoralsearch.eci.gov.in)\n"
        "3. Queue up and wait for your turn\n"
        "4. An officer will verify your identity and apply indelible ink on your finger\n"
        "5. Press the button next to your chosen candidate on the EVM\n"
        "6. Verify on the VVPAT screen – done!"
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
        "Try asking: *'How do I register to vote?'* or *'What is NOTA?'*"
    )


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "gemini_configured": bool(GEMINI_API_KEY)}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    """
    Accept a user message + conversation history,
    return an AI response from Gemini (or fallback).
    """
    if not GEMINI_API_KEY:
        return ChatResponse(reply=get_fallback_response(payload.message), source="fallback")

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        # Build history in Gemini format
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
        logger.error("Gemini error: %s", exc)
        return ChatResponse(reply=get_fallback_response(payload.message), source="fallback")
