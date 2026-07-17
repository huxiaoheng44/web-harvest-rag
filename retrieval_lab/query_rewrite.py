"""LLM-based query rewriting: generate alternate phrasings of a user query.

Real user queries are often vague, terse, or phrased very differently from
how the source documents phrase the same concept. Retrieving for a few
paraphrased variants and merging the results is a simple way to cover more
of the vocabulary/semantic space than a single query embedding can.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API") or os.getenv("OPENAI_API_KEY"))
    return _client


SYSTEM_PROMPT = (
    "You rewrite search queries into alternate phrasings for a retrieval system. "
    "Given a query, produce alternate phrasings that preserve the original intent "
    "but vary the wording, phrasing style, or level of detail - as if different "
    "users asked the same underlying question. Do not add new questions or change "
    "the topic. Respond with a JSON object: {\"variants\": [\"...\", \"...\"]}."
)


def rewrite_query(query: str, n: int = 2) -> list[str]:
    """Return [query] + n LLM-generated paraphrased variants."""
    client = _get_client()
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Query: {query}\nGenerate {n} alternate phrasings."},
        ],
    )
    content = response.choices[0].message.content or "{}"

    try:
        payload = json.loads(content)
        variants = [str(v).strip() for v in payload.get("variants", []) if str(v).strip()]
    except (json.JSONDecodeError, AttributeError):
        variants = []

    return [query] + variants[:n]
