# RABTA AI — Free Tier MVP Backend

This is the core backend engine for **RABTA AI**, built to run on **$0/month free tiers** (Google Gemini Flash Free Tier, Deepgram Free Trial, Meta WhatsApp Cloud API Free Window, Qdrant Cloud Free, and Neon PostgreSQL).

---

## 🛠️ Tech Stack & Services

- **Framework:** FastAPI (Python 3.11+)
- **LLM Brain:** Google Gemini 2.5/3.5/3.7 Flash (`google-genai` SDK) via Google AI Studio Free Tier
- **Voice Transcription (STT):** Deepgram Nova-2 (Urdu & English code-switching) via $200 free credit
- **Vector DB:** Qdrant Cloud (1GB RAM / 4GB disk free cluster)
- **Database:** PostgreSQL (Neon Serverless free tier or local Docker)
- **Cache:** Redis (Upstash Serverless free tier or local Docker)

---

## 🚀 Quickstart (Local Development)

### 1. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your API keys:
- `GEMINI_API_KEY`: from [Google AI Studio](https://aistudio.google.com/)
- `DEEPGRAM_API_KEY`: from [Deepgram Console](https://console.deepgram.com/)
- `WHATSAPP_ACCESS_TOKEN` & `WHATSAPP_PHONE_NUMBER_ID`: from [Meta for Developers](https://developers.facebook.com/)

### 2. (Optional) Run Local Databases with Docker
```bash
docker compose up -d
```

### 3. Install Python Dependencies & Run
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Test Webhook Verification
Your webhook URL for Meta Developer portal:
`https://<your-ngrok-or-server-url>/webhooks/whatsapp`
Verification token: `rabta_webhook_verify_token_12345`
