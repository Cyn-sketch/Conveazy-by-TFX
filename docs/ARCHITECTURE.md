# CONVEAZY by TFX: architecture

> Understand beyond words. *Two people should not have to speak the same emotional language to understand each other.*

CONVEAZY is a two-sided communication bridge for couples. It is not therapy, diagnosis, a chatbot or a compatibility quiz. This document covers the product architecture, data model, user journeys, AI prompt architecture, privacy and consent flows, and dependencies.

## 1. System overview

```
 Browser (Next.js 15, React 19, Tailwind)
   │  same-origin /api/* (Next rewrite) · httpOnly SameSite=Lax session cookie · X-Conveazy-Client header (CSRF)
   ▼
 FastAPI (Python 3.12+)
   ├─ routers/   auth · account (onboarding, privacy, export, delete) · profile (+ relationship) · checkins · ai
   ├─ deps.py    auth, CSRF guard, consent gate, rate limiter
   ├─ ai/
   │   ├─ safety.py      Safety gate: input screen (crisis / manipulation / threat), output screen (diagnosis / medication / certainty)
   │   ├─ context.py     ① Personal Context Engine (consented profile entries + recent check-in)
   │   ├─ knowledge/     ② Evidence-Based Knowledge Engine (vetted corpus + vector retriever)
   │   ├─ engine.py      ③ Communication Intelligence Engine (per-module orchestration + validation)
   │   ├─ contracts.py   Pydantic output schemas per module
   │   ├─ prompts/       Versioned prompt files (system.v1, translator.v1, partner.v1, myself.v1)
   │   └─ providers.py   LLM abstraction: OpenAI · Gemini · Mock (labelled)
   └─ models.py  SQLAlchemy 2 → PostgreSQL 16 (SQLite only in tests)
```

### Request lifecycle for an AI module
1. **Auth + CSRF + consent + rate limit**: the request needs a valid session, the custom client header, a granted `ai_processing` consent, and must stay under N calls per minute per user.
2. **Input safety screen**: urgent crisis language returns crisis resources *without calling the LLM*. Requests to manipulate a partner are declined with a redirect toward direct expression. Concern-level language continues, with resources attached.
3. **Personal context** (consented only), plus **evidence retrieval** (the Partner module only). They go in separately labelled prompt blocks, so clinical knowledge and personal context never mix.
4. **Prompt composition**: `system.v1` + module prompt + context blocks + JSON input.
5. **Provider call**: returns JSON.
6. **Contract validation**: the response must match the module's Pydantic schema. One retry for live providers, otherwise 503 `ai_unavailable`.
7. **Output safety screen**: diagnosis, medication advice and certainty claims about a partner lead to a retry with a correction, otherwise a 503. No unsafe output ever reaches the user.
8. **Citation enforcement** (Partner): source ids the model returns are filtered to the retrieved set. Citations are built server-side from the corpus. An "established" claim with no valid source is downgraded to "possible".
9. **Envelope**: `{status, live, provider, prompt_version, result, citations, crisis, notice, safety}`. `live=false` is rendered as "Mock mode: not live AI".

## 2. Database schema

Every sensitive free-text column is `*_enc`: Fernet (AES-128-CBC + HMAC-SHA256) with a key from `CONVEAZY_DATA_ENCRYPTION_KEY`. Enumerations (emotion, need, etc.) stay in plaintext so they can be queried. They carry no free text.

| Table | Columns | Notes |
|---|---|---|
| `users` | id (uuid), email (unique), password_hash (argon2id), display_name, pronouns, onboarded, token_version, retention_days, save_history, created_at | `token_version` bump = sign out everywhere |
| `consents` | id, user_id→users, kind (`terms_and_care` \| `ai_processing` \| `model_training`), granted, policy_version, created_at | **Append-only ledger**; latest row per kind is current state |
| `relationships` | id, created_by→users, invite_code (unique, nullable, single-use), created_at | Shared space |
| `relationship_members` | id, relationship_id→relationships, user_id→users (**unique**), joined_at | MVP: one space per user, max 2 members |
| `profile_entries` | id, user_id, key, value_enc, share_with_partner, use_in_ai, updated_at; unique(user_id, key) | Owner-controlled switches, both default **off** |
| `checkins` | id, user_id, emotion, intensity 1–10, need, intent, note_enc, created_at | Never visible to partner |
| `conversations` | id, user_id, module (`translator` \| `partner` \| `myself`), title, created_at | Private history |
| `messages` | id, conversation_id, role, content_enc, meta (json: provider, live, prompt_version, status, safety flags), created_at | `meta` never contains user text |

All foreign keys `ON DELETE CASCADE`. Account deletion also deletes explicitly, so it doesn't depend on DB cascade support.

**Profile keys:** communication_style, reassurance_looks_like, feel_dismissed_when, common_misunderstandings, boundaries, resolve_disagreements, receive_affection, overwhelmed_helps, overwhelmed_doesnt_help, self_disclosed_context. Nothing is inferred from a diagnosis. Health context exists only if the person types it in themselves.

**Phase 2 additions (planned):** `knowledge_documents` and `knowledge_chunks` (with a `pgvector` `embedding vector(1536)`, source metadata, reviewer, review date), `youtube_resources` (channel, credential verification notes, reviewer), `conflict_sessions`, and `shared_items` (explicit per-item sharing of a reflection or translation).

## 3. User journeys

