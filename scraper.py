"""
Config-driven website and PDF scraper.

Usage:
    python scraper.py                 # scrape every configured source
    python scraper.py --test          # scrape the first 3 HTML sources
    python scraper.py --limit 10      # scrape the first 10 configured sources
    python scraper.py --html-only     # scrape only HTML sources
    python scraper.py --pdf-only      # scrape only PDF sources
"""

import argparse
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import markdownify
import pdfplumber
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "sources.json"
DATA_DIR = BASE_DIR / "data"
PAGES_DIR = DATA_DIR / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)

MAIN_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".content",
    ".page-content",
    ".article-body",
    "#content",
    "#main",
]


def load_sources() -> tuple[str, list[dict]]:
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        payload = json.load(handle)

    name = payload.get("name", "Knowledge Base")
    sources = payload.get("sources", [])
    normalized = []

    for index, source in enumerate(sources):
        if isinstance(source, str):
            url = source
            source_id = make_source_id(url, index)
            title = make_source_title(url)
            category = infer_category(url)
            source_type = "auto"
        else:
            url = source["url"]
            source_id = source.get("id") or make_source_id(url, index)
            title = source.get("title") or make_source_title(url)
            category = source.get("category") or infer_category(url)
            source_type = source.get("type") or "auto"

        normalized.append(
            {
                "id": source_id,
                "title": title,
                "url": url,
                "category": category,
                "type": source_type,
            }
        )

    return name, normalized


def slugify(value: str) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))


def make_source_id(url: str, index: int) -> str:
    parsed = urlparse(url)
    hostname = parsed.netloc.replace("www.", "")
    path_part = parsed.path.strip("/").replace("/", "-")
    base = slugify("-".join(part for part in [hostname, path_part] if part)) or f"source-{index + 1}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    trimmed = base[:48] if len(base) > 48 else base
    return f"{trimmed}-{digest}"


def make_source_title(url: str) -> str:
    parsed = urlparse(url)
    last_segment = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else parsed.netloc
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", last_segment.replace(".pdf", ""))).strip() or url


def infer_category(url: str) -> str:
    return "downloads" if infer_type_from_url(url) == "pdf" else "website"


def infer_type_from_url(url: str) -> str:
    return "pdf" if re.search(r"\.pdf($|[?#])|coredownload\.pdf|inline\.pdf", url, re.I) else "html"


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def clean_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "button", "iframe", "svg"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"cookie|consent|breadcrumb|social|share", re.I)):
        tag.decompose()
    return soup


def extract_main_content(soup: BeautifulSoup) -> str:
    for selector in MAIN_CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node:
            return str(node)
    body = soup.find("body")
    return str(body) if body else str(soup)


def html_to_markdown(html_fragment: str) -> str:
    markdown = markdownify.markdownify(
        html_fragment,
        heading_style="ATX",
        bullets="-",
        strip=["a", "img"],
    )
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    lines = [line for line in markdown.splitlines() if len(line.strip()) > 3]
    return "\n".join(lines).strip()


def extract_page_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for index, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_pages.append(f"[Page {index + 1}]\n{text.strip()}")
    return "\n\n".join(text_pages)


def fetch_url(url: str, timeout: int = 20) -> requests.Response | None:
    try:
        response = SESSION.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        print(f"  [ERROR] {exc}")
        return None


def detect_response_type(meta: dict, response: requests.Response) -> str:
    if meta.get("type") in ["html", "pdf"]:
        return meta["type"]

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or infer_type_from_url(response.url) == "pdf":
        return "pdf"
    return "html"


def scrape_html(meta: dict) -> dict:
    print(f"Fetching page [{meta['id']}] {meta['url']}")
    response = fetch_url(meta["url"])
    if response is None:
        return {**meta, "status": "error", "content_markdown": "", "content_plain": ""}

    soup = clean_html(response.text)
    detected_title = extract_page_title(soup)
    main_html = extract_main_content(soup)
    content_markdown = html_to_markdown(main_html)
    content_plain = BeautifulSoup(main_html, "lxml").get_text(separator=" ", strip=True)
    content_plain = re.sub(r"\s+", " ", content_plain).strip()

    result = {
        **meta,
        "status": "ok",
        "detected_title": detected_title,
        "scraped_at": utc_timestamp(),
        "final_url": response.url,
        "content_markdown": content_markdown,
        "content_plain": content_plain,
        "char_count": len(content_plain),
    }
    print(f"  OK {len(content_plain):,} chars extracted")
    return result


