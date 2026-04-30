from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    doc_id: str
    title: str | None = None
    url: str | None = None
    category: str | None = None
    similarity: float


class Message(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    sources: list[Source] | None = None


class Conversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversationId: str
    message: Message


class SessionRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    client_user_id: str | None = None


class SessionResponse(BaseModel):
    user_id: str
    display_name: str
