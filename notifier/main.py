from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCE_URLS = ["https://fit.huit.edu.vn/thong-bao"]
STATE_PATH = Path(os.getenv("STATE_PATH", "seen.json"))
USER_AGENT = "fit-huit-notifier/1.0"


@dataclass(frozen=True)
class Notice:
    title: str
    url: str
    date: str = ""
    source: str = ""

    @property
    def key(self) -> str:
        raw = f"{self.url}|{self.title}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"seen": {}, "bootstrapped": False}
    with STATE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with STATE_PATH.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")


def fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
    response.raise_for_status()
    return response.text


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_notice_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "fit.huit.edu.vn":
        return False
    path = parsed.path.strip("/")
    if not path:
        return False
    listing_paths = {"thong-bao", "tin-tuc", "viec-lam-thuc-tap", "thuc-tap-kien-tap"}
    if path in listing_paths:
        return False
    blocked_prefixes = {"gioi-thieu", "lien-he", "dao-tao", "nghien-cuu-khoa-hoc", "sinh-vien", "giang-vien"}
    if path.split("/", 1)[0] in blocked_prefixes:
        return False
    return True


def find_nearby_date(element) -> str:
    date_pattern = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b")
    for parent in [element, *element.parents][:5]:
        text = clean_text(parent.get_text(" ", strip=True))
        match = date_pattern.search(text)
        if match:
            return match.group(0)
    return ""


def parse_notices(html: str, source_url: str) -> list[Notice]:
    soup = BeautifulSoup(html, "html.parser")
    notices: list[Notice] = []
    seen_urls: set[str] = set()

    for link in soup.select("a[href]"):
        title = clean_text(link.get_text(" ", strip=True))
        if len(title) < 8:
            continue

        absolute_url = urljoin(source_url, link["href"]).split("#", 1)[0]
        if absolute_url in seen_urls or not is_notice_url(absolute_url):
            continue

        seen_urls.add(absolute_url)
        notices.append(Notice(title=title, url=absolute_url, date=find_nearby_date(link), source=source_url))

    return notices


def collect_notices(source_urls: Iterable[str]) -> list[Notice]:
    notices: list[Notice] = []
    for source_url in source_urls:
        notices.extend(parse_notices(fetch_html(source_url), source_url))
    return notices


def format_message(notice: Notice) -> str:
    parts = ["[FIT HUIT] Có thông báo mới", "", notice.title]
    if notice.date:
        parts.extend(["", f"Ngày đăng: {notice.date}"])
    parts.extend(["", notice.url])
    return "\n".join(parts)


def send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": False},
        timeout=25,
    )
    response.raise_for_status()


def remember(state: dict, notice: Notice) -> None:
    state["seen"][notice.key] = {
        "title": notice.title,
        "url": notice.url,
        "date": notice.date,
        "first_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    state = load_state()
    state.setdefault("seen", {})
    notices = collect_notices(SOURCE_URLS)

    if not notices:
        print("No notices found. Parser may need an update.")
        return 1

    new_notices = [notice for notice in notices if notice.key not in state["seen"]]

    if not state.get("bootstrapped"):
        for notice in notices:
            remember(state, notice)
        state["bootstrapped"] = True
        save_state(state)
        print(f"Bootstrapped {len(notices)} existing notices. No Telegram messages sent.")
        return 0

    for notice in reversed(new_notices):
        send_telegram(format_message(notice))
        remember(state, notice)
        print(f"Sent: {notice.title}")

    save_state(state)
    print(f"Checked {len(notices)} notices, sent {len(new_notices)} new notices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
