"""Communication intelligence engine: orchestrates safety -> context -> evidence ->
prompt -> provider -> validation -> safety for each module."""
from __future__ import annotations

import json
import logging
import re
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


def _call(provider: LLMProvider, req: LLMRequest, contract: type[BaseModel]) -> BaseModel:
    last_err: Exception | None = None
    attempts = 2 if provider.live else 1
    for _ in range(attempts):
        try:
            raw = provider.complete_json(req)
            parsed = contract.model_validate(raw)
        except (ProviderError, ValidationError) as e:
            last_err = e
            log.warning("ai.%s invalid output: %s", req.module, type(e).__name__)
            continue
        out = screen_output(_strings(parsed.model_dump()))
        if out.ok:
            return parsed
        last_err = RuntimeError(f"safety: {out.violations}")
        log.warning("ai.%s output blocked by safety screen: %s", req.module, out.violations)
        req = LLMRequest(req.module, req.system + "\n\nYour previous answer broke a rule ("
                         + ", ".join(out.violations) + "). Rewrite without it.", req.user, req.payload)
    raise AIUnavailable("We couldn't produce a safe, valid response this time. Please try again.") from last_err


def _precheck(module: str, provider: LLMProvider, *texts: str | None) -> tuple[AIResult | None, dict, dict | None]:
    screen = screen_input(*texts)
    flags = screen.as_flags()
    if screen.crisis == "urgent":
        return AIResult(module, "crisis", provider.live, provider.name, None,
                        crisis=crisis_payload("urgent"), safety=flags), flags, None
    if screen.manipulation:
        return AIResult(module, "declined", provider.live, provider.name, None,
                        notice=DECLINE_MANIPULATION, safety=flags), flags, None
    crisis = crisis_payload("concern") if screen.crisis == "concern" else None
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


def bridge(provider: LLMProvider, *, scraps: str, confirmed_meaning: str | None, context: dict,
           recipient_name: str, recipient_profile: dict, recipient_signal: dict | None) -> AIResult:
    """Sender's rough scraps -> confirmed meaning -> a message written for this recipient."""
    early, flags, crisis = _precheck("bridge", provider, scraps, confirmed_meaning)
    if early:
        return early
    retriever = get_retriever()
    disclosed = disclosed_conditions(recipient_profile.get("Diagnoses or health context I choose to share (optional)", ""))
    wants_anger = bool(re.search(r"rage|anger|angry|furious", " ".join(recipient_profile.values()) + " " + scraps, re.I))
    query = " ".join([scraps, " ".join(disclosed), "anger" if wants_anger else "",
                      recipient_profile.get("What can trigger me", "")])
    # Never pull condition-specific evidence for a condition the recipient didn't disclose themselves.
    hits = [h for h in retriever.search(query, k=8, topics=sorted(disclosed) + (["anger"] if wants_anger else []))
            if not (set(h.doc.topics) & set(_CONDITIONS)) or (set(h.doc.topics) & disclosed)]
    # Prefer passages about how words land (abandonment, anger, regulation) over general condition facts.
    landing = {"bpd", "anger", "attachment_reassurance", "emotional_regulation", "communication"}
    hits = sorted(hits, key=lambda h: (-len(set(h.doc.topics) & landing), -h.score))[:3]
    allowed = [h.doc.id for h in hits]
    payload = {"scraps": scraps, "confirmed_meaning": confirmed_meaning, "recipient_name": recipient_name,
               "recipient_profile": recipient_profile, "recipient_signal": recipient_signal, "source_ids": allowed}
    body = "RECIPIENT CHECK-IN SIGNAL (shared with consent; may be null):\n" + json.dumps(recipient_signal) + \
           "\n\nINPUT:\n" + json.dumps({"scraps": scraps, "confirmed_meaning": confirmed_meaning,
                                         "recipient_name": recipient_name}, ensure_ascii=False)
    system, user, ver = _compose("bridge", context, hits, body)
    parsed = _call(provider, LLMRequest("bridge", system, user, payload), BridgeResult)
    data = parsed.model_dump()
    data["source_ids"] = [i for i in data["source_ids"] if i in allowed]
    for w in data["why_this_works"]:
        if w["grounded_in"] == "evidence" and not data["source_ids"]:
            w["grounded_in"] = "general"
    citations = [retriever.get(i).citation() for i in data["source_ids"]]  # type: ignore[union-attr]
    return AIResult("bridge", "ok", provider.live, provider.name, ver, data, citations, crisis, safety=flags)
