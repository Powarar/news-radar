import json

import pytest

from app.services.ai import news_chat
from app.services.ai.news_chat import answer_news_query, fetch_news_context


class FakePoint:
    def __init__(self, payload):
        self.payload = payload


class FakeQueryResult:
    def __init__(self, points):
        self.points = points


class FakeQdrantClient:
    def __init__(self, points):
        self.points = points
        self.last_query = None

    def query_points(self, **kwargs):
        self.last_query = kwargs
        return FakeQueryResult(self.points)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = iter(responses)
        self.requests = []
        self.is_closed = False

    def post(self, *args, **kwargs) -> FakeResponse:
        self.requests.append(kwargs)
        return next(self.responses)


def test_fetch_news_context_success(monkeypatch):
    # Mock embedding function
    monkeypatch.setattr(news_chat, "get_text_embedding", lambda x: [0.1, 0.2, 0.3])

    # Setup mock points from Qdrant
    mock_points = [
        FakePoint({
            "title": "Новость 1",
            "summary": "Суть новости 1",
            "published_at": 1718000000
        }),
        FakePoint({
            "title": "Новость 2",
            "text": "Текст новости 2",
            "published_at": 1718000100
        })
    ]
    fake_qdrant = FakeQdrantClient(mock_points)
    monkeypatch.setattr(news_chat, "_get_qdrant_client", lambda: fake_qdrant)

    context, count = fetch_news_context("тестовый запрос", days=3, limit=5)

    assert count == 2
    assert "Новость #1" in context
    assert "Заголовок: Новость 1" in context
    assert "Суть: Суть новости 1" in context
    assert "Новость #2" in context
    assert "Заголовок: Новость 2" in context
    assert "Суть: Текст новости 2" in context
    assert fake_qdrant.last_query["limit"] == 5
    assert fake_qdrant.last_query["score_threshold"] == 0.35


def test_fetch_news_context_empty(monkeypatch):
    monkeypatch.setattr(news_chat, "get_text_embedding", lambda x: [0.1, 0.2, 0.3])
    fake_qdrant = FakeQdrantClient([])
    monkeypatch.setattr(news_chat, "_get_qdrant_client", lambda: fake_qdrant)

    context, count = fetch_news_context("тестовый запрос")
    assert context is None
    assert count == 0


def test_fetch_news_context_error(monkeypatch):
    monkeypatch.setattr(news_chat, "get_text_embedding", lambda x: [0.1, 0.2, 0.3])
    
    class ErrorQdrantClient:
        def query_points(self, **kwargs):
            raise RuntimeError("Qdrant connection error")
            
    monkeypatch.setattr(news_chat, "_get_qdrant_client", lambda: ErrorQdrantClient())
    
    context, count = fetch_news_context("тестовый запрос")
    assert context is None
    assert count == 0


def test_answer_news_query_no_context(monkeypatch):
    # Mock empty context
    monkeypatch.setattr(news_chat, "fetch_news_context", lambda q, days: (None, 0))

    response = answer_news_query("запрос без контекста", days=3)
    assert response.status == "no_context"
    assert response.sources_count == 0
    assert "не найдено" in response.answer


def test_answer_news_query_success(monkeypatch):
    # Mock context
    monkeypatch.setattr(news_chat, "fetch_news_context", lambda q, days: ("Новость 1: подробности", 1))

    # Mock Groq API success response
    fake_http = FakeHttpClient([
        FakeResponse(200, {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Ответ от Groq по новостям."
                }
            }]
        })
    ])
    monkeypatch.setattr(news_chat, "_client", fake_http)
    monkeypatch.setattr(news_chat.settings, "groq_api_key", "mock_key")

    response = answer_news_query("полезный запрос", days=3)
    assert response.status == "ok"
    assert response.sources_count == 1
    assert response.answer == "Ответ от Groq по новостям."
    assert len(fake_http.requests) == 1
    assert fake_http.requests[0]["json"]["model"] == "llama-3.3-70b-versatile"
    assert "reasoning_format" not in fake_http.requests[0]["json"]


def test_answer_news_query_hides_reasoning(monkeypatch):
    monkeypatch.setattr(news_chat, "fetch_news_context", lambda q, days: ("Новость", 1))
    fake_http = FakeHttpClient([
        FakeResponse(200, {
            "choices": [{"message": {"content": "<think>Служебные размышления</think>\nФинальный ответ."}}]
        })
    ])
    monkeypatch.setattr(news_chat, "_client", fake_http)
    monkeypatch.setattr(news_chat.settings, "groq_api_key", "mock_key")

    response = answer_news_query("запрос", days=3)

    assert response.answer == "Финальный ответ."
    assert "think" not in response.answer
    assert "Служебные" not in response.answer


