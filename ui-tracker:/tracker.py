"""
경쟁사 UI 트래커
- 스크린샷 픽셀 비교 (시각적 변화)
- HTML 텍스트/구조 diff (텍스트 변화)
- 변경 감지 시 Notion 자동 기록
"""

import os
import json
import hashlib
import datetime
import difflib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageChops
import numpy as np

# ────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")        # Notion Integration Token
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")        # Notion Database ID
SNAPSHOT_DIR = Path("snapshots")                          # 스냅샷 저장 경로
SNAPSHOT_DIR.mkdir(exist_ok=True)

# 추적할 URL 목록 — 원하는 만큼 추가
TARGETS = [
    {
        "name": "잡코리아 Main home",
        "url": "https://www.jobkorea.co.kr/",
        "selectors": ["h1", "h2", ".pricing-card", "[class*='price']"],  # 감시할 CSS 선택자
        "screenshot": True,
    },
    {
        "name": "원티드 Main home",
        "url": "https://www.wanted.co.kr/",
        "selectors": ["h1", "h2", "h3", "[class*='feature']"],
        "screenshot": True,
    },
    {
        "name": "Figma 프라이싱",
        "url": "https://www.figma.com/pricing/",
        "selectors": ["h1", "h2", "[class*='plan']", "[class*='price']"],
        "screenshot": True,
    },
]


# ────────────────────────────────────────────
# 데이터 구조
# ────────────────────────────────────────────

@dataclass
class ChangeRecord:
    site_name: str
    url: str
    change_type: str          # "text" | "screenshot" | "both"
    severity: str             # "minor" | "major"
    summary: str
    diff_text: str = ""
    screenshot_diff_pct: float = 0.0
    detected_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())


# ────────────────────────────────────────────
# HTML 텍스트 스냅샷 & diff
# ────────────────────────────────────────────

def fetch_text_snapshot(url: str, selectors: list[str]) -> str:
    """지정된 CSS 선택자의 텍스트를 추출해 하나의 문자열로 반환"""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; UITracker/1.0)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    parts = []
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(separator=" ", strip=True)
            if text:
                parts.append(f"[{sel}] {text}")
    return "\n".join(parts)


def load_text_snapshot(site_name: str) -> Optional[str]:
    path = SNAPSHOT_DIR / f"{_slug(site_name)}_text.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


def save_text_snapshot(site_name: str, content: str):
    path = SNAPSHOT_DIR / f"{_slug(site_name)}_text.txt"
    path.write_text(content, encoding="utf-8")


def diff_text(old: str, new: str) -> tuple[bool, str, str]:
    """변경 여부, diff 요약, diff 전문 반환"""
    if old == new:
        return False, "", ""

    diff = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile="이전", tofile="현재", lineterm=""
    ))
    added   = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    summary = f"추가 {len(added)}줄 / 삭제 {len(removed)}줄"
    return True, summary, "\n".join(diff[:60])   # diff 최대 60줄만 저장


# ────────────────────────────────────────────
# 스크린샷 비교
# ────────────────────────────────────────────

def take_screenshot(url: str, site_name: str) -> Path:
    """Playwright로 스크린샷 촬영 후 저장"""
    from playwright.sync_api import sync_playwright

    path = SNAPSHOT_DIR / f"{_slug(site_name)}_new.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(path), full_page=False)
        browser.close()
    return path


def compare_screenshots(site_name: str, new_path: Path) -> tuple[bool, float]:
    """이전 스크린샷과 픽셀 비교. (변경여부, 변경률%) 반환"""
    old_path = SNAPSHOT_DIR / f"{_slug(site_name)}_prev.png"
    if not old_path.exists():
        # 최초 실행 — 현재 스크린샷을 이전으로 저장
        new_path.replace(old_path)
        return False, 0.0

    img_old = np.array(Image.open(old_path).convert("RGB"), dtype=np.float32)
    img_new = np.array(Image.open(new_path).convert("RGB"), dtype=np.float32)

    # 크기 맞추기
    h = min(img_old.shape[0], img_new.shape[0])
    w = min(img_old.shape[1], img_new.shape[1])
    diff = np.abs(img_old[:h, :w] - img_new[:h, :w])
    changed_pixels = np.sum(diff.max(axis=2) > 15)   # 15 이상 차이 = 변경
    total_pixels = h * w
    pct = changed_pixels / total_pixels * 100

    # 현재 → 이전으로 교체
    new_path.replace(old_path)
    return pct > 0.5, round(pct, 2)   # 0.5% 초과 시 변경 판정


