from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.schemas.chat import ChatRequest, SessionRequest, SessionResponse
from app.schemas.sources import RemoveSourceRequest, SourceTextRequest
from app.services import conversation_service, source_service
from app.services.clients import get_supabase_client
from app.services.rag_service import answer_question

settings = get_settings()

app = FastAPI(title="Web Harvest RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    get_supabase_client().from_("chunks").select("id").limit(1).execute()
    return {"status": "ready"}


@app.post("/users/session", response_model=SessionResponse)
def create_session(payload: SessionRequest) -> SessionResponse:
    display_name = " ".join(payload.display_name.strip().split())
    user_id = payload.client_user_id or str(uuid4())
    get_supabase_client().from_("app_users").upsert(
        {"id": user_id, "display_name": display_name},
        on_conflict="id",
    ).execute()
    return SessionResponse(user_id=user_id, display_name=display_name)


@app.get("/conversations")
def conversations(user_id: str = Query(min_length=1)) -> dict:
    return {"conversations": conversation_service.list_conversations(user_id)}


@app.post("/conversations")
def create_conversation(payload: dict) -> dict:
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return {"conversation": conversation_service.create_conversation(user_id, payload.get("title"))}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: str = Query(min_length=1)) -> dict:
    conversation_service.delete_conversation(user_id, conversation_id)
    return {"ok": True}


@app.get("/conversations/{conversation_id}/messages")
def messages(conversation_id: str, user_id: str = Query(min_length=1)) -> dict:
    try:
        return {"messages": conversation_service.get_messages(user_id, conversation_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    question = payload.message.strip()
    conversation_id = payload.conversation_id

    if conversation_id:
        history = [message.model_dump() for message in conversation_service.get_messages(payload.user_id, conversation_id)]
    else:
        conversation = conversation_service.create_conversation(payload.user_id, question)
        conversation_id = conversation.id
        history = []

    conversation_service.add_message(conversation_id, "user", question)
    conversation_service.update_new_chat_title(payload.user_id, conversation_id, question)
    answer, sources = answer_question(question, history)
    assistant_message = conversation_service.add_message(conversation_id, "assistant", answer, sources)
    return {"conversationId": conversation_id, "message": assistant_message}


@app.get("/sources")
def sources() -> dict:
    name, items = source_service.load_sources_config()
    return {"name": name, "sources": items, "buildStatus": source_service.read_build_status()}


@app.post("/sources")
def add_sources(payload: SourceTextRequest) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Paste one or more URLs first")
    result = source_service.add_sources_from_text(payload.text)
    if payload.runIngestion:
        started = source_service.start_pipeline_build()
        result["message"] = (
            f"Added {len(result['added'])} source{'s' if len(result['added']) != 1 else ''}. Build started in the background."
            if started
            else "Build is already running in the background."
        )
    else:
        result["message"] = f"Added {len(result['added'])} source{'s' if len(result['added']) != 1 else ''}"
    result["buildStatus"] = source_service.read_build_status()
    return result


@app.patch("/sources")
def run_ingestion() -> dict:
    started = source_service.start_pipeline_build()
    return {
        "message": "Build started in the background." if started else "Build is already running.",
        "buildStatus": source_service.read_build_status(),
    }


@app.delete("/sources")
def remove_source(payload: RemoveSourceRequest) -> dict:
    result = source_service.remove_source_by_id(payload.id)
    if not result["removed"]:
        raise HTTPException(status_code=404, detail="Source not found")
    result["message"] = f"Removed source: {result['removed'].title}"
    result["buildStatus"] = source_service.read_build_status()
    return result
