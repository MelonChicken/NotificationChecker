import csv
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from Util.notice_identity import make_stable_id, notice_history_key


KST = timezone(timedelta(hours=9))
SUMMARY_MODEL = "gpt-4.1-mini"
SUMMARY_WINDOW_DAYS = 7
CSV_HEADERS = ["source", "category", "stable_id", "title", "date", "url", "sent_at"]
LEGACY_CSV_HEADERS = ["recorded_at", "category", "post_id", "post_date", "title", "link"]
CATEGORY_LINE_FORMAT = "- [Board Name](Board URL) (N notices): key points in Korean"
BOARD_LABELS_BY_CATEGORY = {
    "seoultechITM": "ITM",
    "seoultechJanghak": "Janghak",
    "seoultechJob": "Job",
    "seoultechContest": "Contest",
    "seoultechNotice": "Notice",
}
BOARD_URLS_BY_CATEGORY = {
    "seoultechITM": "https://itm.seoultech.ac.kr/bachelor_of_information/notice/",
    "seoultechJanghak": "https://www.seoultech.ac.kr/service/info/janghak/",
    "seoultechJob": "https://www.seoultech.ac.kr/service/info/job/",
    "seoultechContest": "https://www.seoultech.ac.kr/service/board/rec/",
    "seoultechNotice": "https://www.seoultech.ac.kr/service/info/notice",
}
LLM_OUTPUT_TEMPLATE = """{
  "overview": "2-3 sentence summary in Korean",
  "categories": [
    "- [e.g. ITM](https://itm.seoultech.ac.kr/bachelor_of_information/notice/) (N notices): key points in Korean",
    "- [e.g. Janghak](https://www.seoultech.ac.kr/service/info/janghak/) (N notices): key points in Korean"
  ],
  "caution": "One caution sentence in Korean. If none, use '없음'"
}"""
SUMMARY_TEMPLATE = """## **최근 7일 공지 요약 ({date_range})** 

### **📌 전체 흐름**
{overview}

### **📂 카테고리별 핵심**
{categories}

### **⚠️ 주의 포인트**
{caution}
"""


class SummaryGenerationError(Exception):
    def __init__(self, log_message: str, user_message: str):
        super().__init__(log_message)
        self.log_message = log_message
        self.user_message = user_message


def _project_root_from_settings(settings_path: str) -> Path:
    return Path(settings_path).resolve().parent.parent


def get_notice_history_csv_path(settings_path: str) -> Path:
    return _project_root_from_settings(settings_path) / "res" / "notice_history.csv"


