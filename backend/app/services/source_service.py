import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import ROOT_DIR
from app.schemas.sources import BuildStatus, ManagedSource
from app.services.clients import get_supabase_client

SOURCE_CONFIG_PATH = ROOT_DIR / "config" / "sources.json"
KNOWLEDGE_BASE_PATH = ROOT_DIR / "data" / "knowledge_base.json"
BUILD_STATUS_PATH = ROOT_DIR / "data" / "build-status.json"
BUILD_LOG_PATH = ROOT_DIR / "data" / "build.log"
URL_REGEX = re.compile(r'https?://[^\s<>"]+', re.IGNORECASE)


def slugify(value: str) -> str:
    return re.sub(r"(^-+|-+$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))[:48] or "source"


def infer_type(url: str) -> str:
    return "pdf" if re.search(r"\.pdf($|[?#])|coredownload\.pdf|inline\.pdf", url, re.I) else "html"


def infer_category(source_type: str) -> str:
    return "downloads" if source_type == "pdf" else "website"


def infer_title(url: str) -> str:
    parsed = urlparse(url)
    candidate = Path(parsed.path).name.replace(".pdf", "") or parsed.hostname or url
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", candidate)).strip() or url


def infer_id(url: str, used_ids: set[str]) -> str:
    parsed = urlparse(url)
    base = slugify("-".join(part for part in [parsed.hostname or "", parsed.path.strip("/").replace("/", "-")] if part))
    next_id = base
    counter = 2
    while next_id in used_ids:
        next_id = f"{base}-{counter}"
        counter += 1
    used_ids.add(next_id)
    return next_id


def normalize_entry(entry: str | dict, used_ids: set[str]) -> ManagedSource:
    url = entry if isinstance(entry, str) else entry["url"]
    source_type = "pdf" if isinstance(entry, dict) and entry.get("type") == "pdf" else infer_type(url)
    provided_id = entry.get("id") if isinstance(entry, dict) else None
    source_id = provided_id if provided_id and provided_id not in used_ids else infer_id(url, used_ids)
    used_ids.add(source_id)
    return ManagedSource(
        id=source_id,
        title=(entry.get("title") if isinstance(entry, dict) else None) or infer_title(url),
        url=url,
        type=source_type,
        category=(entry.get("category") if isinstance(entry, dict) else None) or infer_category(source_type),
    )


def load_sources_config() -> tuple[str, list[ManagedSource]]:
    payload = json.loads(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    used_ids: set[str] = set()
    return payload.get("name") or "Web Harvest Chatbot Sources", [
        normalize_entry(entry, used_ids) for entry in payload.get("sources", [])
    ]


def save_sources_config(name: str, sources: list[ManagedSource]) -> None:
    SOURCE_CONFIG_PATH.write_text(
        json.dumps({"name": name, "sources": [source.url for source in sources]}, indent=2) + "\n",
        encoding="utf-8",
    )


def read_build_status() -> BuildStatus:
    if not BUILD_STATUS_PATH.exists():
        return BuildStatus(state="idle", summary="No build has run yet.", startedAt=None, finishedAt=None, logPath=None)
    return BuildStatus(**json.loads(BUILD_STATUS_PATH.read_text(encoding="utf-8")))


def extract_urls(text: str) -> list[str]:
    return list(dict.fromkeys(match.rstrip("),.;") for match in URL_REGEX.findall(text)))


def add_sources_from_text(text: str) -> dict:
    name, sources = load_sources_config()
    existing_urls = {source.url for source in sources}
    used_ids = {source.id for source in sources}
    added: list[ManagedSource] = []
    skipped: list[str] = []

    for url in extract_urls(text):
        if url in existing_urls:
            skipped.append(url)
            continue
        source = normalize_entry(url, used_ids)
        sources.append(source)
        existing_urls.add(url)
        added.append(source)

    save_sources_config(name, sources)
    return {"name": name, "sources": sources, "added": added, "skipped": skipped}


def remove_source_by_id(source_id: str) -> dict:
    name, sources = load_sources_config()
    removed = next((source for source in sources if source.id == source_id), None)
    if not removed:
        return {"name": name, "sources": sources, "removed": None}
    next_sources = [source for source in sources if source.id != source_id]
    save_sources_config(name, next_sources)
    get_supabase_client().from_("chunks").delete().eq("doc_id", source_id).execute()
    return {"name": name, "sources": next_sources, "removed": removed}


def start_pipeline_build() -> bool:
    current = read_build_status()
    if current.state == "running":
        return False

    BUILD_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUILD_LOG_PATH.write_text("", encoding="utf-8")
    BUILD_STATUS_PATH.write_text(
        json.dumps(
            {
                "state": "running",
                "summary": "Build is running in the background.",
                "startedAt": None,
                "finishedAt": None,
                "logPath": str(BUILD_LOG_PATH),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    def run_pipeline() -> None:
        completed = subprocess.run(
            [sys.executable, "pipeline.py", "--reset-index"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        output = f"{completed.stdout or ''}{completed.stderr or ''}"
        BUILD_LOG_PATH.write_text(output, encoding="utf-8")

        if completed.returncode == 0:
            status = {
                "state": "success",
                "summary": "Build completed successfully.",
                "startedAt": None,
                "finishedAt": None,
                "logPath": str(BUILD_LOG_PATH),
            }
        else:
            last_line = next((line for line in reversed(output.splitlines()) if line.strip()), "Build failed.")
            status = {
                "state": "error",
                "summary": last_line,
                "startedAt": None,
                "finishedAt": None,
                "logPath": str(BUILD_LOG_PATH),
            }

        BUILD_STATUS_PATH.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    threading.Thread(target=run_pipeline, daemon=True).start()
    return True
