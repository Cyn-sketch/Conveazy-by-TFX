import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import engine
from ..ai.context import build_personal_context
from ..ai.knowledge.retriever import corpus_meta, get_retriever
from ..ai.providers import get_provider
from ..db import get_db
from ..deps import ai_rate_limit, current_user
from ..models import Conversation, Message, User
from ..schemas import AskIn, ReflectIn, TranslateIn
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
