import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


STABLE_ID_QUERY_KEYS = ("bidx", "qidx", "profboardidx")


@dataclass
class Notice:
    source: str
    category: str
    stable_id: str
    title: str
    date: str
    url: str
    is_major_notice: bool = False
    legacy_id: str = ""

    @property
    def id(self) -> str:
        return self.stable_id

    @property
    def link(self) -> str:
        return self.url


def make_stable_id(url: str, category: str = "", date: str = "", title: str = "") -> str:
    stable_id = stable_id_from_url(url)
    if stable_id:
        return stable_id

    fallback = f"{category}|{date}|{normalize_title(title)}"
    digest = hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:16]
    return f"hash:{digest}"


def stable_id_from_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlsplit(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(query_pairs)

    for key in STABLE_ID_QUERY_KEYS:
        value = query.get(key)
        if value:
            return f"{key}:{value}"

    normalized = normalize_url(url)
    return f"url:{normalized}" if normalized else ""


def normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def notice_history_key(source: str, category: str, stable_id: str) -> tuple[str, str, str]:
    return (source or "seoultech", category or "", stable_id or "")


def is_major_notice_text(text: str) -> bool:
    value = (text or "").strip()
    return "notice" in value.lower() or "공지" in value


def format_notice_display_tag(notice: Notice) -> str:
    return format_stable_id_display_tag(notice.stable_id, notice.is_major_notice)


def format_stable_id_display_tag(stable_id: str, is_major_notice: bool = False) -> str:
    prefix = "N" if is_major_notice else "P"
    stable_id = stable_id or ""

    for key in STABLE_ID_QUERY_KEYS:
        marker = f"{key}:"
        if stable_id.startswith(marker):
            return f"{prefix}{stable_id[len(marker):]}"

    if ":" in stable_id:
        kind, payload = stable_id.split(":", 1)
        readable = payload.rsplit("/", 1)[-1] or kind
        return f"{prefix}{readable}"

    return f"{prefix}{stable_id or 'UNKNOWN'}"
