import os, datetime, requests, numpy as np
from pathlib import Path
from PIL import Image, ImageChops

# 1. 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID", "")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

TARGETS = [
    {"name": "잡코리아 Main home", "url": "https://www.jobkorea.co.kr/"},
    {"name": "잡코리아 Smartpick", "url": "hhttps://www.jobkorea.co.kr/service/company/cpc"},
    {"name": "원티드 Pricing", "url": "https://www.wanted.co.kr/dashboard/welcome/pricing"},
    {"name": "Klik Main home", "url": "https://www.klik.co.kr/"},
    {"name": "알바몬 Main home", "url": "https://www.albamon.com/"},
]

# 2. 이미지 업로드 함수
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY or not image_path.exists(): 
        return ""
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_API_KEY}, files={"image": f})
        url = resp.json()["data"]["url"]
        print(f"  📸 강조 이미지 업로드 성공: {url}")
        return url
    except:
        return ""

def create_diff_image(old_path, new_path, diff_path):
    img_old = Image.open(old_path).convert("RGB")
    img_new = Image.open(new_path).convert("RGB")
    
    # 1. 두 이미지 크기 맞추기
    w = max(img_old.size[0], img_new.size[0])
    h = max(img_old.size[1], img_new.size[1])
    
    # 가로로 붙이기 위해 새 캔버스 생성 (간격 10px 추가)
    spacing = 10
    combined = Image.new("RGB", (w * 2 + spacing, h), (255, 255, 255))
    combined.paste(img_old, (0, 0))
    combined.paste(img_new, (w + spacing, 0))
    
    # 2. 차이점 계산 및 감도 조절
    # x > 40: 픽셀 값이 40 이상 차이나야 '다르다'고 판단 (노이즈 제거)
    diff = ImageChops.difference(img_old.resize((w, h)), img_new.resize((w, h)))
    diff_mask = diff.convert("L").point(lambda x: 255 if x > 40 else 0)
    
    # 3. 변경된 영역에 빨간 테두리 그리기
    from PIL import ImageDraw
    draw = ImageDraw.Draw(combined)
    
    # grid_size를 50으로 상향: 너무 자잘하게 박스가 생기는 것을 방지
    grid_size = 50
    for y in range(0, h, grid_size):
        for x in range(0, w, grid_size):
            box = (x, y, x + grid_size, y + grid_size)
            # 해당 구역에 차이가 있는지 확인
            if diff_mask.crop(box).getextrema()[1] > 0:
                # 오른쪽 이미지(img_new) 영역에만 빨간 박스 표시
                draw.rectangle([x + w + spacing, y, x + w + spacing + grid_size, y + grid_size], outline="red", width=2)

    combined.save(diff_path)
    print(f"  📍 최적화된 좌우 비교 이미지 생성 완료")

# 4. 노션 기록 함수 (이미지 1장 버전)
def log_to_notion(name, url, pct, diff_url):
    severity = "major" if pct > 5 else "minor"
    severity_emoji = "🔴" if severity == "major" else "🟡"
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": f"{severity_emoji} {name} — UI 변경 ({pct}%)"}}]},
            "URL": {"url": url},
            "변경 유형": {"select": {"name": "screenshot"}},
            "심각도": {"select": {"name": severity}},
            "감지 시각": {"date": {"start": datetime.datetime.now().isoformat()}},
            "스크린샷 변경률": {"number": pct / 100},
            "스크린샷": {"url": diff_url} # 강조 이미지만 넣음
        },
        "children": [
            {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "📍 변경 위치 확인 (빨간색 표시)"}}]}},
            {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": diff_url}}}
        ] if diff_url else []
    }
    requests.post("https://api.notion.com/v1/pages", 
                  headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}, 
                  json=payload)
    print(f"  ✅ Notion 기록 완료: {name}")

# 5. 메인 로직
def check_target(target):
    from playwright.sync_api import sync_playwright
    name, url = target["name"], target["url"]
    print(f"\n🔍 {name} 확인 중...")
    
    slug = name.replace(" ", "_")
    new_path, old_path, diff_path = SNAPSHOT_DIR/f"{slug}_new.png", SNAPSHOT_DIR/f"{slug}_prev.png", SNAPSHOT_DIR/f"{slug}_diff.png"
    
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
        print("  📸 최초 실행: 스냅샷 저장")
        return

    # 비교 연산
    img_old_arr = np.array(Image.open(old_path).convert("RGB"))
    img_new_arr = np.array(Image.open(new_path).convert("RGB"))
    h, w = min(img_old_arr.shape[0], img_new_arr.shape[0]), min(img_old_arr.shape[1], img_new_arr.shape[1])
    diff_arr = np.abs(img_old_arr[:h, :w].astype(float) - img_new_arr[:h, :w].astype(float))
    pct = round(np.sum(diff_arr.max(axis=2) > 15) / (h * w) * 100, 2)
    
    if pct > 0.5:
        print(f"  🚩 변경 감지 ({pct}%)")
        create_diff_image(old_path, new_path, diff_path) # 빨간 강조 이미지 생성
        diff_url = upload_to_imgbb(diff_path) # 강조 이미지만 업로드
        log_to_notion(name, url, pct, diff_url) # 노션 전송
        new_path.replace(old_path)
    else:
        print(f"  ✓ 변경 없음 ({pct}%)")

def main():
    for t in TARGETS: 
        try: check_target(t)
        except Exception as e: print(f"  ❌ 에러: {e}")

if __name__ == "__main__":
    main()