def scrape_pdf(meta: dict) -> dict:
    print(f"Fetching PDF  [{meta['id']}] {meta['url']}")
    response = fetch_url(meta["url"])
    if response is None:
        return {**meta, "status": "error", "content_markdown": "", "content_plain": ""}

    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not response.url.lower().endswith(".pdf"):
        print(f"  [WARN] Unexpected Content-Type: {content_type}")
        text = BeautifulSoup(response.text, "lxml").get_text(separator=" ", strip=True)
        return {
            **meta,
            "status": "warn_not_pdf",
            "scraped_at": utc_timestamp(),
            "content_markdown": text[:5000],
            "content_plain": text[:5000],
            "char_count": len(text),
        }

    try:
        text = extract_pdf_text(response.content)
    except Exception as exc:
        print(f"  [ERROR] PDF parse failed: {exc}")
        return {**meta, "status": "error_pdf_parse", "content_markdown": "", "content_plain": ""}

    result = {
        **meta,
        "status": "ok",
        "scraped_at": utc_timestamp(),
        "final_url": response.url,
        "content_markdown": text,
        "content_plain": text,
        "char_count": len(text),
    }
    print(f"  OK {len(text):,} chars extracted from PDF")
    return result


def scrape_html_response(meta: dict, response: requests.Response) -> dict:
    soup = clean_html(response.text)
    detected_title = extract_page_title(soup)
    main_html = extract_main_content(soup)
    content_markdown = html_to_markdown(main_html)
    content_plain = BeautifulSoup(main_html, "lxml").get_text(separator=" ", strip=True)
    content_plain = re.sub(r"\s+", " ", content_plain).strip()

    print(f"Fetching page [{meta['id']}] {meta['url']}")
    print(f"  OK {len(content_plain):,} chars extracted")
    return {
        **meta,
        "type": "html",
        "status": "ok",
        "detected_title": detected_title,
        "scraped_at": utc_timestamp(),
        "final_url": response.url,
        "content_markdown": content_markdown,
        "content_plain": content_plain,
        "char_count": len(content_plain),
    }


def scrape_pdf_response(meta: dict, response: requests.Response) -> dict:
    print(f"Fetching PDF  [{meta['id']}] {meta['url']}")
    try:
        text = extract_pdf_text(response.content)
    except Exception as exc:
        print(f"  [ERROR] PDF parse failed: {exc}")
        return {**meta, "type": "pdf", "status": "error_pdf_parse", "content_markdown": "", "content_plain": ""}

    print(f"  OK {len(text):,} chars extracted from PDF")
    return {
        **meta,
        "type": "pdf",
        "status": "ok",
        "scraped_at": utc_timestamp(),
        "final_url": response.url,
        "content_markdown": text,
        "content_plain": text,
        "char_count": len(text),
    }


def scrape_source(meta: dict) -> dict:
    response = fetch_url(meta["url"])
    if response is None:
        return {**meta, "status": "error", "content_markdown": "", "content_plain": ""}

    detected_type = detect_response_type(meta, response)
    if detected_type == "pdf":
        return scrape_pdf_response(meta, response)
    return scrape_html_response(meta, response)


def save(record: dict):
    output_path = PAGES_DIR / f"{record['id']}.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)


def build_knowledge_base(records: list[dict]):
    output_path = DATA_DIR / "knowledge_base.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
    print(f"\nKnowledge base saved -> {output_path} ({len(records)} documents)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Scrape only the first 3 HTML sources")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of configured sources")
    parser.add_argument("--html-only", action="store_true", help="Scrape only HTML sources")
    parser.add_argument("--pdf-only", action="store_true", help="Scrape only PDF sources")
    args = parser.parse_args()

    corpus_name, sources = load_sources()
    if args.html_only:
        sources = [source for source in sources if source["type"] == "html"]
    if args.pdf_only:
        sources = [source for source in sources if source["type"] == "pdf"]
    if args.test:
        sources = [source for source in sources if source["type"] == "html"][:3]
    elif args.limit > 0:
        sources = sources[: args.limit]

    print(f"\n{'=' * 64}")
    print(f"Scraping {len(sources)} sources for: {corpus_name}")
    print(f"Config file: {CONFIG_PATH}")
    print(f"{'=' * 64}\n")

    records = []
    for index, source in enumerate(sources):
        record = scrape_source(source)
        save(record)
        records.append(record)
        if index < len(sources) - 1:
            time.sleep(1.0 if source["type"] == "pdf" else 1.5)

    build_knowledge_base(records)

    ok_count = sum(1 for record in records if record.get("status") == "ok")
    error_count = sum(1 for record in records if "error" in record.get("status", ""))
    total_chars = sum(record.get("char_count", 0) for record in records)
    print(f"\nDone. {ok_count} OK / {error_count} errors / {total_chars:,} total chars")


if __name__ == "__main__":
    main()
