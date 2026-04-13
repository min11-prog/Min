import os
import json
import hashlib
import datetime
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup
from PIL import Image
import numpy as np

# ────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "") # ImgBB 키
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

TARGETS = [
    {
        "name": "잡코리아 Main home",
        "url": "https://www.jobkorea.co.kr/",
        "selectors": ["h1", "h2", ".pricing-card"],
        "screenshot": True,
    },
    {
        "name": "원티드 Main home",
        "url": "https://www.wanted.co.kr/",
        "selectors": ["h1", "h2", "h3"],
        "screenshot": True,
    },
    {
        "name": "Figma 프라이싱",
        "url": "https://www.figma.com/pricing/",
        "selectors": ["h1", "h2", "[class*='plan']"],
        "screenshot": True,
    },
]

@dataclass
class ChangeRecord:
    site_name: str
    url: str
    change_type: str
    severity: str
    summary: str
    diff_text: str = ""
    screenshot_diff_pct: float = 0.0
    screenshot_url: str = "" # 업로드된 이미지 주소
    detected_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

# ────────────────────────────────────────────
# 이미지 업로드 함수
# ────────────────────────────────────────────

def upload_to_imgbb(image_path: Path) -> str:
    """이미지를 ImgBB에 업로드하고 직링크 반환"""
    if not IMGBB_API_KEY:
        print("  ⚠️ IMGBB_API_KEY가 설정되지 않았습니다.")
        return ""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://api.imgbb.com/1/upload",
                params={"key": IMGBB_API_KEY},
                files={"image": f}
            )
        url = resp.json()["data"]["url"]
        print(f"  📸 이미지 업로드 성공: {url}")
        return url
    except Exception as e:
        print(f"  ⚠️ 이미지 업로드 실패: {e}")
        return ""

# ────────────────────────────────────────────
# 나머지 핵심 기능 (기존 유지 + 보완)
# ────────────────────────────────────────────

def fetch_text_snapshot(url, selectors):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    parts = [f"[{sel}] {el.get_text(strip=True)}" for sel in selectors for el in soup.select(sel)]
    return "\n".join(parts)

def take_screenshot(url, site_name):
    from playwright.sync_api import sync_playwright
    path = SNAPSHOT_DIR / f"{_slug(site_name)}_new.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(path), full_page=False)
        browser.close()
    return path

def compare_screenshots(site_name, new_path):
    old_path = SNAPSHOT_DIR / f"{_slug(site_name)}_prev.png"
    if not old_path.exists():
        new_path.replace(old_path)
        return False, 0.0
    img_old = np.array(Image.open(old_path).convert("RGB"), dtype=np.float32)
    img_new = np.array(Image.open(new_path).convert("RGB"), dtype=np.float32)
    h, w = min(img_old.shape[0], img_new.shape[0]), min(img_old.shape[1], img_new.shape[1])
    diff = np.abs(img_old[:h, :w] - img_new[:h, :w])
    changed = np.sum(diff.max(axis=2) > 15)
    pct = round(changed / (h * w) * 100, 2)
    new_path.replace(old_path)
    return pct > 0.5, pct

def log_to_notion(change: ChangeRecord):
    if not NOTION_TOKEN or not NOTION_DB_ID: return
    severity_emoji = {"minor": "🟡", "major": "🔴"}.get(change.severity, "⚪")
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"{severity_emoji} {change.site_name} — {change.summary}"}}]},
            "URL": {"url": change.url},
            "변경 유형": {"select": {"name": change.change_type}},
            "심각도": {"select": {"name": change.severity}},
            "감지 시각": {"date": {"start": change.detected_at}},
            "스크린샷 변경률": {"number": change.screenshot_diff_pct},
        },
        "children": []
    }

    # 스크린샷이 있으면 본문에 이미지 블록 추가
    if change.screenshot_url:
        payload["children"].append({
            "object": "block", "type": "image",
            "image": {"type": "external", "external": {"url": change.screenshot_url}}
        })
    
    # 텍스트 diff가 있으면 코드 블록 추가
    if change.diff_text:
        payload["children"].append({
            "object": "block", "type": "code",
            "code": {"language": "diff", "rich_text": [{"type": "text", "text": {"content": change.diff_text[:1900]}}]}
        })

    requests.post(
        "https://api.notion.com/v1/pages",
        headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
        json=payload
    )

def _slug(name): return name.replace(" ", "_").replace("/", "-")

def check_target(target):
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    change_rec = None

    # 1) 텍스트 체크 (생략 가능하나 기존 로직 유지)
    # 2) 스크린샷 체크
    if target.get("screenshot"):
        new_shot = take_screenshot(url, name)
        changed, pct = compare_screenshots(name, new_shot)
        if changed:
            # 변경 시 ImgBB에 업로드
            img_url = upload_to_imgbb(SNAPSHOT_DIR / f"{_slug(name)}_prev.png")
            change_rec = ChangeRecord(
                site_name=name, url=url, change_type="screenshot",
                severity="major" if pct > 5 else "minor",
                summary=f"UI 변경 ({pct}%)", screenshot_diff_pct=pct, screenshot_url=img_url
            )
            log_to_notion(change_rec)
        else:
            print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    for target in TARGETS: check_target(target)

if __name__ == "__main__":
    main()