1. **Sign up → onboarding (3 steps)**: (a) what CONVEAZY is and isn't, plus a required "complements professional care" acknowledgement; (b) consents: AI processing (on), save history (on), training (**off**), retention window; (c) optional pronouns. There are no diagnosis questions.
2. **Solo use**: every module works without a partner.
3. **Linking**: A creates a single-use invite code, B enters it, and both are linked. Either can end the space at any time, and shared access stops immediately.
4. **Sharing**: each profile answer has two switches. "Share with partner" lets the partner see it on their Us page. "Let AI use this" lets the AI read it. A partner's answer reaches *your* AI only if they switched on **both**.
5. **Check-in → next step**: feeling, intensity, note, need, intent. The app routes to the Translator (communicate) or Myself (reflect), or offers break guidance. Intensity 8 or higher with "communicate" triggers a "settle first" suggestion. The check-in contextualises AI responses for 6 hours.
6. **Translator**: raw draft → intent, flagged phrases (highlighted inline) with "how it may land", 3–4 styled rewrites, changes and preserved items, and a boundary note. Saving is opt-in per translation.
7. **Understand My Partner**: a question → a cited answer with evidence tiers (established / possible / only your partner knows), what can't be inferred, try / avoid lists, questions to ask your partner, and sources. Follow-ups stay in the same conversation.
8. **Understand Myself**: guided Situation → Interpretation → Emotion (and intensity) → Need → a reflection with an evidence check, alternative interpretations, validation, a draft message (with a hand-off to the Translator), escalation signs and a next step.
9. **Privacy**: toggle consents, retention, history; see exactly what the partner can see; export all data as JSON; sign out everywhere; delete the account (password + typed "DELETE").

### Say it to them (bridge), the primary journey
Sender types scraps → `POST /bridge` → **understood meaning** shown first → sender confirms or edits it → `POST /bridge` with `confirmed_meaning` → message for the recipient. Inputs: the recipient's entries marked shared + AI; the recipient's check-in *signal* (feeling and intensity only, last 6 h, only with their `share_checkin_signal` consent, never the note); evidence filtered so condition-specific passages appear only for conditions the recipient disclosed. Output: `BridgeResult` (raw_feelings{right_now, feelings, underneath, feelings_line} shown only to the writer and added to the message when `include_feelings`, understood_meaning, core_points, clarifying_question, message, short_version, alternatives, why_this_works[grounded_in], avoided, kept_true, timing_note, source_ids).

## 4. AI prompt architecture

- **Files:** `backend/app/ai/prompts/*.v1.md`, with front matter `version: <module>.vN`. To change a prompt, add `v2` and change the loader. The version string is stored with every saved response (`messages.meta.prompt_version`).
- **Layering:** `system.v1` (12 non-negotiable rules; modules: translator.v1, partner.v1, myself.v1, bridge.v1: no diagnosis, no medication advice, no certainty about others, both partners equal, no automatic attribution to a diagnosis, no excusing abuse, no manipulation, never invalidate feelings, no dependency, evidence only from EVIDENCE, personal context only from PERSONAL CONTEXT, JSON only), plus the module prompt (task framing and the exact output schema).
- **Separated blocks:** `PERSONAL CONTEXT` (consented JSON), `EVIDENCE` (retrieved passages with ids and evidence level), `CHECK-IN` (inside personal context), `INPUT` / `CONVERSATION SO FAR`.
- **Contracts:** `TranslatorResult`, `PartnerAnswer`, `ReflectionResult` in `contracts.py`, with length caps, enumerated categories and styles, and de-duplicated versions.
- **Defence in depth:** the prompt rules are backed by deterministic screens, so a jailbroken or misbehaving model still can't deliver a diagnosis, a dosage or a fabricated citation.

## 5. Privacy and consent

| Principle | Implementation |
|---|---|
| Private by default | All rows scoped by `user_id`; partner access exists only for `profile_entries.share_with_partner = true` |
| Explicit consent | Consent ledger; AI endpoints gated on `ai_processing`; training consent default off and unused in Phase 1 |
| Minimal collection | No diagnosis fields; free-text notes optional; translations saved only on request; history can be disabled |
| Encryption in transit | HTTPS terminated at the edge (production); `cookie_secure=true` enforced at startup in production |
| Encryption at rest | Fernet field encryption for all free text, plus provider-level disk encryption (e.g. Supabase / RDS) |
| Retention | Per-user window (30 d to 3 y); purge on login and via `python -m app.maintenance purge` (daily cron) |
| Export / delete | `GET /api/privacy/export`, `DELETE /api/account` |
| Logs | Request logs record method, path, status and latency only. Never bodies |
| Third-party AI | Only the minimum prompt is sent; choose provider settings with zero data retention / no training where available |

## 6. Third-party dependencies and API requirements

| Need | Choice | Credentials |
|---|---|---|
| LLM | OpenAI Chat Completions (JSON mode) or Google Gemini `generateContent` (JSON MIME) | `CONVEAZY_OPENAI_API_KEY` or `CONVEAZY_GEMINI_API_KEY` |
| Database | PostgreSQL 16 (self-hosted or Supabase Postgres) | `CONVEAZY_DATABASE_URL` |
| Vector search | Phase 1: in-process TF-IDF cosine retriever. Phase 2: `pgvector` + provider embeddings | none / same LLM key |
| YouTube (Phase 2) | YouTube Data API v3 (`search.list`, `videos.list`, `channels.list`) plus a human credential review | `YOUTUBE_API_KEY` |
| Auth | Built-in (argon2id + signed JWT in httpOnly cookie). Supabase Auth is a drop-in alternative | `CONVEAZY_JWT_SECRET` |
| Email (later) | Password reset / verification via Resend or SES | provider key |

## 7. Roadmap

- **Phase 2:** Conflict Decoder, a knowledge library UI with clinically reviewed, pgvector-backed RAG, a vetted YouTube collection, richer preference use, shared learning, per-item sharing of reflections, Alembic migrations, email verification and password reset, Redis-backed rate limits.
- **Phase 3:** consented pattern insights, more topic collections, native apps.
