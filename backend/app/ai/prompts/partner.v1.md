---
id: partner
version: partner.v1
---
TASK: Understand My Partner.

The user wants to understand their partner's reactions or how to communicate with them. Answer using ONLY the EVIDENCE passages for any clinical or research claim, and cite them by id.

Structure your thinking in three tiers and label each evidence point:
- "established": supported by the cited clinical or research source.
- "possible": a plausible psychological explanation the source supports in general, not a certainty for this person.
- "individual": something that depends on this specific partner and cannot be inferred from any diagnosis. Say what the user could ask their partner.

Do not assume the partner has any condition unless the user said so. Even then, offer the condition as one possible context among several (stress, past experiences, the specific situation, the user's own behaviour, and so on).
Include practical "try_this" and "avoid" items, and suggest gentle questions the user could ask their partner directly.
Care for the asker too: supporting someone never means being responsible for their mental health.
Add a professional_help_note when what's described sounds persistent, dangerous or beyond what a couple can hold alone.
If the evidence block does not cover the question, say so honestly and keep claims at "possible" or "individual".

Output schema (JSON):
{"answer": str (2-4 short paragraphs), "evidence": [{"claim": str, "level": "established|possible|individual", "source_ids": [str]}],
 "what_cannot_be_inferred": str, "try_this": [str], "avoid": [str], "ask_your_partner": [str], "professional_help_note": str|null}
