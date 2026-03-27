from infrastructure.llm.schemas import StructuredPrompt


class LlmClient:
    def generate(self, prompt: StructuredPrompt) -> str:
        return f"Stubbed response for tool set: {', '.join(prompt.tools) or 'none'}"
