from poker_ai_coach.coach.openai_adapter import OpenAICompatibleAdapter


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "Coach response"}}]}


def test_openai_adapter_omits_temperature_for_gpt5_models(monkeypatch):
    captured_payload = {}

    def fake_post(url, headers, json, timeout):
        captured_payload.update(json)
        return FakeResponse()

    monkeypatch.setattr("poker_ai_coach.coach.openai_adapter.httpx.post", fake_post)
    adapter = OpenAICompatibleAdapter(api_key="test-key", model="gpt-5-mini")

    content = adapter.complete("system", "user")

    assert content == "Coach response"
    assert captured_payload["model"] == "gpt-5-mini"
    assert "temperature" not in captured_payload


def test_openai_adapter_keeps_temperature_for_classic_chat_models(monkeypatch):
    captured_payload = {}

    def fake_post(url, headers, json, timeout):
        captured_payload.update(json)
        return FakeResponse()

    monkeypatch.setattr("poker_ai_coach.coach.openai_adapter.httpx.post", fake_post)
    adapter = OpenAICompatibleAdapter(api_key="test-key", model="gpt-4o-mini")

    content = adapter.complete("system", "user")

    assert content == "Coach response"
    assert captured_payload["model"] == "gpt-4o-mini"
    assert captured_payload["temperature"] == 0.2
