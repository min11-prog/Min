import os, datetime, requests, numpy as np
from pathlib import Path
from dataclasses import dataclass
from PIL import Image

# 1. 설정
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

# 2. 이미지 업로드 (이게 로그에 찍혀야 합니다)
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY: 
        print("  ⚠️ IMGBB_API_KEY 없음")
        return ""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_API_KEY}, files={"image": f})
        url = resp.json()["data"]["url"]
        print(f"  📸 이미지 업로드 성공: {url}") # <-- 이 문구가 로그에 떠야 함!
        return url
    except:
        print("  ❌ ImgBB 업로드 실패")
        return ""

# 3. 노션 기록
def log_to_notion(name, url, pct, img_url):
    # 1. 심각도 및 이모지 판정
    severity = "major" if pct > 5 else "minor"
    severity_emoji = "🔴" if severity == "major" else "🟡"
    
    # 2. 노션 데이터 구성
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"{severity_emoji} {name} — UI 변경 ({pct}%)"}}]},
            "URL": {"url": url},
            "변경 유형": {"select": {"name": "screenshot"}},
            "심각도": {"select": {"name": severity}},
            "감지 시각": {"date": {"start": datetime.datetime.now().isoformat()}},
            "스크린샷 변경률": {"number": pct / 100}, # 노션 퍼센트 형식을 위해 100으로 나눔
            "스크린샷": {"url": img_url}
        },
        "children": [
            {
                "object": "block",
                "type": "image",
                "image": {"type": "external", "external": {"url": img_url}}
            }
        ] if img_url else []
    }
    
    # 3. 전송
    requests.post(
        "https://api.notion.com/v1/pages", 
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}", 
            "Notion-Version": "2022-06-28", 
            "Content-Type": "application/json"
        }, 
        json=payload
    )
    print(f"  ✅ Notion 기록 완료: {name}")

# 4. 체크 로직
def check_target(target):
    from playwright.sync_api import sync_playwright
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    
    new_path = SNAPSHOT_DIR / f"{name.replace(' ', '_')}_new.png"
    old_path = SNAPSHOT_DIR / f"{name.replace(' ', '_')}_prev.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto(url, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)
        page.screenshot(path=str(new_path))
        browser.close()

    if not old_path.exists():
        new_path.replace(old_path)
        print("  📸 최초 스냅샷 저장 완료")
        return

    # 비교
    img_old = np.array(Image.open(old_path).convert("RGB"))
    img_new = np.array(Image.open(new_path).convert("RGB"))
    h, w = min(img_old.shape[0], img_new.shape[0]), min(img_old.shape[1], img_new.shape[1])
    diff = np.abs(img_old[:h, :w].astype(float) - img_new[:h, :w].astype(float))
    pct = round(np.sum(diff.max(axis=2) > 15) / (h * w) * 100, 2)
    
    if pct > 0.5:
        print(f"  🚩 변경 감지 ({pct}%)")
        # [순서 중요] 업로드 먼저!
        img_url = upload_to_imgbb(new_path)
        # 그 다음에 노션!
        log_to_notion(name, url, pct, img_url)
        new_path.replace(old_path)
    else:
        print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    for t in TARGETS: 
        try: check_target(t)
        except Exception as e: print(f"  ❌ 에러: {e}")

if __name__ == "__main__":
    main()
