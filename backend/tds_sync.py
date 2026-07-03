from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from typing import Any, Dict, Optional

import re
import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None

try:
    from pypdf import PdfReader  # type: ignore
except ImportError:  # pragma: no cover
    PdfReader = None

TECHNICAL_FIELDS = [
    "IS Type",
    "EN Type",
    "Open Time",
    "Pot Life",
    "Adjustability Time",
    "Tensile Adhesion",
    "Slip Resistance",
    "Mixing Ratio",
    "Coverage",
    "Setting Time",
    "Adhesive Thickness",
    "Application Temperature",
    "VOC Content",
    "Shelf Life",
    "Packaging",
    "Color",
]

FIELD_PATTERNS = {
    "IS Type": [r"is\s*type", r"classification\s*\(?is\)?"],
    "EN Type": [r"en\s*type", r"en\s*12004", r"classification\s*\(?en\)?"],
    "Open Time": [r"open\s*time"],
    "Pot Life": [r"pot\s*life"],
    "Adjustability Time": [r"adjust(?:ability|ment)?\s*time"],
    "Tensile Adhesion": [r"tensile\s*adhesion", r"bond\s*strength"],
    "Slip Resistance": [r"slip\s*resistance", r"slip"],
    "Mixing Ratio": [r"mixing\s*ratio", r"mix\s*ratio"],
    "Coverage": [r"coverage", r"consumption"],
    "Setting Time": [r"setting\s*time", r"curing\s*time"],
    "Adhesive Thickness": [r"adhesive\s*thickness", r"bed\s*thickness", r"layer\s*thickness"],
    "Application Temperature": [r"application\s*temperature", r"service\s*temperature", r"temperature"],
    "VOC Content": [r"voc\s*content", r"volatile\s*organic"],
    "Shelf Life": [r"shelf\s*life", r"storage\s*life"],
    "Packaging": [r"packaging", r"pack\s*size"],
    "Color": [r"colou?r"],
}

USER_AGENT = "KamdhenuTdsSync/1.0"


class VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if not self._skip_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self._chunks.append(cleaned)

    def text(self) -> str:
        return "\n".join(self._chunks)


@dataclass
class TdsFetchResult:
    source_type: str
    raw_text: str
    text_hash: str
    file_hash: str
    content_type: str
    source_version: str


class TdsSyncError(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def next_check_time(days: int) -> datetime:
    return utcnow() + timedelta(days=days)


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    return collapsed


def hash_text(text: str) -> str:
    return sha256(normalize_text(text).encode("utf-8")).hexdigest()


def hash_bytes(content: bytes) -> str:
    return sha256(content).hexdigest()


def _extract_text_from_pdf_bytes(content: bytes) -> str:
    if PdfReader is None:
        raise TdsSyncError("PDF parsing requires the pypdf package")

    reader = PdfReader(BytesIO(content))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages)
    if not text.strip():
        raise TdsSyncError("No readable text found in PDF")
    return text


def _extract_text_from_html(content: bytes) -> str:
    html = content.decode("utf-8", errors="ignore")
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        if text.strip():
            return text

    parser = VisibleTextExtractor()
    parser.feed(html)
    text = parser.text()
    if not text.strip():
        raise TdsSyncError("No visible text found on webpage")
    return text


def fetch_tds_source(url: str, timeout: int = 30) -> TdsFetchResult:
    if not url:
        raise TdsSyncError("TDS URL is missing")

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    content = response.content or b""
    content_type = (response.headers.get("content-type") or "").lower()
    source_url = str(response.url)
    is_pdf = "pdf" in content_type or source_url.lower().endswith(".pdf")

    if is_pdf:
        raw_text = _extract_text_from_pdf_bytes(content)
        source_type = "pdf"
    else:
        raw_text = _extract_text_from_html(content)
        source_type = "webpage"

    file_hash = hash_bytes(content)
    text_hash = hash_text(raw_text)
    source_version = f"{source_type}:{text_hash[:12]}"
    return TdsFetchResult(
        source_type=source_type,
        raw_text=raw_text,
        text_hash=text_hash,
        file_hash=file_hash,
        content_type=content_type,
        source_version=source_version,
    )


def extract_technical_fields(raw_text: str) -> Dict[str, str]:
    lines = [line.strip(" :-	") for line in raw_text.splitlines()]
    lines = [line for line in lines if line]
    extracted: Dict[str, str] = {}

    for field, patterns in FIELD_PATTERNS.items():
        value = _find_field_value(lines, patterns)
        if value:
            extracted[field] = value

    return extracted


def _find_field_value(lines: list[str], patterns: list[str]) -> Optional[str]:
    for index, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line, flags=re.IGNORECASE):
                inline = _extract_inline_value(line)
                if inline:
                    return inline
                if index + 1 < len(lines):
                    nxt = lines[index + 1]
                    if len(nxt.split()) <= 20:
                        return nxt
    return None


def _extract_inline_value(line: str) -> Optional[str]:
    for separator in (":", "-", "="):
        if separator in line:
            left, right = line.split(separator, 1)
            if left.strip() and right.strip():
                return right.strip()
    return None


def build_pending_report(raw_text: str, source_version: str) -> Dict[str, Any]:
    fields = extract_technical_fields(raw_text)
    status = "structured" if fields else "raw_text_only"
    return {
        "fields": fields,
        "raw_text": raw_text,
        "field_count": len(fields),
        "extraction_status": status,
        "source_version": source_version,
        "captured_at": utcnow(),
    }
