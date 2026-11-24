"""Development mock provider.

Deterministic, rule-based output so every screen and test works without API keys.
Every response it produces is labelled `live: false` and shown in the UI as
"Mock mode". It is NOT a language model and is never presented as one.
"""
from __future__ import annotations

import re

from .knowledge.retriever import get_retriever
from .providers import LLMRequest

# (pattern, category, how it may land, replacement or None to drop)
_LEXICON: list[tuple[str, str, str, str | None]] = [
    (r"\byou always\b", "absolute",
     "'Always' can sound like a verdict on who they are, so they may argue with the word instead of hearing the hurt.",
     "it often feels like you"),
    (r"\byou never\b", "absolute",
     "'Never' invites a counter-example ('I did last week!') and pulls focus from what you need.",
     "it feels like you don't"),
    (r"\byou (obviously |clearly )?don'?t (even )?care( about me)?\b", "mind_reading",
     "It tells them what they feel. They may defend their care instead of responding to your hurt.",
     "I'm feeling uncared for"),
    (r"\byou (obviously|clearly) ", "mind_reading",
     "Stating their motives as fact can feel like an accusation they have to disprove.",
     "it seemed to me like you "),
    (r"\bit'?s (all )?your fault\b", "accusatory",
     "Blame tends to trigger defensiveness, which makes repair harder for both of you.",
     "I'm really hurt by what happened"),
    (r"\byou made me\b", "accusatory",
     "It hands them responsibility for your feelings, which they may push back on.",
     "I felt"),
    (r"\bwhy can'?t you (just )?", "accusatory",
     "It can sound like a criticism of their character rather than a request.",
     "could you "),
    (r"\bstop being\b", "accusatory",
     "Labels about how someone 'is' usually land as criticism of who they are.",
     "I'm struggling with"),
    (r"\bcalm down\b", "invalidating",
     "Being told to calm down usually feels like your feelings are the problem, and often has the opposite effect.",
     "can we slow down for a second"),
    (r"\byou'?re (overreacting|being dramatic|too sensitive)\b", "invalidating",
     "It dismisses how they feel, which tends to intensify it.",
     "I'm seeing this differently"),
    (r"\byou'?re (crazy|insane|psycho|pathetic|a joke)\b", "contempt",
     "Name-calling lands as contempt, the pattern most linked to lasting damage in couples research.",
     None),
    (r"\bwhat'?s wrong with you\b", "contempt",
     "It frames them as defective rather than addressing what happened.",
     "I don't understand what happened"),
    (r"\bwhatever\b", "dismissive",
     "It can signal you've stopped listening, even if you're actually overwhelmed.",
     "I need a minute"),
    (r"\bnot my problem\b", "dismissive",
     "It can feel like a door closing on them.",
     "I'm not sure I can help with that part"),
    (r"\bshut up\b", "escalating",
     "Commands like this usually escalate rather than create the quiet you need.",
     "I need us to pause"),
    (r"\bi'?m done\b|\bwe'?re done\b", "escalating",
     "It can sound like you're ending the relationship, which may set off panic rather than a pause.",
     "I need to step away for now"),
    (r"\bi don'?t care( anymore)?\b", "escalating",
     "It can sound like withdrawal of love, even when it's really exhaustion or self-protection.",
     "I'm too worn out to talk about this right now"),
    (r"\bi didn'?t do anything( wrong)?\b", "defensive",
     "Immediate self-defence can make them feel unheard, even if you're right.",
     "I want to understand what hurt you"),
    (r"\b(seriously|really)\?+", "sarcasm",
     "Sarcasm can land as mockery, which tends to stop people from opening up.",
     ""),
    (r"\bthanks a lot\b|\bgreat job\b", "sarcasm",
     "Sarcastic thanks often lands as contempt.",
     ""),
    (r"\bor else\b", "threat",
     "This reads as a threat. Threats make people feel unsafe rather than understood.",
     None),
]

_FEELINGS = {
    "hurt": ["hurt", "hurts", "painful", "stung"],
    "angry": ["angry", "mad", "furious", "pissed", "annoyed"],
    "ignored": ["ignore", "ignored", "ignoring", "left on read", "reply", "replies", "texts", "seen"],
    "lonely": ["alone", "lonely"],
    "anxious": ["anxious", "worried", "scared", "panic"],
    "exhausted": ["tired", "exhausted", "drained", "worn out"],
    "frustrated": ["frustrat", "fed up", "sick of"],
    "disrespected": ["disrespect", "rude", "embarrass"],
    "sad": ["sad", "upset", "crying", "cried"],
}
_NEEDS = {
    "reassurance": ["ignore", "reply", "text", "left on read", "care", "love me", "leave"],
    "clarity": ["why", "plan", "what happened", "confus", "late", "said you would"],
    "space": ["space", "alone", "break", "pause", "step away", "done"],
    "to be listened to": ["listen", "hear me", "interrupt", "talk over"],
    "practical help": ["help", "chores", "dishes", "cook", "clean"],
    "acknowledgement": ["sorry", "apolog", "fault", "blame"],
    "respect": ["disrespect", "rude", "embarrass", "in front of"],
}
_BOUNDARY = re.compile(
    r"\b(i need (some )?space|i (won'?t|will not|can'?t|cannot) (keep|do|accept|be)|please (don'?t|stop)|"
    r"don'?t (yell|shout|call me|talk to me like)|not okay with|i need you to stop)\b",
    re.I,
)


