"""
全アクティブチームのロゴをLiquipediaから取得
既にロゴがあるチームはスキップ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import os
import re
import time
import json

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
os.makedirs(LOGO_DIR, exist_ok=True)

client = httpx.Client(timeout=30)

# チーム名 → Liquipediaページ名のマッピング（名前が違うケース用）
NAME_MAP = {
    "Crazy Thieves": "Crazy_Thieves",
    "GenG Esports": "Gen.G",
    "Team Falcons": "Team_Falcons",
    "Team Liquid": "Team_Liquid",
    "Team RRQ": "RRQ",
    "ShopifyRebellion": "Shopify_Rebellion",
    "NinjasinPyjamas": "Ninjas_in_Pyjamas",
    "GaiminGladiators": "Gaimin_Gladiators",
    "Gaimin Gladiators": "Gaimin_Gladiators",
    "Aurora Gaming": "Aurora_Gaming",
    "AURORA": "Aurora_(European_Team)",
    "ZETA DIVISION": "ZETA_DIVISION",
    "NOVO Esports": "NOVO_Esports",
    "Wolves Esports": "Wolves_Esports",
    "ROC Esports": "ROC_Esports",
    "Source Gaming": "Source_Gaming",
    "MAMMA MIA": "MAMMA_MIA",
    "Made In Heaven": "Made_In_Heaven",
    "Citadel Gaming": "Citadel_Gaming",
    "Pixel Lumina": "Pixel_Lumina",
    "GROW Gaming": "GROW_Gaming",
    "Grape Soda": "Grape_Soda",
    "Bearclaw Gaming": "Bearclaw_Gaming",
    "FIZ6 Gaming": "FIZ6_Gaming",
    "VK GAMING": "VK_Gaming",
    "Remarkable Team": "Remarkable_Team",
    "Inside The Ring": "Inside_The_Ring",
    "S8UL": "S8UL",
    "Relove DCG": "Relove_DCG",
    "Donut Shop": "Donut_Shop",
    "Purple Slushee": "Purple_Slushee",
    "Full XI": "Full_XI",
    "Men Of Culture": "Men_Of_Culture",
    "Nice Guys": "Nice_Guys",
    "Free Thinkers": "Free_Thinkers",
    "Zest Fest": "Zest_Fest",
    "RIDDLE ORDER": "RIDDLE_ORDER",
    "NOEZ FOXX": "NOEZ_FOXX",
    "ENTER FORCE.36": "ENTER_FORCE.36",
    "SBI e-Sports": "SBI_e-Sports",
    "KINOTROPE CLUB": "KINOTROPE_CLUB",
    "KINOTROPE gaming": "KINOTROPE_gaming",
    "Stay Healthy": "Stay_Healthy",
    "Havoc legends": "Havoc_legends",
    "ECLIPSE NEEVEPRO": "ECLIPSE_NEEVEPRO",
    "black hole": "Black_Hole_(Southeast_Asian_Team)",
    "Ctrl Alt Defeat": "Ctrl_Alt_Defeat",
}


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def fetch_logo_from_liquipedia(page_name, team_slug):
    """Liquipediaからロゴ画像をダウンロード"""
    filepath = os.path.join(LOGO_DIR, f"{team_slug}.png")
    if os.path.exists(filepath):
        return f"/logos/{team_slug}.png"

    try:
        # ページのwikitext取得
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
        for page in pages.values():
            if int(list(pages.keys())[0]) < 0:
                return None  # ページが存在しない
            revs = page.get("revisions", [])
            if revs:
                wiki = revs[0].get("*", "")

        if not wiki:
            return None

        # ロゴファイル名抽出（imagedarkを優先、なければimage）
        match = re.search(r"\|\s*imagedark\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            match = re.search(r"\|\s*image\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            return None

        logo_file = match.group(1).strip()
        if not logo_file or logo_file.lower() in ("", "n/a"):
            return None

        # 画像URLを取得
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
                    # ダウンロード
                    img_resp = client.get(img_url, headers=LP_HEADERS)
                    if img_resp.status_code == 200 and len(img_resp.content) > 100:
                        with open(filepath, "wb") as f:
                            f.write(img_resp.content)
                        return f"/logos/{team_slug}.png"

    except Exception as e:
        print(f"    エラー: {e}")

    return None


def main():
    print("=" * 60)
    print("全チームロゴ取得")
    print("=" * 60)

    # ロゴなしのアクティブチームを取得
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/teams",
        params={"select": "id,name,slug,logo_url", "is_active": "eq.true", "order": "name"},
        headers=HEADERS,
    )
    teams = resp.json()

    no_logo = [t for t in teams if not t.get("logo_url")]
    has_logo = [t for t in teams if t.get("logo_url")]
    print(f"全チーム: {len(teams)}, ロゴあり: {len(has_logo)}, ロゴなし: {len(no_logo)}")

    success = 0
    failed = []

    for i, team in enumerate(no_logo):
        name = team["name"]
        slug = team["slug"]

        # Liquipediaページ名を決定
        lp_name = NAME_MAP.get(name, name.replace(" ", "_"))

        print(f"  [{i+1}/{len(no_logo)}] {name} → {lp_name}...", end=" ")

        logo_url = fetch_logo_from_liquipedia(lp_name, slug)

        if logo_url:
            # DB更新
            client.patch(
                f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}",
                json={"logo_url": logo_url},
                headers={**HEADERS, "Prefer": "return=representation"},
            )
            print(f"✓ {logo_url}")
            success += 1
        else:
            # スペースなし版も試す
            alt_name = name.replace(" ", "")
            if alt_name != lp_name.replace("_", ""):
                logo_url = fetch_logo_from_liquipedia(alt_name, slug)
                if logo_url:
                    client.patch(
                        f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}",
                        json={"logo_url": logo_url},
                        headers={**HEADERS, "Prefer": "return=representation"},
                    )
                    print(f"✓ {logo_url} (alt)")
                    success += 1
                    continue

            print("✗")
            failed.append(name)

    print(f"\n{'=' * 60}")
    print(f"結果: {success}チーム取得成功 / {len(failed)}チーム失敗")
    if failed:
        print(f"\n取得失敗チーム:")
        for f_name in failed:
            print(f"  - {f_name}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
