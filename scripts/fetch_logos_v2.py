"""
ロゴ取得v2: Liquipedia検索APIで正しいページ名を見つけてからロゴ取得
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import os
import re
import time

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {"User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)"}
LOGO_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/public/logos"

client = httpx.Client(timeout=30)


def search_team_page(team_name):
    """Liquipedia検索APIでチームページを探す"""
    params = {
        "action": "opensearch",
        "search": team_name,
        "namespace": "0",
        "limit": "10",
        "format": "json",
    }
    resp = client.get(LP_API, params=params, headers=LP_HEADERS)
    time.sleep(2)
    if resp.status_code != 200:
        return None

    data = resp.json()
    if len(data) < 2 or not data[1]:
        return None

    # チーム名に近い結果を選ぶ
    norm_name = team_name.lower().replace(" ", "").replace(".", "").replace("-", "")
    for title in data[1]:
        norm_title = title.lower().replace(" ", "").replace(".", "").replace("-", "").replace("_", "")
        if norm_name in norm_title or norm_title in norm_name:
            return title
        # 部分一致
        if len(norm_name) >= 4 and norm_name[:4] in norm_title:
            return title

    return data[1][0] if data[1] else None


def get_logo_from_page(page_name, team_slug):
    """Liquipediaページからロゴを取得"""
    filepath = os.path.join(LOGO_DIR, f"{team_slug}.png")
    if os.path.exists(filepath):
        return f"/logos/{team_slug}.png"

    try:
        params = {
            "action": "query",
            "titles": page_name,
            "prop": "revisions",
            "rvprop": "content",
            "format": "json",
        }
        resp = client.get(LP_API, params=params, headers=LP_HEADERS)
        time.sleep(3)
        if resp.status_code != 200:
            return None

        wiki = ""
        pages = resp.json().get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if int(pid) < 0:
                return None
            revs = page.get("revisions", [])
            if revs:
                wiki = revs[0].get("*", "")

        if not wiki:
            return None

        # チームのInfoboxか確認
        if "Infobox team" not in wiki.lower() and "infobox team" not in wiki.lower():
            return None

        # ロゴファイル名（imagedark優先）
        match = re.search(r"\|\s*imagedark\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            match = re.search(r"\|\s*image\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            return None

        logo_file = match.group(1).strip()
        if not logo_file:
            return None

        # 画像URL取得
        params2 = {
            "action": "query",
            "titles": f"File:{logo_file}",
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
        resp2 = client.get(LP_API, params=params2, headers=LP_HEADERS)
        time.sleep(3)
        if resp2.status_code != 200:
            return None

        pages2 = resp2.json().get("query", {}).get("pages", {})
        for page2 in pages2.values():
            ii = page2.get("imageinfo", [])
            if ii:
                img_url = ii[0].get("url", "")
                if img_url:
                    img_resp = client.get(img_url, headers=LP_HEADERS)
                    if img_resp.status_code == 200 and len(img_resp.content) > 100:
                        with open(filepath, "wb") as f:
                            f.write(img_resp.content)
                        return f"/logos/{team_slug}.png"

    except Exception as e:
        print(f"      エラー: {e}")
    return None


def main():
    print("=" * 60)
    print("ロゴ取得v2（検索API使用）")
    print("=" * 60)

    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/teams",
        params={"select": "id,name,slug,logo_url", "is_active": "eq.true", "logo_url": "is.null", "order": "name"},
        headers=HEADERS,
    )
    no_logo = resp.json()
    print(f"ロゴなしチーム: {len(no_logo)}")

    success = 0
    failed = []

    for i, team in enumerate(no_logo):
        name = team["name"]
        slug = team["slug"]
        print(f"  [{i+1}/{len(no_logo)}] {name}...", end=" ")

        # 検索APIでページ名を探す
        page_name = search_team_page(name)
        if not page_name:
            print("✗ (ページ不明)")
            failed.append(name)
            continue

        print(f"→ {page_name}...", end=" ")

        # ロゴ取得
        logo_url = get_logo_from_page(page_name, slug)
        if logo_url:
            client.patch(
                f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}",
                json={"logo_url": logo_url},
                headers={**HEADERS, "Prefer": "return=representation"},
            )
            print(f"✓")
            success += 1
        else:
            print("✗ (ロゴなし)")
            failed.append(name)

    print(f"\n{'=' * 60}")
    print(f"結果: {success}成功 / {len(failed)}失敗")
    if failed:
        print(f"\n失敗チーム ({len(failed)}):")
        for f_name in failed:
            print(f"  - {f_name}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
