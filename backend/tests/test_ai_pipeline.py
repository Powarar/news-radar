import json

import httpx

from app.services.ai import pipeline


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = iter(responses)
        self.requests: list[dict] = []
        self.is_closed = False

    def post(self, *_args, **kwargs) -> FakeResponse:
        self.requests.append(kwargs)
        return next(self.responses)


def groq_response(content: str) -> FakeResponse:
    return FakeResponse(
        200,
        {"choices": [{"message": {"content": content}}]},
    )


def test_process_uses_json_mode_and_validates_topics(monkeypatch):
    fake = FakeClient([
        groq_response(json.dumps({
            "topics": {
                "technology": 0.9,
                "unknown": 0.8,
                "sports": 1.4,
                "culture": 0.1,
            },
            "summary": "Это достаточно длинное тестовое предложение для проверки ограничения количества слов в итоговом кратком описании новости моделью.",
        }))
    ])
    monkeypatch.setattr(pipeline.settings, "groq_api_key", "test")
    monkeypatch.setattr(pipeline, "_client", fake)

    topics, summary, status = pipeline.process("Test article", news_id=7)

    assert topics == {"technology": 0.9}
    assert status == "ok"
    assert summary is not None
    assert len(summary.rstrip("…").split()) <= 15
    assert fake.requests[0]["json"]["response_format"] == {"type": "json_object"}


def test_invalid_json_uses_keyword_fallback(monkeypatch):
    fake = FakeClient([groq_response("not-json")])
    monkeypatch.setattr(pipeline.settings, "groq_api_key", "test")
    monkeypatch.setattr(pipeline, "_client", fake)
    monkeypatch.setattr(
        pipeline,
        "classify_keywords",
        lambda _text: {"technology": 0.5},
    )

    topics, summary, status = pipeline.process("Test article")

    assert topics == {"technology": 0.5}
    assert summary is None
    assert status == "failed"


def test_rate_limit_retries_using_retry_after(monkeypatch):
    fake = FakeClient([
        FakeResponse(429, {"error": {}}, headers={"retry-after": "2"}),
        groq_response(json.dumps({
            "topics": {"business": 0.8},
            "summary": "Короткое тестовое резюме.",
        })),
    ])
    sleeps: list[float] = []
    monkeypatch.setattr(pipeline.settings, "groq_api_key", "test")
    monkeypatch.setattr(pipeline, "_client", fake)
    monkeypatch.setattr(pipeline.time, "sleep", sleeps.append)

    topics, _summary, status = pipeline.process("Test article")

    assert topics == {"business": 0.8}
    assert status == "ok"
    assert sleeps == [2.0]


def test_network_errors_retry_each_fallback_once(monkeypatch):
    class FailingClient:
        is_closed = False

        def __init__(self):
            self.calls = 0

        def post(self, *_args, **_kwargs):
            self.calls += 1
            raise httpx.ConnectError("offline")

    fake = FailingClient()
    sleeps: list[float] = []
    monkeypatch.setattr(pipeline.settings, "groq_api_key", "test")
    monkeypatch.setattr(pipeline, "_client", fake)
    monkeypatch.setattr(pipeline.time, "sleep", sleeps.append)
    monkeypatch.setattr(pipeline, "classify_keywords", lambda _text: {})

    topics, summary, status = pipeline.process("Test article")

    assert fake.calls == 4
    assert sleeps == [1.0, 1.0]
    assert (topics, summary, status) == ({}, None, "failed")


def test_auth_error_does_not_try_other_models(monkeypatch):
    fake = FakeClient([FakeResponse(401, {"error": {"message": "bad key"}})])
    monkeypatch.setattr(pipeline.settings, "groq_api_key", "test")
    monkeypatch.setattr(pipeline, "_client", fake)
    monkeypatch.setattr(pipeline, "classify_keywords", lambda _text: {})

    assert pipeline.process("Test article") == ({}, None, "failed")
    assert len(fake.requests) == 1
