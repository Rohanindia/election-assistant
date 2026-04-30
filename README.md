# 🗳️ VoteGuide AI – India Election Assistant

> An AI-powered assistant that helps Indian citizens understand the election process, timelines, and voting steps in an interactive and easy-to-follow way.

**Challenge 2 – PromptWars Virtual | Hack2skill × Google for Developers**

---

## 🎯 Chosen Vertical

**Civic Education & Democratic Participation**

This assistant targets every Indian citizen — first-time voters, students, and general public — who needs clear, unbiased guidance on the Indian election process.

---

## 🌟 Features

| Feature | Description |
|---|---|
| 🤖 AI Chat | Conversational Q&A powered by **Google Gemini 2.0 Flash** |
| 🔁 Memory | Multi-turn conversation history for natural follow-ups |
| ⚡ Fallback | Keyword-based instant answers when Gemini is unavailable |
| 🗺️ Timeline | Visual step-by-step election timeline in the sidebar |
| 🚀 Quick Chips | One-tap topic buttons for common election questions |
| 🔒 Input Validation | Pydantic-enforced sanitization; rejects empty/oversized input |
| ♿ Accessible | Semantic HTML, ARIA labels, keyboard navigation, responsive design |

---

## 🏗️ Architecture & Approach

```
User Browser
     │
     ▼
FastAPI Backend (Python)
     │
     ├─ GET  /          → Serves index.html (Jinja2)
     ├─ GET  /health    → Health check
     └─ POST /chat      → Accepts message + history
               │
               ▼
       Google Gemini 2.0 Flash API
       (system prompt: election-specialist)
               │
               ▼ (if Gemini unavailable)
       Keyword Fallback Engine
```

**Logic Flow:**
1. User types a question (validated: non-empty, ≤ 1000 chars)
2. Full conversation history is sent with each request (stateless backend, stateful frontend)
3. Gemini responds with election-specific context from the system prompt
4. If Gemini is unavailable (no API key / error), keyword fallback fires automatically
5. Response is rendered in the chat UI with typing animation

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **AI** | Google Gemini 2.0 Flash API (`google-generativeai`) |
| **Backend** | Python 3.11 + FastAPI + Uvicorn |
| **Frontend** | HTML5, CSS3, Vanilla JS (single-page, no build step) |
| **Templating** | Jinja2 |
| **Validation** | Pydantic v2 |
| **Testing** | Pytest + HTTPX (FastAPI TestClient) |

---

## 📦 Project Structure

```
election-assistant/
├── main.py                  # FastAPI app, Gemini integration, fallback engine
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
├── templates/
│   └── index.html           # Full chat UI (HTML/CSS/JS)
├── static/                  # Static assets (extensible)
└── tests/
    └── test_main.py         # 15+ pytest tests covering all endpoints
```

---

## 🔑 Google Services Used

### Google Gemini 2.0 Flash API
- Powers all AI responses via `google-generativeai` Python SDK
- System prompt enforces election-specialist persona
- Multi-turn conversation with full history context
- Graceful fallback if API is unavailable

---

## 🚀 How to Run

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/election-assistant.git
cd election-assistant
```

### 2. Create a virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your API key
```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_key_here
```
Get a free key at: https://aistudio.google.com/

### 5. Run the server
```bash
uvicorn main:app --reload
```

### 6. Open the app
Visit: **http://localhost:8000**

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Expected output: **15 tests passing** covering:
- Health endpoint
- HTML rendering
- Input validation (empty, too-long, missing fields)
- Fallback keyword engine (all keywords)
- Chat with mocked Gemini
- Chat without API key (fallback mode)
- Multi-turn conversation history
- CORS headers

---

## 🔒 Security Measures

- **Input validation** via Pydantic: rejects empty messages and messages > 1000 characters
- **`.env` excluded** from git via `.gitignore` — API keys never committed
- **`.env.example`** provided for safe onboarding
- **Non-partisan system prompt**: AI refuses to comment on specific candidates/parties
- **CORS middleware** configured for controlled cross-origin access
- **Error handling**: Gemini failures caught and gracefully handled without exposing internals

---

## ♿ Accessibility

- Semantic HTML (`<header>`, `<main>`, `<aside>`)
- ARIA label on send button
- Keyboard navigation: **Enter** to send, **Shift+Enter** for new line
- Color contrast meets WCAG AA standards
- Fully responsive: works on mobile, tablet, and desktop

---

## 📋 Assumptions Made

1. Target audience is Indian citizens (Lok Sabha + Vidhan Sabha focus)
2. English-language interface (multilingual support can be added via Google Translate API)
3. Conversation history stored client-side (no user accounts required)
4. The app does not provide legal advice — only factual, process-based information
5. Gemini 2.0 Flash is used for its speed and cost-efficiency at scale

---

## 👨‍💻 Author

**Rohan Devadiga**  
KLE Technological University, Hubballi  
PromptWars Virtual – Challenge 2

---

*Built with ❤️ for Indian democracy. Every vote counts.*
