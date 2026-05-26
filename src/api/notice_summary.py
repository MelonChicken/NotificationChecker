import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


KST = timezone(timedelta(hours=9))
SUMMARY_MODEL = "gpt-5"
SUMMARY_WINDOW_DAYS = 7
CSV_HEADERS = ["recorded_at", "category", "post_id", "post_date", "title", "link"]
LLM_OUTPUT_TEMPLATE = """OVERVIEW<<<전체 공지 건수와 가장 비중이 큰 카테고리를 포함한 한 단락 요약>>>
CATEGORIES<<<아래 분류 체계에 따라 '- [분류] (N건): 핵심 내용' 형식으로 작성. 분류는 학사 / 장학 / 취업·인턴 / 행사·특강 / 모집·신청 / 기타 중에서 선택. 해당 분류에 공지가 없으면 그 줄은 생략. 같은 분류 안에서는 중요 순으로 정렬>>>
CAUTION<<<마감 임박이거나 놓치면 불이익이 있는 항목 한 줄, 없으면 '없음'>>>"""
SUMMARY_TEMPLATE = """[최근 7일 공지 요약]
📌 전체 흐름
{overview}

📂 카테고리별 핵심
{categories}

⚠️ 주의 포인트
{caution}"""


def _project_root_from_settings(settings_path: str) -> Path:
    return Path(settings_path).resolve().parent.parent


def get_notice_history_csv_path(settings_path: str) -> Path:
    return _project_root_from_settings(settings_path) / "res" / "notice_history.csv"


def append_notice_history(settings_path: str, category_key: str, post, recorded_at: datetime) -> None:
    csv_path = get_notice_history_csv_path(settings_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(
            {
                "recorded_at": recorded_at.isoformat(),
                "category": category_key,
                "post_id": getattr(post, "id", ""),
                "post_date": getattr(post, "date", ""),
                "title": getattr(post, "title", ""),
                "link": getattr(post, "link", ""),
            }
        )


def generate_recent_notice_summary(settings_path: str, days: int = SUMMARY_WINDOW_DAYS) -> tuple[str, int]:
    recent_rows = load_recent_notice_rows(settings_path, days=days)
    if not recent_rows:
        return "최근 7일 내 기록된 공지가 없습니다.", 0

    api_key = _load_openai_api_key(settings_path)
    prompt = _build_summary_prompt(recent_rows, days)
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": SUMMARY_MODEL,
            "store": False,
            "instructions": (
                "You summarize university notices in Korean. "
                "Fill only the requested placeholders and return only the template output."
            ),
            "input": prompt,
        },
        timeout=60,
    )
    response.raise_for_status()
    filled_sections = _parse_llm_sections(_extract_output_text(response.json()))
    return (
        SUMMARY_TEMPLATE.format(
            overview=filled_sections["overview"],
            categories=filled_sections["categories"],
            caution=filled_sections["caution"],
        ),
        len(recent_rows),
    )


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
            post_date = _parse_post_date(row.get("post_date", ""))
            if post_date is None or post_date < threshold:
                continue

            dedupe_key = (row.get("category"), row.get("post_id"), row.get("link"))
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            recent_rows.append(row)

    recent_rows.sort(key=lambda row: (row.get("post_date", ""), row.get("category", ""), row.get("post_id", "")))
    return recent_rows


def _build_summary_prompt(rows, days: int) -> str:
    lines = [
        f"최근 {days}일 동안 기록된 대학 공지 목록이다.",
        "아래 출력 템플릿의 빈칸만 채운다고 생각하고 응답하라.",
        "설명, 서론, 코드블록, 추가 문구 없이 템플릿 결과만 반환하라.",
        "카테고리별 핵심은 '-'로 시작하는 bullet 여러 줄로 작성하라.",
        "",
        "[출력 템플릿]",
        LLM_OUTPUT_TEMPLATE,
        "",
        "[공지 목록]",
    ]

    for row in rows:
        lines.append(
            f"- 날짜: {row.get('post_date', '')} | 분류: {row.get('category', '')} | "
            f"번호: {row.get('post_id', '')} | 제목: {row.get('title', '')} | 링크: {row.get('link', '')}"
        )

    return "\n".join(lines)


def _extract_output_text(response_json: dict) -> str:
    parts = []
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))

    text = "\n".join(part for part in parts if part).strip()
    if not text:
        raise ValueError("OpenAI response did not include summary text.")
    return text


def _parse_llm_sections(text: str) -> dict:
    sections = {}
    for key in ("OVERVIEW", "CATEGORIES", "CAUTION"):
        start_token = f"{key}<<<"
        start_index = text.find(start_token)
        if start_index == -1:
            raise ValueError(f"OpenAI response missing {key} section.")
        start_index += len(start_token)
        end_index = text.find(">>>", start_index)
        if end_index == -1:
            raise ValueError(f"OpenAI response missing closing token for {key}.")
        sections[key.lower()] = text[start_index:end_index].strip()

    return sections


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
