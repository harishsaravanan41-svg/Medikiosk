from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatCompletionRequest(BaseModel):
    message: Optional[str] = Field(
        default=None,
        description="The prompt or question to send to the Qwen model."
    )
    messages: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Structured list of conversation turns."
    )
    system_prompt: Optional[str] = None
    max_new_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

class ChatCompletionResponse(BaseModel):
    response: str
    success: bool = True
    answer: str

class HealthResponse(BaseModel):
    status: str = "ok"
    model: str = "qwen-2.5"

class ErrorResponse(BaseModel):
    success: bool = False
    detail: str
