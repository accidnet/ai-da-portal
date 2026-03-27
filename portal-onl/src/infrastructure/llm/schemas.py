from pydantic import BaseModel, Field


class StructuredPrompt(BaseModel):
    system: str
    user: str
    tools: list[str] = Field(default_factory=list)
