import os, datetime, requests, difflib
from pathlib import Path
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from PIL import Image
import numpy as np

# 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

TARGETS = [
    {"name": "잡코리아 Main home", "url": "https://www.naver.com", "selectors": ["h1", "h2"]},
    {"name": "원티드 Main home", "url": "https://www.wanted.co.kr/", "selectors": ["h1", "h2"]},
    {"name": "Figma 프라이싱", "url": "https://www.figma.com/pricing/", "selectors": ["h1", "h2"]},
]

@dataclass
class ChangeRecord:
    site_name: str
    url: str
    summary: str
    screenshot_url: str = ""
    screenshot_diff_pct: float = 0.0

def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        print("  ⚠️ IMGBB_API_KEY 없음")
        return ""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_API_KEY}, files={"image": f})
        url = resp.json()["data"]["url"]
        print(f"  📸 이미지 업로드 성공: {url}")
        return url
    except:
        return ""

def log_to_notion(record):
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"🚨 {record.site_name} — {record.summary}"}}]},
            "URL": {"url": record.url},
            "감지 시각": {"date": {"start": datetime.datetime.now().isoformat()}},
            "스크린샷 변경률": {"number": record.screenshot_diff_pct},
            "스크린샷": {"url": record.screenshot_url} # 노션의 '스크린샷' 칸
        }
    }
    # 페이지 본문에도 이미지 추가
    if record.screenshot_url:
        payload["children"] = [{"object": "block", "type": "image", "image": {"type": "external", "external": {"url": record.screenshot_url}}}]
    
    requests.post("https://api.notion.com/v1/pages", 
                  headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}, 
                  json=payload)
    print(f"  ✅ Notion 기록 완료: {record.site_name}")

def _slug(name): return name.replace(" ", "_")

def check_target(target):
    from playwright.sync_api import sync_playwright
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    
    new_shot_path = SNAPSHOT_DIR / f"{_slug(name)}_new.png"
    old_shot_path = SNAPSHOT_DIR / f"{_slug(name)}_prev.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=str(new_shot_path))
        browser.close()

    if not old_shot_path.exists():
        new_shot_path.replace(old_shot_path)
        print("  📸 최초 실행: 스냅샷 저장 완료")
        return

    img_old = np.array(Image.open(old_shot_path).convert("RGB"))
    img_new = np.array(Image.open(new_shot_path).convert("RGB"))
    h, w = min(img_old.shape[0], img_new.shape[0]), min(img_old.shape[1], img_new.shape[1])
    diff = np.abs(img_old[:h, :w].astype(float) - img_new[:h, :w].astype(float))
    pct = round(np.sum(diff.max(axis=2) > 15) / (h * w) * 100, 2)
    
    if pct > 0.5:
        print(f"  🚩 변경 감지 ({pct}%)")
        # 1. 먼저 이미지를 올린다
        img_url = upload_to_imgbb(new_shot_path)
        # 2. 노션에 기록한다
        log_to_notion(ChangeRecord(name, url, f"UI 변경 ({pct}%)", img_url, pct))
        new_shot_path.replace(old_shot_path)
    else:
        print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    for t in TARGETS:
        try: check_target(t)
        except Exception as e: print(f"  ❌ 에러: {e}")

if __name__ == "__main__":
    main()
