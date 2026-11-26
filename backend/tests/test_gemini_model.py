import httpx

from app.ai import providers
from app.ai.providers import GeminiProvider, LLMRequest, pick_gemini_model
from app.config import Settings


def _m(name, methods=("generateContent",)):
    return {"name": f"models/{name}", "supportedGenerationMethods": list(methods)}


def test_pick_prefers_latest_alias_then_newest_stable_flash():
    models = [_m("gemini-2.0-flash"), _m("gemini-3.0-flash"), _m("gemini-3.5-flash-preview-05"),
              _m("gemini-3.0-flash-lite"), _m("gemini-3.0-pro"), _m("text-embedding-004", ("embedContent",))]
    assert pick_gemini_model(models) == "gemini-3.0-flash"
    assert pick_gemini_model(models + [_m("gemini-flash-latest")]) == "gemini-flash-latest"
    assert pick_gemini_model([_m("gemini-3.0-pro")]) is None


def test_404_switches_to_discovered_model_and_remembers(monkeypatch):
    providers._gemini_model_swap.clear()
    posted = []

    def fake_post(url, **kw):
        posted.append(url)
        req = httpx.Request("POST", url)
        if "gemini-old" in url:
            return httpx.Response(404, request=req)
        body = {"candidates": [{"content": {"parts": [{"thought": True, "text": "hmm"}, {"text": '{"ok": 1}'}]}}]}
        return httpx.Response(200, json=body, request=req)

    def fake_get(url, **kw):
        return httpx.Response(200, json={"models": [_m("gemini-9.0-flash")]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setattr(providers.httpx, "get", fake_get)
    p = GeminiProvider(Settings(_env_file=None, gemini_api_key="k", gemini_model="gemini-old"))
    req = LLMRequest("bridge", "s", "u", {})
    assert p.complete_json(req) == {"ok": 1}
    assert p.complete_json(req) == {"ok": 1}
    assert [u.split("/models/")[1].split(":")[0] for u in posted] == ["gemini-old", "gemini-9.0-flash", "gemini-9.0-flash"]
    providers._gemini_model_swap.clear()
