"""Communication intelligence engine: orchestrates safety -> context -> evidence ->
prompt -> provider -> validation -> safety for each module."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from .contracts import PartnerAnswer, ReflectionResult, TranslatorResult
from .knowledge.retriever import get_retriever
from .prompts import load_prompt
from .providers import LLMProvider, LLMRequest, ProviderError
from .safety import crisis_payload, screen_input, screen_output

log = logging.getLogger("conveazy.ai")

_CONTRACTS: dict[str, type[BaseModel]] = {
    "translator": TranslatorResult,
    "partner": PartnerAnswer,
    "myself": ReflectionResult,
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
