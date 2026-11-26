"""Communication intelligence engine: orchestrates safety -> context -> evidence ->
prompt -> provider -> validation -> safety for each module."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from .contracts import BridgeResult, PartnerAnswer, ReflectionResult, TranslatorResult
from .knowledge.retriever import get_retriever
from .prompts import load_prompt
from .providers import LLMProvider, LLMRequest, ProviderError
from .safety import crisis_payload, screen_input, screen_output

log = logging.getLogger("conveazy.ai")

_CONTRACTS: dict[str, type[BaseModel]] = {
    "translator": TranslatorResult,
    "partner": PartnerAnswer,
    "myself": ReflectionResult,
    "bridge": BridgeResult,
}

DECLINE_MANIPULATION = (
    "CONVEAZY can't help with getting a partner to feel guilty, jealous or afraid, or with using "
    "their vulnerabilities against them. It sounds like something important is going on for you, though. "
    "If you tell us what you're feeling and what you need, we can help you say that directly."
)


class AIUnavailable(RuntimeError):
    pass


BUSY_MESSAGE = "The AI is busy right now. Please try again in a minute. Nothing you wrote was lost."


@dataclass
class AIResult:
    module: str
    status: str  # ok | crisis | declined
    live: bool
    provider: str
    prompt_version: str | None
    result: dict | None = None
    citations: list[dict] = field(default_factory=list)
    crisis: dict | None = None
    notice: str | None = None
    safety: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _strings(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_strings(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_strings(v) for v in obj)
    return ""


def _compose(module: str, context: dict | None, evidence: list | None, body: str) -> tuple[str, str, str]:
    sys_ver, sys_text = load_prompt("system")
    mod_ver, mod_text = load_prompt(module)
    parts = []
    if context is not None:
        parts.append("PERSONAL CONTEXT (consented by its owner; may be empty; never treat as clinical fact):\n"
                     + json.dumps(context, ensure_ascii=False))
    if evidence is not None:
        ev = "\n\n".join(f"[{h.doc.id}] {h.doc.title} | {h.doc.publisher} | level: {h.doc.evidence_level}\n{h.doc.text}"
                         for h in evidence) or "(no relevant sources found)"
        parts.append("EVIDENCE (clinical/research knowledge; cite by id; do not use anything else as evidence):\n" + ev)
    parts.append(body)
    return f"{sys_text}\n\n{mod_text}", "\n\n---\n\n".join(parts), f"{sys_ver}+{mod_ver}"


def _repair(raw: Any, err: ValidationError) -> Any:
    """Fix the harmless ways a model overshoots the contract instead of throwing the whole answer away:
    trim over-long text and lists, clamp numbers, and drop list items (or optional fields) with an unknown label."""
    drops: list[tuple] = []
    for e in err.errors():
        loc, kind, ctx = e["loc"], e["type"], e.get("ctx") or {}
        parent: Any = raw
        try:
            for k in loc[:-1]:
                parent = parent[k]
            key = loc[-1] if loc else None
            if key is None:
                continue
            value = parent[key]
        except (KeyError, IndexError, TypeError):
            continue
        if kind == "string_too_long" and isinstance(value, str):
            parent[key] = value[: ctx["max_length"]].rstrip()
        elif kind == "too_long" and isinstance(value, list):
            parent[key] = value[: ctx["max_length"]]
        elif kind == "less_than_equal" and isinstance(value, (int, float)):
            parent[key] = ctx["le"]
        elif kind == "greater_than_equal" and isinstance(value, (int, float)):
            parent[key] = ctx["ge"]
        elif kind in ("literal_error", "int_parsing", "int_type", "string_type", "model_type", "list_type"):
            # Drop the nearest list item that holds the bad value; otherwise drop the field if it is optional.
            for i in range(len(loc) - 1, -1, -1):
                if isinstance(loc[i], int):
                    drops.append(tuple(loc[: i + 1]))
                    break
            else:
                drops.append(tuple(loc))
    for path in sorted(set(drops), reverse=True):  # later list items first, so indexes stay valid
        try:
            parent = raw
            for k in path[:-1]:
                parent = parent[k]
            del parent[path[-1]]
        except (KeyError, IndexError, TypeError):
            pass
    return raw


def _validate(raw: Any, contract: type[BaseModel]) -> BaseModel:
    last: ValidationError | None = None
    for _ in range(4):
        try:
            return contract.model_validate(raw)
        except ValidationError as e:
            last = e
            if not isinstance(raw, dict):
                break
            raw = _repair(raw, e)
    assert last is not None
    raise last


def _describe(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['type']}" for x in e.errors()[:6])


def _call(provider: LLMProvider, req: LLMRequest, contract: type[BaseModel],
          disclosed: set[str] | frozenset[str] = frozenset()) -> BaseModel:
    last_err: Exception | None = None
    attempts = 3 if provider.live else 1
    base_system = req.system
    for attempt in range(attempts):
        if attempt:
            time.sleep(2.0 if isinstance(last_err, ProviderError) and getattr(last_err, "status", None) == 429 else 0.5)
        try:
            raw = provider.complete_json(req)
            parsed = _validate(raw, contract)
        except ProviderError as e:
            last_err = e
            log.warning("ai.%s provider error (attempt %d): %s", req.module, attempt + 1, e)
            if getattr(e, "busy", False):
                # The provider already retried; more retries would only add waiting.
                raise AIUnavailable(BUSY_MESSAGE) from e
            continue
        except ValidationError as e:
            last_err = e
            log.warning("ai.%s invalid output (attempt %d): %s", req.module, attempt + 1, _describe(e))
            req = LLMRequest(req.module, base_system + "\n\nYour previous answer did not match the required JSON format ("
                             + _describe(e) + "). Return valid JSON that follows the format exactly.", req.user, req.payload)
            continue
        out = screen_output(_strings(parsed.model_dump()), disclosed)
        if out.ok:
            return parsed
        last_err = RuntimeError(f"safety: {out.violations}")
        log.warning("ai.%s output blocked by safety screen (attempt %d): %s", req.module, attempt + 1, out.violations)
        req = LLMRequest(req.module, base_system + "\n\nYour previous answer broke a rule ("
                         + ", ".join(out.violations) + "). Rewrite without it.", req.user, req.payload)
    raise AIUnavailable("We couldn't produce a safe, valid response this time. Please try again.") from last_err


def _precheck(module: str, provider: LLMProvider, *texts: str | None) -> tuple[AIResult | None, dict, dict | None]:
    screen = screen_input(*texts)
    flags = screen.as_flags()
    if screen.manipulation:
        return AIResult(module, "declined", provider.live, provider.name, None,
                        notice=DECLINE_MANIPULATION, safety=flags), flags, None
    # Crisis support is shown alongside the help, never instead of it: the person can keep going.
    crisis = crisis_payload(screen.crisis) if screen.crisis != "none" else None
    return None, flags, crisis


def translate(provider: LLMProvider, *, draft: str, styles: list[str] | None, context: dict,
              audience_note: str | None = None) -> AIResult:
    early, flags, crisis = _precheck("translator", provider, draft, audience_note)
    if early:
        return early
    body = "INPUT:\n" + json.dumps({"draft": draft, "requested_styles": styles or [], "note_from_sender": audience_note},
                                    ensure_ascii=False)
    system, user, ver = _compose("translator", context, None, body)
    parsed = _call(provider, LLMRequest("translator", system, user, {"draft": draft, "styles": styles}), TranslatorResult)
    return AIResult("translator", "ok", provider.live, provider.name, ver, parsed.model_dump(),
                    crisis=crisis, safety=flags)


def ask_partner(provider: LLMProvider, *, question: str, history: list[dict], context: dict) -> AIResult:
    early, flags, crisis = _precheck("partner", provider, question)
    if early:
        return early
    retriever = get_retriever()
    hits = retriever.search(question + " " + " ".join(h["content"] for h in history[-2:] if h["role"] == "user"), k=4)
    allowed = {h.doc.id for h in hits}
    body = "CONVERSATION SO FAR:\n" + json.dumps(history[-8:], ensure_ascii=False) + "\n\nQUESTION:\n" + question
    system, user, ver = _compose("partner", context, hits, body)
    parsed = _call(provider, LLMRequest("partner", system, user, {"question": question, "source_ids": [h.doc.id for h in hits]}), PartnerAnswer)
    data = parsed.model_dump()
    # Citations are built server-side from retrieved documents only. Any id the model invents is dropped.
    used: list[str] = []
    for ev in data["evidence"]:
        ev["source_ids"] = [i for i in ev["source_ids"] if i in allowed]
        if ev["level"] == "established" and not ev["source_ids"]:
            ev["level"] = "possible"  # an uncited claim can't be presented as established
        used += [i for i in ev["source_ids"] if i not in used]
    citations = [retriever.get(i).citation() for i in used]  # type: ignore[union-attr]
    return AIResult("partner", "ok", provider.live, provider.name, ver, data, citations, crisis, safety=flags)


def reflect(provider: LLMProvider, *, situation: str, interpretation: str | None, emotions: list[str],
            needs: list[str], intensity: int | None, context: dict) -> AIResult:
    early, flags, crisis = _precheck("myself", provider, situation, interpretation)
    if early:
        return early
    payload = {"situation": situation, "interpretation": interpretation or "", "emotions": emotions,
               "needs": needs, "intensity": intensity}
    body = "INPUT:\n" + json.dumps(payload, ensure_ascii=False)
    system, user, ver = _compose("myself", context, None, body)
    parsed = _call(provider, LLMRequest("myself", system, user, payload), ReflectionResult)
    return AIResult("myself", "ok", provider.live, provider.name, ver, parsed.model_dump(), crisis=crisis, safety=flags)


_CONDITIONS = {"bpd": r"\bbpd\b|borderline", "depression": r"depress|\bmdd\b", "gad": r"\bgad\b|anxiety", "pcos": r"pcos|pmos|polycystic"}


def disclosed_conditions(text: str) -> set[str]:
    return {k for k, pat in _CONDITIONS.items() if re.search(pat, text or "", re.I)}


def _ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    w = re.findall(r"[a-z']+", (text or "").lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def _redact_leaks(text: str, story_grams: set) -> tuple[str, bool]:
    """Drop any sentence that repeats 5+ consecutive words of a private story."""
    if not text or not story_grams:
        return text, False
    keep, leaked = [], False
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if _ngrams(sent) & story_grams:
            leaked = True
        else:
            keep.append(sent)
    return " ".join(keep).strip(), leaked


def bridge(provider: LLMProvider, *, scraps: str, confirmed_meaning: str | None, context: dict,
           recipient_name: str, recipient_profile: dict, recipient_signal: dict | None,
           include_feelings: bool = False, situation: str = "", intensity: int | None = None,
           share_traits: bool = False, traits: list[dict] | None = None, recipient_story: str = "",
           long_distance: str | None = None, sender_name: str = "your partner") -> AIResult:
    """What happened (+ optional scraps) -> confirmed meaning -> a message written for this recipient,
    plus a feeling brief that carries the sender's real intensity."""
    from .knowledge.library import condition_lexicon, exercise_menu, exercises, hurt_points_text

    early, flags, crisis = _precheck("bridge", provider, situation, scraps, confirmed_meaning)
    if early:
        return early
    retriever = get_retriever()
    disclosed = disclosed_conditions(recipient_profile.get("Diagnoses or health context I choose to share (optional)", ""))
    wants_anger = bool(re.search(r"rage|anger|angry|furious", " ".join(recipient_profile.values()) + " " + scraps, re.I))
    query = " ".join([situation, scraps, " ".join(disclosed), "anger" if wants_anger else "",
                      recipient_profile.get("What can trigger me", "")])
    # Never pull condition-specific evidence for a condition the recipient didn't disclose themselves.
    hits = [h for h in retriever.search(query, k=8, topics=sorted(disclosed) + (["anger"] if wants_anger else []))
            if not (set(h.doc.topics) & set(_CONDITIONS)) or (set(h.doc.topics) & disclosed)]
    # Prefer passages about how words land (abandonment, anger, regulation) over general condition facts.
    landing = {"bpd", "anger", "attachment_reassurance", "emotional_regulation", "communication"}
    hits = sorted(hits, key=lambda h: (-len(set(h.doc.topics) & landing), -h.score))[:3]
    allowed = [h.doc.id for h in hits]
    share_traits = bool(share_traits and traits)
    payload = {"scraps": scraps, "situation": situation, "confirmed_meaning": confirmed_meaning,
               "recipient_name": recipient_name, "sender_name": sender_name,
               "recipient_profile": recipient_profile, "recipient_signal": recipient_signal, "source_ids": allowed,
               "include_feelings": include_feelings, "intensity": intensity, "share_traits": share_traits,
               "traits": traits or [], "long_distance": long_distance, "sender_profile": (context.get("you") or {}).get("preferences", {}),
               "condition_lexicon": condition_lexicon(sorted(disclosed)),
               "sender_intensity": (context.get("your_recent_checkin") or {}).get("intensity_value")}
    parts = ["RECIPIENT CHECK-IN SIGNAL (shared with consent; may be null):\n" + json.dumps(recipient_signal),
             "INCLUDE FEELINGS: " + str(include_feelings).lower(),
             f"SENDER'S OWN INTENSITY RATING (1-10, may be null; use it as-is in the brief): {intensity}",
             "RELATIONSHIP: " + (f"long distance ({long_distance})" if long_distance else "not marked as long distance")]
    if recipient_story:
        parts.append(f"RECIPIENT'S PRIVATE STORY (the sender has NOT seen this). Use it only to understand what might hurt "
                     f"{recipient_name} and to choose gentler wording. Never reveal, quote, hint at or refer to it anywhere "
                     f"in your output:\n\"\"\"{recipient_story}\"\"\"")
    hp = hurt_points_text(sorted(disclosed))
    if hp:
        parts.append("COMMON HURT POINTS for what the recipient chose to share (avoid even if not in their own triggers):\n" + hp)
    parts.append("CALMING EXERCISES (pick ids for `calm` only from this list):\n" + exercise_menu())
    if share_traits:
        parts.append("TRAITS THE SENDER CHOSE TO SHARE (reword kindly for the brief):\n" + json.dumps(traits, ensure_ascii=False))
    parts.append("INPUT:\n" + json.dumps({"what_happened": situation, "scraps": scraps, "confirmed_meaning": confirmed_meaning,
                                          "sender_name": sender_name, "recipient_name": recipient_name}, ensure_ascii=False))
    system, user, ver = _compose("bridge", context, hits, "\n\n".join(parts))
    parsed = _call(provider, LLMRequest("bridge", system, user, payload), BridgeResult, disclosed)
    data = parsed.model_dump()
    data["source_ids"] = [i for i in data["source_ids"] if i in allowed]
    for w in data["why_this_works"]:
        if w["grounded_in"] == "evidence" and not data["source_ids"]:
            w["grounded_in"] = "general"
    valid = exercises()
    data["calm"] = [dict(c, **{"exercise": valid[c["id"]]}) for c in data["calm"] if c["id"] in valid][:3]
    if data.get("brief"):
        if intensity:
            data["brief"]["intensity"] = intensity
        if not share_traits:
            data["brief"]["traits"] = []  # trait suggestions never leave the sender without their say-so
    # Defence in depth: nothing from the recipient's private story may surface in what the sender sees.
    grams = _ngrams(recipient_story)
    leaked = False
    if grams:
        for k in ("message", "short_version", "timing_note"):
            if data.get(k):
                data[k], l = _redact_leaks(data[k], grams)
                leaked |= l
        for w in data["why_this_works"]:
            w["reason"], l = _redact_leaks(w["reason"], grams)
            leaked |= l
        if data.get("brief"):
            for k in ("feeling", "why", "need"):
                data["brief"][k], l = _redact_leaks(data["brief"][k], grams)
                leaked |= l
        for a in data["alternatives"]:
            a["text"], l = _redact_leaks(a["text"], grams)
            leaked |= l
    if leaked:
        flags = dict(flags, private_story_redacted=True)
    citations = [retriever.get(i).citation() for i in data["source_ids"]]  # type: ignore[union-attr]
    return AIResult("bridge", "ok", provider.live, provider.name, ver, data, citations, crisis, safety=flags)
