# 🗳️ VoteGuide AI – India Election Assistant

> **VoteGuide AI** is an interactive assistant that helps Indian citizens understand the election process, timelines, and steps in an easy-to-follow way — powered by Google Gemini and Google Cloud Translation API.

**Challenge 2 – PromptWars Virtual | Hack2skill × Google for Developers**

---

## 📋 Problem Statement

> *"Create an assistant that helps users understand the election process, timelines, and steps in an interactive and easy-to-follow way."*

**VoteGuide AI** is built exactly to solve this problem. This assistant guides every Indian citizen — first-time voters, students, and the general public — through the election process with interactive Q&A, easy-to-follow step-by-step guides, and visual election timelines.

---

## 🎯 What This Assistant Does

This assistant makes the Indian election process interactive and easy-to-follow by covering:

- ✅ **Election Process** — The assistant explains the complete election process from announcement to result
- ✅ **Election Timelines** — Interactive timelines showing every phase of the election process
- ✅ **Step-by-Step Guides** — Easy-to-follow steps for voter registration, polling day, and counting
- ✅ **Interactive Q&A** — Ask the assistant anything about the election process in natural language
- ✅ **Multilingual Support** — Translate election process info into Hindi, Kannada, Tamil, Telugu, Malayalam

---

## 🗺️ Election Process & Timelines

This assistant covers the complete Indian election process interactively:

### Step-by-Step Election Process Timeline:
1. **Announcement** — ECI announces schedule; Model Code of Conduct begins
2. **Nominations** — Candidates file papers; scrutiny of nominations takes place
3. **Campaigning** — Parties campaign; ends 48 hours before polling (silent period)
4. **Polling Day** — Voters cast votes via EVM; VVPAT provides paper trail
5. **Counting & Result** — Votes counted; winner declared by Returning Officer

### Easy-to-Follow Steps the Assistant Explains:
- 📋 **Voter Registration Steps** — Form 6, NVSP portal, helpline 1950, EPIC card
- 🗳️ **Voting Day Steps** — Booth location, ID verification, EVM usage, VVPAT
- 🏛️ **Lok Sabha Election Process** — 543 constituencies, 5-year timelines, 272+ majority
- 📜 **Vidhan Sabha Election Process** — State assembly timelines and steps
- 🚫 **NOTA Steps** — How and when to use None of the Above option
- ⚖️ **Model Code of Conduct** — Timeline and steps of MCC enforcement

---

## 🌟 Interactive Features

| Interactive Feature | Description |
|---|---|
| 🤖 **Interactive AI Chat** | Ask the assistant anything about the election process |
| 🗺️ **Visual Election Timeline** | Interactive sidebar showing election process phases |
| 🚀 **Quick Topic Chips** | One-tap interactive buttons for common election questions |
| 🌐 **Language Selector** | Interactive translation into 5 Indian languages |
| 🔁 **Conversation Memory** | Multi-turn interactive conversation for follow-up questions |
| ⚡ **Instant Fallback** | Keyword-based instant answers for election process steps |

---

## 🔑 Google Services Integration

This assistant uses **7 Google Services**:

### 1. Google Gemini 2.0 Flash API
- Powers all interactive AI responses about the election process
- System prompt makes the assistant an election process specialist
- Handles multi-turn interactive conversations with full history
- Explains election timelines, steps, and process in easy-to-follow language
- SDK: `google-generativeai`

### 2. Google Cloud Translation API
- Translates election process information into Indian languages interactively
- Supported: Hindi (hi), Kannada (kn), Tamil (ta), Telugu (te), Malayalam (ml)
- Makes election process easy-to-follow for non-English speakers
- Endpoint: `translation.googleapis.com/language/translate/v2`

### 3. Google Analytics GA4
- Tracks user interactions with the election assistant
- Custom events: chat_message_sent, quick_topic_clicked, news_search_opened
- Measures response times and language preferences
- Helps understand which election topics users ask most

### 4. Google Charts
- Visual representation of Indian election data
- Voter Turnout % bar chart (2009–2024)
- 2024 Election Phases pie chart (7 phases, 545 constituencies)
- Renders dynamically in sidebar alongside the assistant

### 5. Google News Search
- One-click access to latest Indian election news
- Opens Google News filtered for Indian election content
- Keeps users informed with real-time election updates

### 6. Google Firebase Firestore
- Stores every chat interaction in Firestore collection
- Tracks message counts, languages used, cache hits
- Endpoint: `/firestore/stats` shows real-time Firestore data
- Enables persistent chat analytics across sessions

### 7. Google Cloud Logging
- Structured JSON logging for every chat query and translation
- Logs IP hash, message length, language, cache status
- Format compatible with Google Cloud Logging ingestion
- Enables monitoring and debugging in production