def append_notice_history(settings_path: str, category_key: str, post, recorded_at: datetime) -> None:
    csv_path = get_notice_history_csv_path(settings_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    migrate_notice_history(settings_path)
    is_new_file = not csv_path.exists()
    fieldnames = _read_history_fieldnames(csv_path)

    if fieldnames and fieldnames != CSV_HEADERS:
        with csv_path.open("a", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=LEGACY_CSV_HEADERS)
            writer.writerow(
                {
                    "recorded_at": recorded_at.isoformat(),
                    "category": category_key,
                    "post_id": getattr(post, "stable_id", getattr(post, "id", "")),
                    "post_date": getattr(post, "date", ""),
                    "title": getattr(post, "title", ""),
                    "link": getattr(post, "link", ""),
                }
            )
        return

    with csv_path.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(
            {
                "source": getattr(post, "source", "seoultech"),
                "category": category_key,
                "stable_id": getattr(
                    post,
                    "stable_id",
                    make_stable_id(
                        getattr(post, "link", ""),
                        category_key,
                        getattr(post, "date", ""),
                        getattr(post, "title", ""),
                    ),
                ),
                "title": getattr(post, "title", ""),
                "date": getattr(post, "date", ""),
                "url": getattr(post, "link", ""),
                "sent_at": recorded_at.isoformat(),
            }
        )


def load_seen_notice_keys(settings_path: str) -> set[tuple[str, str, str]]:
    csv_path = get_notice_history_csv_path(settings_path)
    if not csv_path.exists():
        return set()

    migrate_notice_history(settings_path)
    seen = set()
    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            source = row.get("source") or "seoultech"
            category = row.get("category", "")
            stable_id = row.get("stable_id") or make_stable_id(
                row.get("url") or row.get("link", ""),
                category,
                row.get("date") or row.get("post_date", ""),
                row.get("title", ""),
            )
            if category and stable_id:
                seen.add(notice_history_key(source, category, stable_id))

    return seen


def _read_history_fieldnames(csv_path: Path):
    if not csv_path.exists():
        return None
    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return csv.DictReader(csv_file).fieldnames


def migrate_notice_history(settings_path: str) -> bool:
    csv_path = get_notice_history_csv_path(settings_path)
    if not csv_path.exists():
        return False

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames == CSV_HEADERS:
            return False
        rows = list(reader)

    migrated_rows = []
    seen = set()
    for row in rows:
        category = row.get("category", "")
        title = _legacy_title(row)
        date = row.get("date") or row.get("post_date", "")
        url = _legacy_url(row)
        stable_id = row.get("stable_id") or make_stable_id(url, category, date, title)
        source = row.get("source") or "seoultech"
        key = notice_history_key(source, category, stable_id)
        if not category or not stable_id or key in seen:
            continue

        seen.add(key)
        migrated_rows.append(
            {
                "source": source,
                "category": category,
                "stable_id": stable_id,
                "title": title,
                "date": date,
                "url": url,
                "sent_at": row.get("sent_at") or row.get("recorded_at", ""),
            }
        )

    with tempfile.NamedTemporaryFile(
        "w",
        newline="",
        encoding="utf-8-sig",
        dir=csv_path.parent,
        delete=False,
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(migrated_rows)
        temp_path = Path(csv_file.name)

    try:
        temp_path.replace(csv_path)
    except PermissionError:
        temp_path.unlink(missing_ok=True)
        return False

    return True


def _legacy_url(row: dict) -> str:
    url = row.get("url") or row.get("link", "")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url

    for value in row.get(None) or []:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return url or ""


def _legacy_title(row: dict) -> str:
    title = row.get("title", "")
    extras = []
    for value in row.get(None) or []:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            break
        extras.append(value)
    return ",".join([title, *extras]) if extras else title


def generate_recent_notice_summary(settings_path: str, days: int = SUMMARY_WINDOW_DAYS) -> tuple[str, int]:
    recent_rows = load_recent_notice_rows(settings_path, days=days)
    if not recent_rows:
        return "최근 7일 내 기록된 공지가 없습니다.", 0

    try:
        api_key = _load_openai_api_key(settings_path)
        client = OpenAI(api_key=api_key, timeout=90.0, max_retries=2)
        prompt = _build_summary_prompt(recent_rows, days)
        response_text = _request_summary_text(client, prompt)
        sections = _parse_llm_sections(response_text)
        formatted_categories = "\n".join(sections["categories"]) if sections["categories"] else "- 없음"
        return (
            SUMMARY_TEMPLATE.format(
                date_range=_build_date_range(recent_rows),
                overview=sections["overview"],
                categories=formatted_categories,
                caution=sections["caution"],
            ),
            len(recent_rows),
        )
    except APITimeoutError as exc:
        raise SummaryGenerationError(
            "OpenAI summary request timed out.",
            "요약 요청 시간이 초과되었습니다. 관리자에게 문의해 주세요.",
        ) from exc
    except APIConnectionError as exc:
        raise SummaryGenerationError(
            "OpenAI summary request failed due to a connection error.",
            "OpenAI 연결에 실패했습니다. 관리자에게 문의해 주세요.",
        ) from exc
    except APIStatusError as exc:
        raise SummaryGenerationError(
            f"OpenAI summary request failed with status {exc.status_code}.",
            "OpenAI 응답 처리 중 오류가 발생했습니다. 관리자에게 문의해 주세요.",
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise SummaryGenerationError(
            f"OpenAI summary response was invalid: {exc}",
            "요약 결과를 처리하는 중 오류가 발생했습니다. 관리자에게 문의해 주세요.",
        ) from exc


def load_recent_notice_rows(settings_path: str, days: int = SUMMARY_WINDOW_DAYS):
    csv_path = get_notice_history_csv_path(settings_path)
    if not csv_path.exists():
        return []

    threshold = (datetime.now(KST) - timedelta(days=days)).date()
    recent_rows = []
    seen = set()

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            post_date = _parse_post_date(row.get("date") or row.get("post_date", ""))
            if post_date is None or post_date < threshold:
                continue

            stable_id = row.get("stable_id") or make_stable_id(
                row.get("url") or row.get("link", ""),
                row.get("category", ""),
                row.get("date") or row.get("post_date", ""),
                row.get("title", ""),
            )
            dedupe_key = (row.get("source") or "seoultech", row.get("category"), stable_id)
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            recent_rows.append(row)

    recent_rows.sort(
        key=lambda row: (
            row.get("date") or row.get("post_date", ""),
            row.get("category", ""),
            row.get("stable_id") or row.get("post_id", ""),
        )
    )
    return recent_rows


def _build_summary_prompt(rows, days: int) -> str:
    lines = [
        f"This is a list of university notices recorded over the last {days} days.",
        "Return exactly one JSON object.",
        "Do not add markdown fences or any text before or after the JSON.",
        "Write overview and caution in Korean.",
        "categories must be a JSON string array.",
        f"Each category item must follow this exact format: '{CATEGORY_LINE_FORMAT}'.",
        "Group notices only by source board, never by semantic topic.",
        "Do not merge different boards into one category.",
        "Use only the board names listed below as category names.",
        "Use the board list URL for each category, never a notice detail URL.",
        "Only include boards that actually have notices in the input list.",
        "",
        "[Allowed board names]",
    ]

    for category_key, board_label in BOARD_LABELS_BY_CATEGORY.items():
        lines.append(f"- {category_key}: {board_label}")

    lines.extend(
        [
            "",
            "[Board URLs]",
        ]
    )

    for category_key, board_url in BOARD_URLS_BY_CATEGORY.items():
        lines.append(f"- {category_key}: {board_url}")

    lines.extend(
        [
            "",
            "[Output format]",
            LLM_OUTPUT_TEMPLATE,
            "",
            "[Notice list]",
        ]
    )

    for row in rows:
        lines.append(
            f"- date: {row.get('date') or row.get('post_date', '')} | board_key: {row.get('category', '')} | "
            f"id: {row.get('stable_id') or row.get('post_id', '')} | title: {row.get('title', '')} | "
            f"link: {row.get('url') or row.get('link', '')}"
        )

    return "\n".join(lines)


def _request_summary_text(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model=SUMMARY_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize university notices in Korean. "
                    "Return exactly one JSON object and nothing else."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=1400,
    )

    content = response.choices[0].message.content
    text = _normalize_completion_content(content)
    if not text:
        finish_reason = response.choices[0].finish_reason
        raise ValueError(f"OpenAI chat completion did not include summary text. finish_reason={finish_reason}")
    return text


def _normalize_completion_content(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            else:
                part_text = getattr(part, "text", "")
                if isinstance(part_text, str):
                    text_parts.append(part_text)
        return "\n".join(part for part in text_parts if part).strip()

    return ""


def _parse_llm_sections(text: str) -> dict:
    json_text = _extract_json_object(text)
    payload = json.loads(json_text)

    overview = str(payload.get("overview", "")).strip()
    caution = str(payload.get("caution", "")).strip()
    raw_categories = payload.get("categories", [])

    if isinstance(raw_categories, str):
        categories = [line.strip() for line in raw_categories.splitlines() if line.strip()]
    elif isinstance(raw_categories, list):
        categories = [str(item).strip() for item in raw_categories if str(item).strip()]
    else:
        categories = []

    if not overview or not caution:
        raise ValueError("OpenAI JSON response missing overview or caution.")

    return {
        "overview": overview,
        "categories": categories,
        "caution": caution,
    }


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise ValueError("OpenAI response did not contain a JSON object.")
    return match.group(0)


def _build_date_range(rows) -> str:
    dates = sorted((row.get("date") or row.get("post_date", "")) for row in rows if row.get("date") or row.get("post_date"))
    if not dates:
        return "unknown - unknown"
    return f"{dates[0]} - {dates[-1]}"


def _load_openai_api_key(settings_path: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    env_path = _project_root_from_settings(settings_path) / ".env"
    if not env_path.exists():
        raise RuntimeError("OPENAI_API_KEY not found. Root .env file is missing.")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "OPENAI_API_KEY":
            return value.strip().strip('"').strip("'")

    raise RuntimeError("OPENAI_API_KEY not found in root .env.")


def _parse_post_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