def test_answer_news_query_rejects_echoed_private_context(monkeypatch):
    monkeypatch.setattr(news_chat, "fetch_news_context", lambda q, days: ("Новость", 1))
    fake_http = FakeHttpClient([
        FakeResponse(200, {
            "choices": [{"message": {"content": "КОНТЕКСТ СВЕЖИХ НОВОСТЕЙ:\nсекретный prompt"}}]
        }),
        FakeResponse(200, {
            "choices": [{"message": {"content": "Безопасный финальный ответ."}}]
        }),
    ])
    monkeypatch.setattr(news_chat, "_client", fake_http)
    monkeypatch.setattr(news_chat.settings, "groq_api_key", "mock_key")

    response = answer_news_query("запрос", days=3)

    assert response.answer == "Безопасный финальный ответ."
    assert len(fake_http.requests) == 2


def test_qwen_payload_disables_reasoning():
    payload = news_chat._chat_payload("qwen/qwen3.6-27b", "prompt")

    assert payload["reasoning_effort"] == "none"
    assert payload["reasoning_format"] == "hidden"


def test_answer_news_query_groq_fallback_and_fail(monkeypatch):
    # Mock context
    monkeypatch.setattr(news_chat, "fetch_news_context", lambda q, days: ("Новость 1: подробности", 1))

    # Mock all HTTP calls failing with HTTP status != 200
    # There are 3 fallback models, each retries 2 times (so 3 attempts total per model).
    # That is 3 * 3 = 9 calls total. Let's return 400 for all of them.
    responses = [FakeResponse(400, {"error": "bad request"}) for _ in range(9)]
    fake_http = FakeHttpClient(responses)
    monkeypatch.setattr(news_chat, "_client", fake_http)
    monkeypatch.setattr(news_chat.settings, "groq_api_key", "mock_key")

    # Mock sleep to avoid slow test
    monkeypatch.setattr(news_chat.time, "sleep", lambda x: None)

    response = answer_news_query("запрос с ошибкой", days=3)
    assert response.status == "failed"
    assert response.sources_count == 1
    assert "генерации ответов временно недоступен" in response.answer


def test_get_text_embedding_uses_shared_service(monkeypatch):
    from app.services.ai import embedding

    fake_http = FakeHttpClient([
        FakeResponse(200, {
            "model": "test-model",
            "dimension": 384,
            "embeddings": [[0.1] * 384],
            "cached": [False],
        })
    ])
    monkeypatch.setattr(embedding, "_http_client", fake_http)

    vector = embedding.get_text_embedding("тест")

    assert vector == [0.1] * 384
    assert fake_http.requests[0]["json"] == {"texts": ["тест"]}


def test_get_text_embedding_rejects_wrong_dimension(monkeypatch):
    from app.services.ai import embedding

    fake_http = FakeHttpClient([
        FakeResponse(200, {
            "dimension": 3,
            "embeddings": [[0.1, 0.2, 0.3]],
        })
    ])
    monkeypatch.setattr(embedding, "_http_client", fake_http)

    with pytest.raises(embedding.EmbeddingServiceError, match="dimension mismatch"):
        embedding.get_text_embedding("тест")


def test_index_news_to_qdrant(monkeypatch):
    from app.services.ai import embedding
    
    monkeypatch.setattr(embedding, "get_text_embedding", lambda x: [0.1] * 384)
    
    # Mock QdrantClient
    class MockQdrant:
        def __init__(self):
            self.collection_exists_called = False
            self.create_collection_called = False
            self.upsert_called_with = None
            
        def collection_exists(self, name):
            self.collection_exists_called = True
            return False
            
        def create_collection(self, **kwargs):
            self.create_collection_called = True
            
        def upsert(self, **kwargs):
            self.upsert_called_with = kwargs
            
    mock_client = MockQdrant()
    monkeypatch.setattr(embedding, "_get_qdrant_client", lambda: mock_client)
    
    embedding.index_news_to_qdrant(123, "Тест", "Текст новости", "Саммари", 1718000000)
    
    assert mock_client.collection_exists_called
    assert mock_client.create_collection_called
    assert mock_client.upsert_called_with is not None
    assert mock_client.upsert_called_with["collection_name"] == "news_feed_minilm_384"
    assert mock_client.upsert_called_with["points"][0].id == 123


def test_chat_api_endpoint(monkeypatch):
    from app.api.v1.routes.news import ChatRequest, chat_with_news
    from app.services.ai.news_chat import ChatResponse
    
    # Mock answer_news_query
    monkeypatch.setattr(
        "app.api.v1.routes.news.answer_news_query",
        lambda query, days: ChatResponse(answer="Ответ на: " + query, sources_count=1, status="ok")
    )
    
    # Call endpoint directly
    req = ChatRequest(query="что нового", days=3)
    resp = chat_with_news(req, user=None, _quota=None)
    
    assert resp.answer == "Ответ на: что нового"
    assert resp.sources_count == 1
    assert resp.status == "ok"
