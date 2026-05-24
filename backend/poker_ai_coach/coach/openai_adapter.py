import httpx


class OpenAICompatibleAdapter:
    provider = "openai"

    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if _supports_temperature(self.model):
            payload["temperature"] = 0.2

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()


def _supports_temperature(model: str) -> bool:
    lowered = model.lower()
    reasoning_prefixes = ("gpt-5", "o1", "o3", "o4")
    return not lowered.startswith(reasoning_prefixes)
