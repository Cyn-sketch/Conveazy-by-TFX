# CONVEAZY API contracts (v0.1)

Base: `/api`. Auth is the `cz_session` httpOnly cookie. Every non-GET request must send `X-Conveazy-Client: web`.
Errors are always `{"detail": {"code": str, "message": str}}`. Interactive docs: `/api/docs` (non-production).

| Method & path | Body | Returns |
|---|---|---|
| POST `/auth/signup` | `{email, password(≥10), display_name}` | 201 `User`, sets cookie · 409 `email_taken` |
| POST `/auth/login` | `{email, password}` | `User` · 401 `bad_credentials` |
| POST `/auth/logout?everywhere=bool` | – | 204 |
| GET `/auth/me` | – | `User {id,email,display_name,pronouns,onboarded}` |
| POST `/onboarding` | `{accept_terms_and_care:true, ai_processing, model_training?, retention_days?, save_history?, pronouns?}` | `User` · 422 `terms_required` |
| GET/PUT `/privacy` | PUT: `{retention_days?, save_history?, ai_processing?, model_training?}` | `{retention_days, save_history, consents, partner_can_see, consent_history[]}` |
| GET `/privacy/export` | – | JSON attachment of all of *your* data |
| DELETE `/account` | `{password, confirm:"DELETE"}` | 204 · 403 `bad_password` |
| GET `/profile` | – | `{fields:[{key,label,value,share_with_partner,use_in_ai}]}` |
| PUT `/profile/{key}` | `{value, share_with_partner, use_in_ai}` | `{key, share_with_partner, use_in_ai}` |
| DELETE `/profile/{key}` | – | 204 |
| GET `/relationship` | – | `{status:"none"}` · `{status:"pending", invite_code}` · `{status:"linked", partner{name,pronouns}, partner_shared[{key,label,value}]}` |
| POST `/relationship/invite` | – | `{invite_code}` |
| POST `/relationship/join` | `{code}` | relationship · 404 `invalid_code` · 409 |
| DELETE `/relationship` | – | 204 (ends space for both) |
| POST `/checkins` | `{emotion, intensity 1-10, need, intent, note?}` | 201 `{checkin, next{label,href}, guidance, crisis, disclaimer}` |
| GET `/checkins` · DELETE `/checkins/{id}` | – | own check-ins only |
| GET `/ai/status` | – | `{provider, live, label}` |
| POST `/translate` | `{draft, styles?[], note?, save?}` | `AIEnvelope<TranslatorResult>` |
| POST `/partner/ask` | `{question, conversation_id?}` | `AIEnvelope<PartnerAnswer>` (+`conversation_id` if history on) |
| POST `/myself/reflect` | `{situation, interpretation?, emotions[], needs[], intensity?, save?}` | `AIEnvelope<ReflectionResult>` |
| GET `/conversations?module=` · GET/DELETE `/conversations/{id}` | – | own conversations only (404 otherwise) |
| GET `/knowledge/sources` | – | corpus metadata and sources |

AI endpoints: 403 `consent_required`, 429 `rate_limited`, 503 `ai_unavailable`.

```ts
AIEnvelope<T> = { module, status: "ok"|"crisis"|"declined", live: boolean, provider: "mock"|"openai"|"gemini",
  prompt_version: string|null, result: T|null, citations: Citation[], crisis: Crisis|null, notice: string|null, safety: {crisis, manipulation, threat} }
```
Schemas for `TranslatorResult`, `PartnerAnswer` and `ReflectionResult` are in `backend/app/ai/contracts.py` (frontend mirror: `frontend/lib/api.ts`).
