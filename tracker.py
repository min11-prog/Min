import os
import datetime
import requests
from pathlib import Path
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from PIL import Image
import numpy as np

# ────────────────────────────────────────────
# 1. 설정 (GitHub Secrets와 연결됨)
# ────────────────────────────────────────────
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")

SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

TARGETS = [
    {"name": "잡코리아 Main home", "url": "https://www.jobkorea.co.kr/"},
    {"name": "원티드 Main home", "url": "https://www.wanted.co.kr/"},
    {"name": "Figma 프라이싱", "url": "https://www.figma.com/pricing/"},
]

@dataclass
class ChangeRecord:
    site_name: str
    url: str
    summary: str
    screenshot_url: str = ""
    screenshot_diff_pct: float = 0.0

# ────────────────────────────────────────────
# 2. 이미지 업로드 함수 (ImgBB)
# ────────────────────────────────────────────
def upload_to_imgbb(image_path: Path) -> str:
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
        data = resp.json()
        if data["success"]:
            url = data["data"]["url"]
            print(f"  📸 이미지 업로드 성공: {url}")
            return url
        else:
            print(f"  ❌ ImgBB 오류: {data.get('error')}")
            return ""
    except Exception as e:
        print(f"  ⚠️ 이미지 업로드 중 에러: {e}")
        return ""

# ────────────────────────────────────────────
# 3. 노션 기록 함수
# ────────────────────────────────────────────
def log_to_notion(record: ChangeRecord):
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("  ⚠️ Notion 설정이 부족합니다.")
        return

    # [중요] 노션 표의 칸 이름이 '스크린샷', 'URL', '스크린샷 변경률' 등과 일치해야 함
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"🚨 {record.site_name} — {record.summary}"}}]},
            "URL": {"url": record.url},
            "감지 시각": {"date": {"start": datetime.datetime.now().isoformat()}},
            "스크린샷 변경률": {"number": record.screenshot_diff_pct},
            "스크린샷": {"url": record.screenshot_url} 
        }
    }

    # 페이지 본문에도 이미지 블록 추가
    if record.screenshot_url:
        payload["children"] = [
            {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": record.screenshot_url}
                }
            }
        ]
    
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    if resp.status_code == 200:
        print(f"  ✅ Notion 기록 완료: {record.site_name}")
    else:
        print(f"  ❌ Notion 에러: {resp.text}")

# ────────────────────────────────────────────
# 4. 핵심 체크 로직 (Playwright 접속 강화)
# ────────────────────────────────────────────
def _slug(name): return name.replace(" ", "_").replace("/", "-")

def check_target(target):
    from playwright.sync_api import sync_playwright
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    
    new_shot_path = SNAPSHOT_DIR / f"{_slug(name)}_new.png"
    old_shot_path = SNAPSHOT_DIR / f"{_slug(name)}_prev.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 잡코리아 접속을 위해 '사람인 척' 위장
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="load", timeout=60000)
            page.wait_for_timeout(5000) # 안정화 대기
            page.screenshot(path=str(new_shot_path), full_page=False)
        except Exception as e:
            print(f"  ❌ 접속/촬영 실패: {e}")
            browser.close()
            return
        browser.close()

    # 최초 실행 처리
    if not old_shot_path.exists():
        new_shot_path.replace(old_shot_path)
        print("  📸 최초 실행: 기준 스냅샷 저장 완료")
        return

    # 이미지 비교
    img_old = np.array(Image.open(old_shot_path).convert("RGB"))
    img_new = np.array(Image.open(new_shot_path).convert("RGB"))
    
    h, w = min(img_old.shape[0], img_new.shape[0]), min(img_old.shape[1], img_new.shape[1])
    diff = np.abs(img_old[:h, :w].astype(float) - img_new[:h, :w].astype(float))
    pct = round(np.sum(diff.max(axis=2) > 15) / (h * w) * 100, 2)
    
    if pct > 0.5: # 0.5% 이상 변경 시
        print(f"  🚩 변경 감지 ({pct}%)")
        img_url = upload_to_imgbb(new_shot_path) # 이미지 업로드
        log_to_notion(ChangeRecord(name, url, f"UI 변경 ({pct}%)", img_url, pct))
        new_shot_path.replace(old_shot_path) # 기준 교체
    else:
        print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    print("=" * 50)
    print(f"🕵️ 경쟁사 트래커 작동 시작: {datetime.datetime.now()}")
    for t in TARGETS:
        try: check_target(t)
        except Exception as e: print(f"  ❌ 에러 발생: {e}")
    print("=" * 50)

if __name__ == "__main__":
    main()