def _detect(words: dict[str, list[str]], text: str) -> list[str]:
    t = text.lower()
    return [k for k, kws in words.items() if any(kw in t for kw in kws)]


def _soften(text: str) -> tuple[str, list[dict], list[dict]]:
    flags, changes, out = [], [], text
    for pat, cat, land, repl in _LEXICON:
        m = re.search(pat, out, re.I)
        if not m:
            continue
        flags.append({"phrase": m.group(0).strip(), "category": cat, "how_it_may_land": land})
        if repl is None:
            out = re.sub(r"[^.!?\n]*" + pat + r"[^.!?\n]*[.!?]?", "", out, flags=re.I)
            changes.append({"what": f"Removed \"{m.group(0).strip()}\"", "why": land})
        else:
            out = re.sub(pat, repl, out, flags=re.I)
            if repl:
                changes.append({"what": f"\"{m.group(0).strip()}\" became \"{repl}\"", "why": land})
            else:
                changes.append({"what": f"Dropped \"{m.group(0).strip()}\"", "why": land})
    out = re.sub(r"!{2,}", "!", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    # Calm down all-caps shouting while keeping the words.
    if sum(c.isupper() for c in out) > 0.5 * max(1, sum(c.isalpha() for c in out)):
        out = out.lower().capitalize()
        changes.append({"what": "Lowered all-caps", "why": "Capitals read as shouting, which can drown out the message."})
    if out and out[-1] not in ".!?":
        out += "."
    out = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out, flags, changes


class MockProvider:
    name = "mock"
    live = False

    def complete_json(self, req: LLMRequest) -> dict:
        return getattr(self, f"_{req.module}")(req.payload)

    # ---------- Message Translator ----------
    def _translator(self, p: dict) -> dict:
        draft: str = p["draft"]
        softened, flags, changes = _soften(draft)
        feelings = _detect(_FEELINGS, draft) or ["upset"]
        needs = _detect(_NEEDS, draft) or ["to be understood"]
        boundary = bool(_BOUNDARY.search(draft))
        threat = any(f["category"] == "threat" for f in flags)
        feel = " and ".join(feelings[:2])
        need = needs[0]
        core = softened or f"I'm feeling {feel} about what happened."

        versions = [
            {"style": "gentle", "text": f"Hey, can I tell you something that's been sitting with me? {core} I'm not trying to start a fight. I just want us to get each other here."},
            {"style": "direct", "text": f"{core} What I need is {need}. Can we talk about it today?"},
            {"style": "emotionally_honest", "text": f"Honestly, I'm feeling {feel} right now. {core} I'm telling you because I'd rather be honest with you than go quiet."},
        ]
        if boundary or threat or "space" in needs:
            versions.append({"style": "boundary", "text": f"I care about us, and I also need to be clear: {core} That part matters to me, and I'm not going to pretend it doesn't."})
        else:
            versions.append({"style": "reassuring", "text": f"I love you and I'm on your side, even right now. {core} I want us to work this out together."})
        if p.get("styles"):
            wanted = set(p["styles"])
            picked = [v for v in versions if v["style"] in wanted]
            versions = picked or versions

        return {
            "intent_summary": f"It sounds like you're feeling {feel} and want {need}. Under the frustration, you're asking to be taken seriously.",
            "feelings_detected": feelings,
            "needs_detected": needs,
            "flags": flags,
            "how_original_may_land": (
                "As written, your partner may hear blame first and your feelings second, so they may defend themselves instead of responding to what you need."
                if flags else
                "Your draft is already fairly clear. The rewrites mostly make your feeling and request easier to spot."
            ),
            "versions": versions,
            "changes": changes or [{"what": "Kept your wording largely intact", "why": "Nothing in it was likely to escalate. We only framed the feeling and the request."}],
            "preserved": ["Your feeling (" + feel + ")", "Your request for " + need] + (["Your boundary"] if boundary else []),
            "boundary_note": "Your boundary is kept in every version. Being kind doesn't mean giving it up." if boundary else (
                "Your draft included a threat, so we didn't polish it. Each version keeps the feeling underneath and states a limit instead." if threat else None),
        }

    # ---------- Understand My Partner ----------
    def _partner(self, p: dict) -> dict:
        retriever = get_retriever()
        hits = [retriever.get(i) for i in p.get("source_ids", [])]
        hits = [h for h in hits if h]
        if not hits:
            return {
                "answer": "Our source library doesn't cover this question yet, so I won't guess at a clinical explanation. The most reliable source here is your partner. Consider asking them what that moment was like for them, when you're both calm.",
                "evidence": [{"claim": "How a specific person experiences a situation can't be inferred from general information.", "level": "individual", "source_ids": []}],
                "what_cannot_be_inferred": "Why your partner, specifically, reacted the way they did.",
                "try_this": ["Ask with curiosity, not as a cross-examination: \"What was going on for you when that happened?\""],
                "avoid": ["Filling the gap with the worst-case explanation."],
                "ask_your_partner": ["What helps you most when you feel like that?"],
                "professional_help_note": None,
            }
        paras = []
        for d in hits[:3]:
            first = " ".join(re.split(r"(?<=[.!?])\s+", d.text)[:2])
            paras.append(f"{d.publisher} notes: {first}")
        topics = {t for d in hits for t in d.topics}
        try_this = ["Name what you noticed and ask, rather than assume: \"I noticed you went quiet. Are you okay, or do you need some time?\""]
        avoid = ["Explaining their reaction to them (\"you're only upset because...\")."]
        if topics & {"attachment_reassurance", "withdrawal"}:
            try_this.append("If you need space, say when you'll be back. A specific time makes the gap feel safe.")
            avoid.append("Going silent without a word. To an anxious mind, silence often gets filled with rejection.")
        if topics & {"validation", "emotional_regulation", "bpd"}:
            try_this.append("Validate the feeling before discussing the facts: \"I can see this really hurt.\" You don't have to agree to validate.")
        if topics & {"boundaries", "supporting_partner"}:
            try_this.append("State boundaries as what you will do: \"I'll take twenty minutes and come back,\" not \"you need to stop.\"")
            avoid.append("Becoming their only support. It's caring to encourage other support, including professional care.")
        return {
            "answer": "\n\n".join(paras) + "\n\nThese are general patterns. They describe what can happen, not what is happening for your partner.",
            "evidence": [
                {"claim": re.split(r"(?<=[.!?])\s+", d.text)[0], "level": d.evidence_level, "source_ids": [d.id]} for d in hits[:4]
            ] + [{"claim": "What your partner experiences in a specific moment is individual and best learned by asking them.", "level": "individual", "source_ids": []}],
            "what_cannot_be_inferred": "Whether any of this applies to your partner, or why they reacted the way they did in a particular moment. A diagnosis, if there is one, doesn't tell you that.",
            "try_this": try_this[:5],
            "avoid": avoid[:5],
            "ask_your_partner": ["When that happens, what's it like on your side?", "What helps you feel reassured, and what makes it worse?"],
            "professional_help_note": "If this pattern is frequent or painful for either of you, a couples therapist or the clinician supporting your partner can help you both build shared tools.",
        }

    # ---------- Understand Myself ----------
    def _myself(self, p: dict) -> dict:
        situation = p.get("situation", "").strip()
        interp = p.get("interpretation", "").strip() or "You haven't named an interpretation yet."
        emotions = p.get("emotions") or _detect(_FEELINGS, situation + " " + interp) or ["unsettled"]
        needs = p.get("needs") or _detect(_NEEDS, situation + " " + interp) or ["clarity"]
        feel = ", ".join(emotions)
        need = " and ".join(needs[:2])
        return {
            "situation": situation[:780] or "You described a moment that stayed with you.",
            "interpretation": f"The meaning you took from it: \"{interp[:700]}\"",
            "evidence_check": "Ask yourself which parts of that meaning you saw or heard directly, and which parts filled a gap, such as their silence, tone or timing. Gaps are usually where the most painful meanings get written in.",
            "alternative_interpretations": [
                "They were caught up in something unrelated and didn't realise how it landed.",
                "They were overwhelmed themselves and pulled back to cope.",
                "Your interpretation may be partly right. It's worth asking rather than guessing.",
            ],
            "emotions": emotions,
            "validation": f"Feeling {feel} makes sense given what this meant to you. The feeling is real, even while the meaning is still being checked.",
            "possible_needs": needs,
            "communication": f"\"When {situation[:120].rstrip('.') or 'that happened'}, I felt {feel}. I might be reading it wrong, but I'd really like {need}. Can we talk about it?\"",
            "escalation_signs": ["Replaying the moment again and again", "Drafting messages in your head that start with 'you always'", "Feeling an urgent need to resolve it right now"],
            "next_step": "If your intensity is 7 or higher, take twenty minutes for something calming before you send anything. Otherwise, try the message above in the Translator.",
        }
