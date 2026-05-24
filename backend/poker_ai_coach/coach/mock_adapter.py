class MockCoachAdapter:
    provider = "mock"
    model = "mock"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if "User question:" in user_prompt and "Provided context JSON:" in user_prompt:
            return (
                "Main answer: mock coach chat is grounded in the selected context.\n"
                "Evidence: the request included predefined report or hand context only.\n"
                "Next step: ask about one leak, one selected hand, or the weekly drill.\n"
                "Confidence level: low, mock response.\n"
                "Missing data: real AI is disabled or not configured."
            )

        if "Selected hand metadata" in user_prompt:
            return (
                "Main leak: needs review.\n"
                "Evidence: selected historical hand text was provided, but mock mode does not "
                "infer strategy.\n"
                "Why it matters: microstakes MTT profit comes from simple exploitative decisions.\n"
                "Specific hands to review: the selected hand ID from the request.\n"
                "One drill: mark the street where the pot became big and write the value target.\n"
                "Confidence level: low, mock response.\n"
                "Missing data: real AI is disabled or not configured."
            )

        return (
            "Main leak: no proven leak in mock mode.\n"
            "Evidence: overview report JSON was provided, but mock mode avoids inventing stats.\n"
            "Why it matters: microstakes MTT review should start from sample size "
            "and data quality.\n"
            "Specific hands to review: use selected review hands.\n"
            "One drill: review marked all-in and import-error hands after each session.\n"
            "Confidence level: low, mock response.\n"
            "Missing data: real AI is disabled or not configured."
        )
