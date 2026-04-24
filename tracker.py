import os, datetime, requests, numpy as np, random, time
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

# 1. 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

# 모니터링 대상 리스트 업데이트
TARGETS = [
    {"name": "잡코리아 Smartpick", "url": "https://www.jobkorea.co.kr/service/company/cpc"},
    {"name": "원티드 Pricing", "url": "https://www.wanted.co.kr/dashboard/welcome/pricing"},
    {"name": "Klik Main home", "url": "https://www.klik.co.kr/"},
    {"name": "알바몬 Main home", "url": "https://www.albamon.com/"},
    {"name": "Figma 프라이싱", "url": "https://www.figma.com/pricing/"}
]

# 2. 이미지 업로드 함수
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY or not image_path.exists(): return ""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_API_KEY}, files={"image": f})
        return resp.json()["data"]["url"]
    except: return ""

# 3. 최적화된 좌우 비교 이미지 생성 (감도 40, 격자 50)
def create_diff_image(old_path, new_path, diff_path):
    img_old = Image.open(old_path).convert("RGB")
    img_new = Image.open(new_path).convert("RGB")
    w, h = max(img_old.size[0], img_new.size[0]), max(img_old.size[1], img_new.size[1])
    
    spacing = 10
    combined = Image.new("RGB", (w * 2 + spacing, h), (255, 255, 255))
    combined.paste(img_old, (0, 0))
    combined.paste(img_new, (w + spacing, 0))
    
    diff = ImageChops.difference(img_old.resize((w, h)), img_new.resize((w, h)))
    diff_mask = diff.convert("L").point(lambda x: 255 if x > 40 else 0)
    
    draw = ImageDraw.Draw(combined)
    grid_size = 50
    for y in range(0, h, grid_size):
        for x in range(0, w, grid_size):
            if diff_mask.crop((x, y, x + grid_size, y + grid_size)).getextrema()[1] > 0:
                draw.rectangle([x + w + spacing, y, x + w + spacing + grid_size, y + grid_size], outline="red", width=2)
    combined.save(diff_path)

# 4. 노션 기록 함수
def log_to_notion(name, url, pct, diff_url):
    severity = "major" if pct > 5 else "minor"
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"🚨 {name} ({pct}%)"}}]},
            "URL": {"url": url},
            "변경 유형": {"select": {"name": "screenshot"}},
            "심각도": {"select": {"name": severity}},
            "감지 시각": {"date": {"start": datetime.datetime.now().isoformat()}},
            "스크린샷 변경률": {"number": pct / 100},
            "스크린샷": {"url": diff_url}
        },
        "children": [
            {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "🔍 변경 위치 (우측 빨간 박스)"}}]}},
            {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": diff_url}}}
        ]
    }
    requests.post("https://api.notion.com/v1/pages", 
                  headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}, 
                  json=payload)

# 5. 메인 체크 로직 (접속 보안 강화)
def check_target(target):
    from playwright.sync_api import sync_playwright
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    
    slug = name.replace(" ", "_")
    new_path, old_path, diff_path = SNAPSHOT_DIR/f"{slug}_new.png", SNAPSHOT_DIR/f"{slug}_prev.png", SNAPSHOT_DIR/f"{slug}_diff.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 사람처럼 보이게 환경 설정 강화
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        page = context.new_page()
        
        try:
            # 1. 랜덤 대기 (사람인 척)
            time.sleep(random.uniform(2, 5))
            
            # 2. networkidle 대신 load 또는 domcontentloaded 사용
            # 이렇게 하면 무거운 광고 스크립트가 다 안 끝나도 메인 화면이 뜨면 진행합니다.
            page.goto(url, wait_until="load", timeout=60000)
            
            # 3. 페이지가 안정될 때까지 명시적으로 조금 더 대기
            page.wait_for_timeout(7000) 
            
            # 4. 스냅샷 촬영
            page.screenshot(path=str(new_path), full_page=False)
        except Exception as e:
            print(f"  ❌ 접속 실패: {e}")
            browser.close()
            return
        browser.close()

    if not old_path.exists():
        new_path.replace(old_path)
        print("  📸 기준점 생성 완료")
        return

    # 이미지 비교
    img_old = np.array(Image.open(old_path).convert("RGB"))
    img_new = np.array(Image.open(new_path).convert("RGB"))
    h, w = min(img_old.shape[0], img_new.shape[0]), min(img_old.shape[1], img_new.shape[1])
    diff_arr = np.abs(img_old[:h, :w].astype(float) - img_new[:h, :w].astype(float))
    pct = round(np.sum(diff_arr.max(axis=2) > 40) / (h * w) * 100, 2)
    
    if pct > 0.5:
        print(f"  🚩 변경 감지 ({pct}%)")
        create_diff_image(old_path, new_path, diff_path)
        diff_url = upload_to_imgbb(diff_path)
        log_to_notion(name, url, pct, diff_url)
        new_path.replace(old_path)
    else:
        print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    print(f"🚀 모니터링 시작: {datetime.datetime.now()}")
    for t in TARGETS:
        try: check_target(t)
        except Exception as e: print(f"  ❌ 에러: {e}")

if __name__ == "__main__":
    main()
