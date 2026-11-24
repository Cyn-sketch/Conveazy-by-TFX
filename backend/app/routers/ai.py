import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import engine
from ..ai.context import PROFILE_FIELDS, _entries, build_personal_context, partner_checkin_signal, partner_of
from ..ai.knowledge.retriever import corpus_meta, get_retriever
from ..ai.providers import get_provider
from ..db import get_db
from ..deps import ai_rate_limit, current_user
from ..models import Conversation, Message, User
from ..schemas import AskIn, BridgeIn, ReflectIn, TranslateIn
from ..security import decrypt, encrypt

router = APIRouter(prefix="/api", tags=["ai"])


def _meta(r: engine.AIResult) -> dict:
    return {"live": r.live, "provider": r.provider, "prompt_version": r.prompt_version, "status": r.status, "safety": r.safety}


def _save(db: Session, conv: Conversation, user_text: str, r: engine.AIResult) -> None:
    db.add(Message(conversation_id=conv.id, role="user", content_enc=encrypt(user_text), meta={}))
    payload = {"result": r.result, "citations": r.citations, "crisis": r.crisis, "notice": r.notice}
    db.add(Message(conversation_id=conv.id, role="assistant", content_enc=encrypt(json.dumps(payload)), meta=_meta(r)))
    db.commit()


@router.get("/ai/status")
def status(user: User = Depends(current_user)):
    p = get_provider()
    return {"provider": p.name, "live": p.live,
            "label": "Live AI" if p.live else "Mock mode: rule-based responses for development, not a language model"}


@router.get("/knowledge/sources")
def sources(user: User = Depends(current_user)):
    r = get_retriever()
    return {"meta": corpus_meta(), "sources": [d.citation() | {"topics": list(d.topics)} for d in r.docs]}  # type: ignore[attr-defined]


@router.post("/translate")
def translate(body: TranslateIn, db: Session = Depends(get_db), user: User = Depends(ai_rate_limit)):
    ctx = build_personal_context(db, user)
    r = engine.translate(get_provider(), draft=body.draft, styles=body.styles, context=ctx, audience_note=body.note)
    if body.save and user.save_history and r.status == "ok":
        conv = Conversation(user_id=user.id, module="translator", title=body.draft[:60])
        db.add(conv)
        db.flush()
        _save(db, conv, body.draft, r)
    return r.to_dict()


@router.post("/partner/ask")
def ask(body: AskIn, db: Session = Depends(get_db), user: User = Depends(ai_rate_limit)):
    conv = None
    history: list[dict] = []
    if body.conversation_id:
        conv = db.scalar(select(Conversation).where(Conversation.id == body.conversation_id,
                                                    Conversation.user_id == user.id, Conversation.module == "partner"))
        if not conv:
            raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found."})
        for m in conv.messages[-8:]:
            text = decrypt(m.content_enc) or ""
            if m.role == "assistant":
                try:
                    text = (json.loads(text).get("result") or {}).get("answer", "")
                except json.JSONDecodeError:
                    text = ""
            history.append({"role": m.role, "content": text[:1500]})
    ctx = build_personal_context(db, user)
    r = engine.ask_partner(get_provider(), question=body.question, history=history, context=ctx)
    out = r.to_dict()
    if user.save_history:
        if not conv:
            conv = Conversation(user_id=user.id, module="partner", title=body.question[:80])
            db.add(conv)
            db.flush()
        _save(db, conv, body.question, r)
        out["conversation_id"] = conv.id
    return out


@router.post("/myself/reflect")
def reflect(body: ReflectIn, db: Session = Depends(get_db), user: User = Depends(ai_rate_limit)):
    ctx = build_personal_context(db, user)
    r = engine.reflect(get_provider(), situation=body.situation, interpretation=body.interpretation,
                       emotions=body.emotions, needs=body.needs, intensity=body.intensity, context=ctx)
    out = r.to_dict()
    if body.save and user.save_history and r.status == "ok":
        conv = Conversation(user_id=user.id, module="myself", title=body.situation[:80])
        db.add(conv)
        db.flush()
        _save(db, conv, json.dumps(body.model_dump(exclude={"save"})), r)
        out["conversation_id"] = conv.id
    return out


@router.get("/conversations")
def list_conversations(module: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Conversation).where(Conversation.user_id == user.id)
    if module:
        q = q.where(Conversation.module == module)
    rows = db.scalars(q.order_by(Conversation.created_at.desc()).limit(100))
    return {"conversations": [{"id": c.id, "module": c.module, "title": c.title, "created_at": c.created_at.isoformat()} for c in rows]}


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.scalar(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    if not c:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found."})
    msgs = []
    for m in c.messages:
        raw = decrypt(m.content_enc) or ""
        msgs.append({"role": m.role, "meta": m.meta, "created_at": m.created_at.isoformat(),
                     "content": json.loads(raw) if m.role == "assistant" else raw})
    return {"id": c.id, "module": c.module, "title": c.title, "messages": msgs}


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = db.scalar(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    if not c:
        raise HTTPException(404, detail={"code": "not_found", "message": "Conversation not found."})
    db.delete(c)
    db.commit()


@router.post("/bridge")
def bridge(body: BridgeIn, db: Session = Depends(get_db), user: User = Depends(ai_rate_limit)):
    """Say it to them: understand the sender's scraps, then write for the recipient's own profile."""
    partner = partner_of(db, user.id)
    recipient_profile = _entries(db, partner.id, require_shared=True) if partner else {}
    signal = partner_checkin_signal(db, partner) if partner else None
    ctx = build_personal_context(db, user)
    r = engine.bridge(get_provider(), scraps=body.scraps, confirmed_meaning=body.confirmed_meaning, context=ctx,
                      recipient_name=partner.display_name if partner else "your partner",
                      recipient_profile=recipient_profile, recipient_signal=signal)
    out = r.to_dict()
    out["recipient"] = {"name": partner.display_name if partner else None, "profile_items_used": len(recipient_profile),
                        "checkin_signal": signal is not None}
    if body.save and user.save_history and r.status == "ok":
        conv = Conversation(user_id=user.id, module="bridge", title=body.scraps[:80])
        db.add(conv)
        db.flush()
        _save(db, conv, body.scraps, r)
    return out


@router.get("/knowledge/videos")
def videos(user: User = Depends(current_user)):
    import json as _json
    from pathlib import Path
    data = _json.loads((Path(__file__).resolve().parent.parent / "ai" / "knowledge" / "youtube.json").read_text())
    return data
