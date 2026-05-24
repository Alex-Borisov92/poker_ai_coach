from typing import Protocol


class CoachAdapter(Protocol):
    provider: str
    model: str | None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return a coach response for prepared prompts."""