# ────────────────────────────────────────────
# Notion 기록
# ────────────────────────────────────────────

def log_to_notion(change: ChangeRecord):
    """변경 사항을 Notion 데이터베이스에 새 페이지로 추가"""
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("  ⚠️  NOTION_TOKEN / NOTION_DB_ID 미설정 — 콘솔에만 출력합니다.")
        print(f"     [{change.site_name}] {change.summary}")
        return

    severity_emoji = {"minor": "🟡", "major": "🔴"}.get(change.severity, "⚪")

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {
                "title": [{"text": {"content": f"{severity_emoji} {change.site_name} — {change.summary}"}}]
            },
            "URL": {"url": change.url},
            "변경 유형": {"select": {"name": change.change_type}},
            "심각도": {"select": {"name": change.severity}},
            "감지 시각": {"date": {"start": change.detected_at}},
            "스크린샷 변경률": {"number": change.screenshot_diff_pct},
        },
        "children": [
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "diff",
                    "rich_text": [{"type": "text", "text": {"content": change.diff_text[:1900]}}]
                }
            }
        ] if change.diff_text else []
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    if resp.status_code == 200:
        print(f"  ✅ Notion 기록 완료: {change.site_name}")
    else:
        print(f"  ❌ Notion 오류 {resp.status_code}: {resp.text[:200]}")


# ────────────────────────────────────────────
# 메인 실행
# ────────────────────────────────────────────

def _slug(name: str) -> str:
    return name.replace(" ", "_").replace("/", "-")


def check_target(target: dict):
    name = target["name"]
    url  = target["url"]
    print(f"\n🔍 {name} 확인 중...")

    changes: list[ChangeRecord] = []

    # 1) 텍스트 변경 감지
    try:
        new_text = fetch_text_snapshot(url, target.get("selectors", ["body"]))
        old_text = load_text_snapshot(name)
        if old_text is None:
            print("  📸 최초 스냅샷 저장 (텍스트)")
            save_text_snapshot(name, new_text)
        else:
            changed, summary, diff = diff_text(old_text, new_text)
            if changed:
                save_text_snapshot(name, new_text)
                severity = "major" if len(diff.splitlines()) > 10 else "minor"
                changes.append(ChangeRecord(
                    site_name=name, url=url,
                    change_type="text", severity=severity,
                    summary=f"텍스트 변경 감지 ({summary})",
                    diff_text=diff,
                ))
            else:
                print("  ✓ 텍스트 변경 없음")
    except Exception as e:
        print(f"  ⚠️  텍스트 수집 실패: {e}")

    # 2) 스크린샷 비교
    if target.get("screenshot"):
        try:
            new_shot = take_screenshot(url, name)
            changed, pct = compare_screenshots(name, new_shot)
            if changed:
                severity = "major" if pct > 5 else "minor"
                changes.append(ChangeRecord(
                    site_name=name, url=url,
                    change_type="screenshot", severity=severity,
                    summary=f"UI 레이아웃 변경 ({pct}% 픽셀 차이)",
                    screenshot_diff_pct=pct,
                ))
            else:
                print(f"  ✓ 스크린샷 변경 없음 ({pct}%)")
        except Exception as e:
            print(f"  ⚠️  스크린샷 실패 (Playwright 미설치?): {e}")

    # 3) Notion 기록
    for c in changes:
        print(f"  🚨 변경 감지: {c.summary}")
        log_to_notion(c)

    return changes


def main():
    print("=" * 50)
    print(f"🕵️  경쟁사 UI 트래커 시작 — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_changes = []
    for target in TARGETS:
        all_changes.extend(check_target(target))

    print(f"\n{'=' * 50}")
    print(f"완료 — 총 {len(all_changes)}건 변경 감지 / Notion 기록")
    print("=" * 50)


if __name__ == "__main__":
    main()
