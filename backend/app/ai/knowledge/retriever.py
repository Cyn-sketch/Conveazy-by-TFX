"""Evidence-based knowledge engine: semantic-ish retrieval over vetted sources.

Phase 1 ships an in-process TF-IDF vector retriever so the app works with zero external
services. The `Retriever` protocol is the seam for Phase 2, where embeddings move into
Postgres with pgvector (see docs/ARCHITECTURE.md). Clinical knowledge lives here only;
personal relationship context never enters this index.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

_CORPUS = Path(__file__).with_name("corpus.json")
_STOP = set(
    "a an the and or but if of to in on at for with by from as is are was were be been being it its this that "
    "these those i you he she they we me him her them my your his their our do does did not no so can could "
    "would should may might will just than then there here what why how when who which about into over more "
    "most some any very".split()
)
# Lightweight synonym expansion so lay questions find clinical passages.
_SYNONYMS = {
    "silence": ["withdrawal", "distance", "stonewalling", "rejection"],
    "silent": ["withdrawal", "distance", "stonewalling"],
    "withdraw": ["withdrawal", "stonewalling", "flooding"],
    "withdraws": ["withdrawal", "stonewalling", "flooding"],
    "reassurance": ["abandonment", "attachment", "anxiety", "worry"],
    "intense": ["intensely", "emotions", "regulate", "dysregulation"],
    "intensely": ["intense", "emotions", "regulate"],
    "react": ["reactions", "emotions", "regulate"],
    "overwhelmed": ["flooded", "flooding", "dysregulation", "break"],
    "boundaries": ["boundary", "limits"],
    "boundary": ["boundaries", "limits"],
    "fight": ["conflict", "argument"],
    "argue": ["conflict", "argument"],
    "disagreements": ["conflict"],
    "angry": ["anger", "irritability", "emotions"],
    "sad": ["depression", "mood"],
    "hormones": ["pcos", "hormonal"],
    "hormonal": ["pcos"],
    "say": ["communication", "messages"],
    "support": ["supporting", "care"],
    "responsible": ["responsibility", "treatment", "boundaries"],
    "rage": ["anger", "angry", "control"],
    "anger": ["angry", "control"],
    "triggered": ["anger", "abandonment"],
    "borderline": ["bpd"],
    "bpd": ["borderline", "abandonment"],
    "pcos": ["hormonal", "polycystic"],
    "depressed": ["depression"],
    "anxiety": ["anxious", "worry", "gad"],
}


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    publisher: str
    url: str
    kind: str
    evidence_level: str
    topics: tuple[str, ...]
    text: str

    def citation(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "publisher": self.publisher,
            "url": self.url,
            "kind": self.kind,
            "evidence_level": self.evidence_level,
        }


@dataclass(frozen=True)
class Hit:
    doc: Document
    score: float


class Retriever(Protocol):
    def search(self, query: str, k: int = 4, topics: list[str] | None = None) -> list[Hit]: ...
    def get(self, doc_id: str) -> Document | None: ...


def _tokens(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2]
    out = list(words)
    for w in words:
        out.extend(_SYNONYMS.get(w, []))
    return out


class TfidfRetriever:
    def __init__(self, docs: list[Document]):
        self.docs = docs
        self._by_id = {d.id: d for d in docs}
        tokenised = [_tokens(f"{d.title} {d.text} {' '.join(d.topics)}") for d in docs]
        df = Counter(t for toks in tokenised for t in set(toks))
        n = len(docs)
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
        self.vectors = [self._vec(toks) for toks in tokenised]

    def _vec(self, toks: list[str]) -> dict[str, float]:
        tf = Counter(toks)
        v = {t: c * self.idf.get(t, 0.0) for t, c in tf.items() if t in self.idf}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, query: str, k: int = 4, topics: list[str] | None = None) -> list[Hit]:
        q = self._vec(_tokens(query))
        hits = []
        for doc, vec in zip(self.docs, self.vectors):
            score = sum(w * vec.get(t, 0.0) for t, w in q.items())
            if topics and set(topics) & set(doc.topics):
                score += 0.15
            if score > 0.05:
                hits.append(Hit(doc, round(score, 4)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def get(self, doc_id: str) -> Document | None:
        return self._by_id.get(doc_id)


def load_documents(path: Path = _CORPUS) -> list[Document]:
    raw = json.loads(path.read_text())
    return [
        Document(**{**d, "topics": tuple(d["topics"])})
        for d in raw["documents"]
    ]


@lru_cache
def get_retriever() -> Retriever:
    return TfidfRetriever(load_documents())


def corpus_meta() -> dict:
    return json.loads(_CORPUS.read_text())["_meta"]
