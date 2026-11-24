# CONVEAZY by TFX

**Understand beyond words.** An AI-powered relationship communication and understanding companion, from TFX, the tool-building segment of MadAutomate.

CONVEAZY helps couples understand each other, especially when one or both partners live with emotional dysregulation, anxiety, depression, BPD, hormonal health conditions such as PCOS, or simply different communication styles. It is a two-sided bridge. It is not therapy, diagnosis or a referee.

## The core idea

One partner finds it hard to put feelings into words. The other may feel things intensely and be easily triggered by silence, vagueness or blame. **Say it to them** sits between them: the sender types rough scraps, CONVEAZY plays back what it thinks they mean and asks them to confirm, then writes a message for *this* recipient. It uses the recipient's own "About me" profile (triggers, what calms them, any diagnoses they chose to share) and cited sources (APA, DSM-5-TR summaries, NIMH, NHS). It changes how something is said, never what is meant.

## What's built

| Module | What it does |
|---|---|
| **Say it to them** (main) | Scraps → a raw, private read of what you are feeling right now (optionally added to the message) → "Is this what you mean?" → a message shaped by the recipient's own profile. It explains each choice (from their profile, from the sources, or general), what was left out, and what was kept true. If the recipient opts in and checked in at 7/10 or higher, it adds a short version and a timing nudge |
| About me profiles | Each partner writes about themselves: how they feel, triggers, what calms them, how they express themselves, and diagnoses they choose to share. Every answer has its own switches |
| Auth & onboarding | Email + password (argon2id), httpOnly session cookie, 3-step onboarding with care acknowledgement and consents |
| Profiles | Ten communication-preference answers, each with its own "Share with partner" and "Let AI use this" switches (both off by default) |
| Shared space | Single-use invite codes; either partner can end it at any time |
| Message Translator | Flags risky phrases and shows how they may land, gives 3–4 styled rewrites, explains what changed and what was kept, and preserves boundaries |
| Understand My Partner | Cited answers with evidence tiers (established / possible / only your partner knows), plus try / avoid lists and questions to ask your partner |
| Understand Myself | Guided Situation → Interpretation → Emotion → Need → Communication reflection |
| Emotional check-in | Feeling, intensity, need and intent, routed to the right next step; contextualises AI for 6 hours |
| Privacy | Consent ledger, retention window, history toggle, JSON export, account deletion, sign out everywhere |
| Safety | Crisis detection (with India, US, UK and global resources), manipulation declines, blocks on diagnosis and medication output, citation enforcement |

Architecture, schema, journeys, prompt design and privacy flows: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. API contracts: **[docs/API.md](docs/API.md)**.

## Mock mode: read this first

Without an API key, the backend uses **`MockProvider`**: deterministic, rule-based output so every flow works in development and tests. Every mock response carries `live: false`, and the UI shows a **"Mock mode: not live AI"** badge on the shell and on each result. It is not a language model and is never presented as one. Set `CONVEAZY_AI_PROVIDER=openai` (or `gemini`) plus the key to go live. Nothing else changes.

## Local setup

Requirements: Python 3.12+, Node 20+, PostgreSQL 16.

```bash
# 1. Database
createuser conveazy -P            # password: conveazy (dev only)
createdb conveazy -O conveazy

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # fill in secrets (see below)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                        # http://localhost:3000 (proxies /api to :8000)
```

Tables are created on startup in Phase 1. Moving to Alembic migrations is on the Phase 2 list.

## Environment variables (backend, prefix `CONVEAZY_`)

| Variable | Required | Purpose |
|---|---|---|
| `ENV` | – | `development` \| `test` \| `production` (production refuses unsafe config) |
| `DATABASE_URL` | yes | `postgresql+psycopg://user:pass@host:5432/db` |
| `JWT_SECRET` | prod | ≥32 random chars for session signing |
| `DATA_ENCRYPTION_KEY` | prod | Fernet key for field-level encryption at rest |
| `COOKIE_SECURE` | prod | `true` behind HTTPS |
| `AI_PROVIDER` | – | `mock` (default) \| `openai` \| `gemini` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | if openai | default model `gpt-4o-mini` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | if gemini | default model `gemini-1.5-flash` |
| `AI_RATE_LIMIT_PER_MINUTE` | – | default 12 per user |
| `AUTH_RATE_LIMIT_PER_MINUTE` | – | default 10 per IP |
| `DEFAULT_RETENTION_DAYS` | – | default 365 |

Frontend: `CONVEAZY_API_URL` (default `http://127.0.0.1:8000`), used by the `/api` rewrite.

## Tests

```bash
cd backend && pytest -q                 # 44 tests: auth, permissions, privacy boundaries, encryption at rest,
                                        # consent, retention, AI contract validation, citation enforcement,
                                        # safety screens, rate limiting, error handling
cd frontend && npm run typecheck && npm run build
# Two-partner end-to-end journey in a real browser (needs both servers running, Playwright installed):
BASE_URL=http://localhost:3000 SHOTS=./e2e/shots npm run e2e
```

## Deployment

- **Frontend:** Vercel (or any Node host). Set `CONVEAZY_API_URL` to the backend's internal URL.
- **Backend:** a container on Fly.io, Render, Railway or Cloud Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`. Set `CONVEAZY_ENV=production` and all secrets.
- **Database:** Supabase Postgres or managed Postgres with encryption at rest and daily backups.
- **Daily job:** `python -m app.maintenance purge` (retention).
- Serve both under one domain (or set the cookie domain accordingly) so the session cookie stays first-party.

## Known limitations (honest list)

- **Knowledge corpus is a draft.** The 16 passages are editorial paraphrases written for CONVEAZY, not quotations. They and their URLs **must be checked by a qualified clinician and a person before launch** (`corpus.json → _meta.links_verified: false`). The build environment had no internet access to verify links.
- Retrieval is in-process TF-IDF vectors. pgvector with embeddings is Phase 2.
- Safety screens are pattern-based floors, not clinical screening. Crisis support is shown alongside the help, never instead of it, so the person can keep going. Crisis lines should be localised per user region.
- The rate limiter is in-memory (single process). Use Redis when running multiple workers.
- No email verification or password reset yet. No Alembic migrations yet.
- Mock rewrites are template-based and read stiffly. Real quality needs a live provider.
- Live OpenAI and Gemini paths are implemented but untested against real keys in this build.
- Conflict Decoder and the full knowledge library UI are Phase 2. YouTube channels (`backend/app/ai/knowledge/youtube.json`) are a candidate list marked `verified: false`. Links are YouTube searches, so no channel handle is guessed. Verify credentials independently and with the YouTube Data API before marking them verified.
- DSM-5-TR is used only as short paraphrases for explanation, never quoted and never used to diagnose. Condition-specific evidence is used only when the recipient disclosed that condition themselves.
- The mock bridge expands texting shorthand and reorders scraps, but it can't truly understand them. Real "understanding" needs a live provider.

## Brand

CONVEAZY (always capitals) · signature "CONVEAZY by TFX" · parent ecosystem MadAutomate. The palette is warm paper and ink, with clay for *you*, sage for *your partner*, and dusk for the space between. Type is Fraunces (editorial serif) and Inter. The mark is two voices turned toward each other, with the space between them held open. Light and dark themes follow the system setting.
