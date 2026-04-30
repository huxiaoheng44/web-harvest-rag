from app.schemas.chat import Conversation, Message, Source
from app.services.clients import get_supabase_client


def make_title(input_text: str | None) -> str:
    base = " ".join((input_text or "New chat").strip().split())
    return f"{base[:57]}..." if len(base) > 60 else base


def list_conversations(user_id: str) -> list[Conversation]:
    result = (
        get_supabase_client()
        .from_("conversations")
        .select("id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return [Conversation(**item) for item in (result.data or [])]


def create_conversation(user_id: str, title: str | None = None) -> Conversation:
    result = (
        get_supabase_client()
        .from_("conversations")
        .insert({"user_id": user_id, "title": make_title(title)})
        .select("id, title, created_at, updated_at")
        .single()
        .execute()
    )
    return Conversation(**result.data)


def delete_conversation(user_id: str, conversation_id: str) -> None:
    (
        get_supabase_client()
        .from_("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )


def get_messages(user_id: str, conversation_id: str) -> list[Message]:
    conversation = (
        get_supabase_client()
        .from_("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not conversation.data:
        raise ValueError("Conversation not found")

    result = (
        get_supabase_client()
        .from_("messages")
        .select("id, role, content, created_at, sources")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return [Message(**item) for item in (result.data or [])]


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list[Source] | None = None,
) -> Message:
    payload = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }
    if sources is not None:
        payload["sources"] = [source.model_dump() for source in sources]

    result = (
        get_supabase_client()
        .from_("messages")
        .insert(payload)
        .select("id, role, content, created_at, sources")
        .single()
        .execute()
    )
    return Message(**result.data)


def update_new_chat_title(user_id: str, conversation_id: str, question: str) -> None:
    (
        get_supabase_client()
        .from_("conversations")
        .update({"title": make_title(question)})
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .eq("title", "New chat")
        .execute()
    )
