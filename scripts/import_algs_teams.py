"""
ALGS Year 6 チーム+ロスターをSupabaseに投入
algs_year6_teams.json を読み込んで処理
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import time
import re
import os

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

LP_HEADERS = {"User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)"}
LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "logos")

client = httpx.Client(timeout=30)

# インポート対象リージョン（コマンドライン引数で切替可能）
IMPORT_REGIONS = sys.argv[1:] if len(sys.argv) > 1 else ["APAC_N"]


def supabase_get(table, params=None):
    resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def supabase_upsert(table, data):
    if not data:
        return []
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())
    normalized = [{k: row.get(k) for k in all_keys} for row in data]
    headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=normalized, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  UPSERT エラー: {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def supabase_insert(table, data):
    if not data:
        return []
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())
    normalized = [{k: row.get(k) for k in all_keys} for row in data]
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=normalized, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー: {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def make_slug(name):
    """チーム名/選手名からslugを生成"""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "unknown"


def get_region(flag):
    """国旗コードからリージョンを推定"""
    flag = flag.upper()
    if flag in ("JP", "KR", "TW", "HK"):
        return "APAC_N"
    elif flag in ("US", "CA", "AU", "BR", "MX", "AR", "CL"):
        return "NA"
    elif flag in ("SE", "NO", "DK", "FI", "DE", "FR", "GB", "UK", "ES", "IT", "PL", "RU", "SA", "NL", "PT", "BE", "AT", "CH", "CZ", "HU", "RO", "BG", "RS", "HR", "UA", "GR", "TR", "IE", "AE"):
        return "EMEA"
    elif flag in ("ID", "TH", "PH", "SG", "MY", "VN", "IN", "CN", "HK", "TW", "NZ"):
        return "APAC_S"
    return "APAC_N"


def fetch_logo(lp_page_name, team_slug):
    """Liquipediaからロゴ取得（既存なら即返す）"""
    filepath = os.path.join(LOGO_DIR, f"{team_slug}.png")
    if os.path.exists(filepath):
        return f"/logos/{team_slug}.png"

    try:
        # ページ取得
        params = {"action": "query", "titles": lp_page_name, "prop": "revisions", "rvprop": "content", "format": "json"}
        resp = client.get("https://liquipedia.net/apexlegends/api.php", params=params, headers=LP_HEADERS)
        time.sleep(3)
        if resp.status_code != 200:
            return None

        wiki = ""
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            revs = page.get("revisions", [])
            if revs:
                wiki = revs[0].get("*", "")
        if not wiki:
            return None

        # ロゴファイル名
        match = re.search(r"\|image\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            return None
        logo_file = match.group(1).strip()

        # 画像URL
        params2 = {"action": "query", "titles": f"File:{logo_file}", "prop": "imageinfo", "iiprop": "url", "format": "json"}
        resp2 = client.get("https://liquipedia.net/apexlegends/api.php", params=params2, headers=LP_HEADERS)
        time.sleep(3)

        img_url = None
        pages2 = resp2.json().get("query", {}).get("pages", {})
        for page in pages2.values():
            info = page.get("imageinfo", [])
            if info:
                img_url = info[0].get("url")
        if not img_url:
            return None

        # ダウンロード
        img_resp = client.get(img_url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if img_resp.status_code == 200 and len(img_resp.content) > 100:
            with open(filepath, "wb") as f:
                f.write(img_resp.content)
            print(f"      ロゴ保存: {team_slug}.png")
            return f"/logos/{team_slug}.png"
    except Exception as e:
        print(f"      ロゴ取得エラー: {e}")
    return None


def main():
    print(f"=== ALGS Year 6 チーム投入 ===")
    print(f"対象リージョン: {', '.join(IMPORT_REGIONS)}\n")

    # JSONデータ読み込み
    json_path = os.path.join(os.path.dirname(__file__), "algs_year6_teams.json")
    with open(json_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    # 既存データ取得
    existing_teams = supabase_get("teams", {"select": "id,slug,name,is_active"})
    existing_players = supabase_get("players", {"select": "id,slug,ign"})

    team_map = {t["slug"]: t for t in existing_teams}
    player_by_ign = {p["ign"].lower(): p for p in existing_players}
    player_by_slug = {p["slug"]: p for p in existing_players}

    # 既存ロスター全削除
    print("既存ロスター全削除...")
    rosters = supabase_get("team_rosters", {"select": "id"})
    for r in rosters:
        client.delete(f"{SUPABASE_URL}/rest/v1/team_rosters?id=eq.{r['id']}", headers=HEADERS)
    print(f"  {len(rosters)} 件削除\n")

    # リージョンごとに処理
    all_rosters = []
    total_new_teams = 0
    total_new_players = 0

    for region in IMPORT_REGIONS:
        teams_data = all_data.get(region, [])
        if not teams_data:
            print(f"\n{region}: データなし")
            continue

        print(f"\n{'='*50}")
        print(f"  {region}: {len(teams_data)} チーム")
        print(f"{'='*50}")

        for t in teams_data:
            team_name = t["team"]
            slug = make_slug(team_name)
            lp_page = team_name.replace(" ", "_")

            print(f"\n  {team_name} ({slug}):")

            # チーム存在チェック
            team = team_map.get(slug)
            if not team:
                # 新規チーム追加
                team_data = {
                    "slug": slug,
                    "name": team_name,
                    "short_name": team_name[:5].upper() if len(team_name) <= 10 else team_name[:3].upper(),
                    "region": region,
                    "is_active": True,
                    "liquipedia_url": f"https://liquipedia.net/apexlegends/{lp_page}",
                }

                result = supabase_upsert("teams", [team_data])
                if result:
                    team = result[0]
                    team_map[slug] = team
                    total_new_teams += 1
                    print(f"    [新規チーム追加]")
                else:
                    print(f"    [チーム追加失敗]")
                    continue
            else:
                # 既存チームをアクティブに
                if not team.get("is_active"):
                    client.patch(
                        f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}",
                        json={"is_active": True},
                        headers={**HEADERS, "Prefer": "return=representation"},
                    )
                    print(f"    [再アクティブ化]")

            # 選手処理
            for p in t["players"]:
                ign = p["ign"]
                flag = p.get("flag", "")
                ign_lower = ign.lower()
                p_slug = make_slug(ign)

                player = player_by_ign.get(ign_lower) or player_by_slug.get(p_slug)
                if not player:
                    # 新規選手追加
                    player_region = get_region(flag) if flag else region
                    player_data = {
                        "slug": p_slug,
                        "ign": ign,
                        "nationality": flag.upper()[:2] if flag else None,
                        "region": player_region,
                        "is_active": True,
                    }
                    result = supabase_insert("players", [player_data])
                    if result:
                        player = result[0]
                        player_by_ign[ign_lower] = player
                        player_by_slug[p_slug] = player
                        total_new_players += 1
                        print(f"    + {ign} (新規)")
                    else:
                        print(f"    ✗ {ign} (追加失敗)")
                        continue
                else:
                    print(f"    ✓ {ign}")

                all_rosters.append({
                    "team_id": team["id"],
                    "player_id": player["id"],
                    "joined_at": "2026-01-01",
                    "is_substitute": False,
                })

    # ロスター一括投入
    print(f"\n\n=== ロスター投入 ===")
    if all_rosters:
        # バッチで投入（50件ずつ）
        total_inserted = 0
        for i in range(0, len(all_rosters), 50):
            batch = all_rosters[i:i+50]
            result = supabase_insert("team_rosters", batch)
            total_inserted += len(result)
        print(f"  {total_inserted} 件投入完了")

    # 最終統計
    print(f"\n{'='*50}")
    print(f"=== 完了 ===")
    final_teams = supabase_get("teams", {"select": "id,is_active"})
    final_players = supabase_get("players", {"select": "id"})
    active_teams = [t for t in final_teams if t.get("is_active")]
    print(f"新規チーム追加: {total_new_teams}")
    print(f"新規選手追加: {total_new_players}")
    print(f"アクティブチーム: {len(active_teams)}")
    print(f"総選手数: {len(final_players)}")


if __name__ == "__main__":
    main()
