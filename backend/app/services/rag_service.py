from app.core.config import get_settings
from app.schemas.chat import Message, Source
from app.services.clients import get_openai_client, get_supabase_client


def build_system_prompt() -> str:
    return " ".join(
        [
            "You are a knowledge-base assistant for a private vector database.",
            "Answer in the same language as the user's question when possible.",
            "Use the retrieved context as the primary source of truth.",
            "If the context is insufficient, say clearly that you cannot confirm it from the current knowledge base.",
            "Do not invent facts, product details, or policies that are not supported by the provided sources.",
            "Keep answers practical and structured.",
        ]
    )


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant sources were retrieved from the knowledge base."

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Title: {chunk.get('title') or 'Untitled'}",
                    f"URL: {chunk.get('url') or ''}",
                    f"Category: {chunk.get('category') or 'unknown'}",
                    f"Similarity: {float(chunk.get('similarity') or 0):.3f}",
                    f"Content: {chunk.get('content') or ''}",
                ]
            )
        )
    return "\n\n".join(parts)


def retrieve_relevant_chunks(query: str) -> list[dict]:
    settings = get_settings()
    openai = get_openai_client()
    response = openai.embeddings.create(model=settings.openai_embed_model, input=query)
    embedding = response.data[0].embedding if response.data else None
    if not embedding:
        raise RuntimeError("Failed to generate query embedding.")

    supabase = get_supabase_client()
    result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": embedding,
            "match_count": settings.match_count,
        },
    ).execute()

    return [
        chunk
        for chunk in (result.data or [])
        if float(chunk.get("similarity") or 0) >= settings.min_similarity
    ]


def generate_answer(question: str, history: list[dict], chunks: list[dict]) -> str:
    settings = get_settings()
    openai = get_openai_client()
    context = build_context(chunks)
    recent_history = [
        {"role": item["role"], "content": item["content"]}
        for item in history[-8:]
        if item.get("role") in {"user", "assistant", "system"}
    ]

    completion = openai.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": build_system_prompt()},
            *recent_history,
            {
                "role": "user",
                "content": "\n".join(
                    [
                        "Answer the question using the context below.",
                        "If the context is weak or empty, say that you cannot confirm from the current knowledge base.",
                        "At the end, add a short 'Sources' section only when you used retrieved sources.",
                        "",
                        "Context:",
                        context,
                        "",
                        f"Question: {question}",
                    ]
                ),
            },
        ],
    )
    return completion.choices[0].message.content.strip() if completion.choices[0].message.content else "I could not generate a response."


def map_sources(chunks: list[dict]) -> list[Source]:
    return [
        Source(
            id=chunk["id"],
            doc_id=chunk["doc_id"],
            title=chunk.get("title"),
            url=chunk.get("url"),
            category=chunk.get("category"),
            similarity=float(chunk.get("similarity") or 0),
        )
        for chunk in chunks
    ]


def answer_question(question: str, history: list[dict]) -> tuple[str, list[Source]]:
    chunks = retrieve_relevant_chunks(question)
    return generate_answer(question, history, chunks), map_sources(chunks)