## 🏗️ Google Cloud Architecture
User Request
│
▼
Google Analytics GA4 ← tracks every interaction
│
▼
FastAPI Backend
│
├── Google Gemini API ← primary AI
├── Google Cloud Translation API ← multilingual
├── Google Cloud Logging ← structured logs
├── Google Firebase Firestore ← chat history
├── Google Charts ← data visualization
└── Google News ← election news

## 📊 Google Services Status
Check live status at:
`https://election-assistant-production-c9e1.up.railway.app/health`

All 6 Google services are monitored and reported in the health endpoint.

---

## 🏗️ Architecture & Logic

```
User Browser (Interactive UI)
     │
     ▼
FastAPI Backend (Python)
     │
     ├─ GET  /                → Serves interactive assistant UI
     ├─ GET  /health          → Health check (Gemini + Translate status)
     ├─ POST /chat            → Election process Q&A (interactive assistant)
     └─ POST /translate       → Translate election process info
               │
               ▼
       Google Gemini 2.0 Flash  ← Primary AI (election specialist)
               │
               ▼ (quota exceeded)
       Groq Llama 3.1           ← Fallback AI (same election context)
               │
               ▼ (both unavailable)
       Keyword Fallback Engine  ← Easy-to-follow instant answers
```

**Step-by-Step Logic Flow:**
1. User asks the assistant about election process, timelines, or steps
2. Message validated (non-empty, ≤ 1000 chars) and sanitized
3. Gemini processes with election-specialist system prompt
4. Assistant responds with easy-to-follow, step-by-step election process info
5. User interactively translates response into preferred Indian language

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Primary AI** | Google Gemini 2.0 Flash API |
| **Fallback AI** | Groq Llama 3.1 (8b-instant) |
| **Translation** | Google Cloud Translation API |
| **Analytics** | Google Analytics GA4 |
| **Data Viz** | Google Charts API |
| **Storage** | Google Firebase Firestore |
| **Logging** | Google Cloud Logging |
| **News** | Google News Search |
| **Backend** | Python 3.12 + FastAPI + Uvicorn |
| **Frontend** | HTML5, CSS3, Vanilla JS |
| **Testing** | Pytest + HTTPX |
| **Deployment** | Railway |

---

## 📦 Project Structure

```
election-assistant/
├── main.py                  # FastAPI app, Gemini + Translate integration
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
├── templates/
│   └── index.html           # Interactive assistant UI
├── static/                  # Static assets
└── tests/
    └── test_main.py         # 15+ pytest tests
```

---

## 🚀 How to Run

### Step 1 — Clone the repository
```bash
git clone https://github.com/Rohanindia/election-assistant.git
cd election-assistant
```

### Step 2 — Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Set up API keys
```bash
cp .env.example .env
# GEMINI_API_KEY=your_gemini_key
# TRANSLATE_API_KEY=your_translate_key
# GROQ_API_KEY=your_groq_key
```

### Step 5 — Run the interactive assistant
```bash
uvicorn main:app --reload
```

### Step 6 — Open the assistant
Visit: **http://localhost:8000**

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- Health endpoint and Google Services status
- Interactive assistant HTML rendering
- Input validation (empty, too-long, missing fields)
- Election process keyword fallback engine
- Chat with mocked Gemini
- Google Translate API endpoint
- Multi-turn interactive conversation history
- CORS and security headers

---

## 🔒 Security Measures

- **Input validation** via Pydantic — rejects empty/oversized messages
- **HTML sanitization** — strips script tags from user input
- **Security headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Rate limiting** — max 30 requests/minute per IP
- **`.env` excluded** from git — API keys never committed
- **Non-partisan assistant** — refuses to comment on specific candidates/parties
- **CORS middleware** — controlled cross-origin access
- **Error handling** — failures handled gracefully without exposing internals

---

## ♿ Accessibility

- Semantic HTML (`<header>`, `<main>`, `<aside>`)
- `aria-live="polite"` on chat messages for screen readers
- `aria-label` on all interactive buttons
- Skip navigation link for keyboard users
- Keyboard navigation: **Enter** to send, **Shift+Enter** for new line
- WCAG AA color contrast compliance
- Fully responsive: mobile, tablet, and desktop

---

## 📋 Assumptions Made

1. Target audience is Indian citizens (Lok Sabha + Vidhan Sabha focus)
2. Assistant provides election process info in English with translation to Indian languages
3. Conversation history stored client-side — no user accounts required
4. Assistant provides factual election process information only — not legal advice
5. Gemini 2.0 Flash is primary AI for delivering easy-to-follow responses

---

## 👨‍💻 Author

**Rohan Devadiga**
KLE Technological University, Hubballi
PromptWars Virtual – Challenge 2

---

*VoteGuide AI — Your interactive assistant for understanding the Indian election process, timelines, and steps in an easy-to-follow way. Every vote counts. 🇮🇳*
