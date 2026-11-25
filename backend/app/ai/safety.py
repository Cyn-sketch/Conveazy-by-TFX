"""Safety gate that runs before and after every AI call.

Input checks:  crisis language, danger/abuse disclosures, requests to manipulate a partner.
Output checks: diagnosis, medication/treatment advice, certainty about a partner's mind.

Pattern matching is deliberately conservative (it prefers false positives for crisis).
It is a floor, not a clinical screening tool; live providers get the same rules in the prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

CrisisLevel = Literal["none", "concern", "urgent"]

_URGENT = [
    r"\b(kill|hang|shoot|drown)\s+my\s*self\b",
    r"\bkill(ing)?\s+myself\b",
    r"\bend(ing)?\s+(my|it)\s+(life|all)\b",
    r"\b(want|going|plan(ning)?)\s+to\s+die\b",
    r"\bsuicid(e|al)\b",
    r"\btake\s+my\s+(own\s+)?life\b",
    r"\b(overdos(e|ing)|od\s+on)\b",
    r"\bno\s+reason\s+to\s+live\b",
    r"\bbetter\s+off\s+(dead|without\s+me)\b",
    r"\b(cut|cutting|hurt|hurting|harm|harming)\s+my\s*self\b",
    r"\bself[-\s]?harm",
    r"\b(he|she|they|partner)\s+(hit|hits|choked|chokes|strangled|beat|beats|punched)\s+me\b",
    r"\b(threaten(ed|s)?\s+to\s+kill)\b",
    r"\bafraid\s+(he|she|they)('ll| will| might)\s+(hurt|kill)\b",
    r"\bi('m| am)\s+(going|gonna)\s+to\s+(hurt|kill)\s+(him|her|them)\b",
]
_CONCERN = [
    r"\bcan'?t\s+(go\s+on|do\s+this\s+anymore|take\s+it\s+anymore)\b",
    r"\bwish\s+i\s+(was|were)n'?t\s+(here|alive)\b",
    r"\bdisappear\s+forever\b",
    r"\bhopeless\b",
    r"\bnot\s+safe\b",
    r"\bscared\s+of\s+(him|her|them|my\s+partner)\b",
    r"\b(controls?|checks?)\s+my\s+(phone|money|location)\b",
]
_MANIPULATION = [
    r"\bmake\s+(him|her|them)\s+(feel\s+)?(guilty|jealous|insecure|worthless)\b",
    r"\b(punish|manipulate|control|trap|guilt[-\s]?trip)\s+(him|her|them|my\s+partner)\b",
    r"\buse\s+(his|her|their)\s+(bpd|depression|anxiety|diagnosis|trauma|insecurit\w+)\s+against\b",
    r"\bso\s+(he|she|they)\s+(can'?t|won'?t)\s+leave\b",
    r"\bget\s+(him|her|them)\s+to\s+stop\s+seeing\s+(friends|family)\b",
]
_THREAT = [
    r"\bor\s+else\b",
    r"\bi('ll| will)\s+(hurt|destroy|ruin|expose)\s+you\b",
    r"\byou('ll| will)\s+regret\b",
    r"\bi('ll| will)\s+(kill|hurt)\s+(you|myself)\s+if\b",
]

_DIAGNOSIS = [
    r"\b(your partner|they|he|she|you)\s+(clearly\s+|probably\s+|definitely\s+)?(has|have|is|are)\s+"
    r"(bpd|borderline|bipolar|npd|narcissis\w*|depress(ed|ion)\s+disorder|an?\s+personality\s+disorder|adhd|ptsd)\b",
    r"\b(this|that)\s+is\s+(a\s+)?(classic|typical)\s+(bpd|borderline|narcissis\w*)\b",
    r"\bsounds\s+like\s+(bpd|borderline|bipolar|narcissis\w*|npd)\b",
]
_MEDICATION = [
    r"\b(stop|start|increase|decrease|reduce|double|skip|taper)\s+(taking\s+)?(your|their|his|her)?\s*"
    r"(medication|meds|dose|dosage|antidepressant|ssri|pills?)\b",
    r"\b\d+\s?mg\b",
    r"\b(you|they)\s+should\s+(take|try)\s+(an?\s+)?(ssri|antidepressant|benzodiazepine|medication)\b",
]
_CERTAINTY = [
    r"\b(your partner|they|he|she)\s+(definitely|certainly|obviously)\s+(feels?|thinks?|wants?|meant)\b",
]


def _any(patterns: list[str], text: str) -> list[str]:
    t = text.lower()
    return [m.group(0) for p in patterns for m in [re.search(p, t)] if m]


@dataclass
class InputScreen:
    crisis: CrisisLevel = "none"
    manipulation: bool = False
    threat: bool = False
    matched: list[str] = field(default_factory=list)

    def as_flags(self) -> dict:
        return {"crisis": self.crisis, "manipulation": self.manipulation, "threat": self.threat}


def screen_input(*texts: str | None) -> InputScreen:
    joined = " \n ".join(t for t in texts if t)
    res = InputScreen()
    urgent, concern = _any(_URGENT, joined), _any(_CONCERN, joined)
    if urgent:
        res.crisis = "urgent"
    elif concern:
        res.crisis = "concern"
    res.manipulation = bool(_any(_MANIPULATION, joined))
    res.threat = bool(_any(_THREAT, joined))
    res.matched = urgent + concern
    return res


@dataclass
class OutputScreen:
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


# Condition words a person may have disclosed about themselves (keys match engine._CONDITIONS).
_CONDITION_TERMS = {"bpd": ("bpd", "borderline"), "depression": ("depress",), "gad": ("anxiety", "gad"), "pcos": ("pcos",)}


def screen_output(text: str, disclosed: set[str] | frozenset[str] = frozenset()) -> OutputScreen:
    """`disclosed`: conditions the person shared about themselves. Restating those isn't diagnosing;
    naming anything else still is."""
    v = []
    allowed = tuple(t for k in disclosed for t in _CONDITION_TERMS.get(k, ()))
    if [m for m in _any(_DIAGNOSIS, text) if not (allowed and any(t in m for t in allowed))]:
        v.append("diagnosis")
    if _any(_MEDICATION, text):
        v.append("medication")
    if _any(_CERTAINTY, text):
        v.append("certainty_about_partner")
    return OutputScreen(v)


CRISIS_RESOURCES = [
    {"region": "Anywhere", "name": "Local emergency services", "contact": "Your local emergency number (112 in India and the EU, 911 in the US, 999 in the UK)"},
    {"region": "India", "name": "Tele-MANAS (Government of India, 24x7)", "contact": "14416 or 1-800-891-4416"},
    {"region": "United States", "name": "988 Suicide & Crisis Lifeline", "contact": "Call or text 988"},
    {"region": "United Kingdom & Ireland", "name": "Samaritans", "contact": "116 123"},
    {"region": "Elsewhere", "name": "Find a Helpline", "contact": "https://findahelpline.com"},
]


def crisis_payload(level: CrisisLevel) -> dict:
    if level == "urgent":
        message = (
            "What you wrote sounds really serious, and you deserve support from a person right now. "
            "If you or someone else might be in danger, please contact emergency services or one of the "
            "lines below. If you can, reach out to someone you trust and let them know how you're doing. "
            "CONVEAZY can't respond to emergencies, but you don't have to handle this alone."
        )
    else:
        message = (
            "It sounds like things feel very heavy right now. If it would help to talk to someone, the "
            "lines below are free and confidential. A therapist or doctor can also help you with this."
        )
    return {"level": level, "message": message, "resources": CRISIS_RESOURCES}
