"""
ロゴなし・ロスターなしのチームをLiquipediaから補完するスクリプト
レート制限: 3秒間隔で安全に取得
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
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

LIQUIPEDIA_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app; contact@apex-esports-db.com)",
    "Accept-Encoding": "gzip",
}

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "logos")
client = httpx.Client(timeout=30)
RATE_LIMIT = 3  # 3秒間隔


def supabase_get(table, params=None):
    resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


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
        print(f"  INSERT エラー: {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def supabase_patch(table, filter_str, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}"
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.patch(url, json=data, headers=headers)
    return resp.status_code in (200, 204)


def fetch_lp(title):
    """Liquipediaページ取得（レート制限準拠）"""
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {"action": "query", "titles": title, "prop": "revisions", "rvprop": "content", "format": "json"}
    try:
        resp = client.get(url, params=params, headers=LIQUIPEDIA_HEADERS)
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                revs = page.get("revisions", [])
                if revs:
                    return revs[0].get("*", "")
    except Exception as e:
        print(f"    LP取得エラー: {e}")
    return None


def fetch_lp_image_url(filename):
    """画像の直接URLを取得"""
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {"action": "query", "titles": f"File:{filename}", "prop": "imageinfo", "iiprop": "url", "format": "json"}
    try:
        resp = client.get(url, params=params, headers=LIQUIPEDIA_HEADERS)
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                info = page.get("imageinfo", [])
                if info:
                    return info[0].get("url")
    except Exception as e:
        print(f"    画像URL取得エラー: {e}")
    return None


def download_logo(team_slug, logo_url):
    """ロゴをダウンロードしてpublic/logos/に保存"""
    ext = logo_url.split(".")[-1].split("?")[0].lower()
    if ext not in ("png", "jpg", "jpeg", "svg", "webp"):
        ext = "png"
    filename = f"{team_slug}.{ext}"
    filepath = os.path.join(LOGO_DIR, filename)

    if os.path.exists(filepath):
        return f"/logos/{filename}"

    try:
        img_resp = client.get(logo_url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        if img_resp.status_code == 200 and len(img_resp.content) > 100:
            with open(filepath, "wb") as f:
                f.write(img_resp.content)
            print(f"    ロゴ保存: {filename} ({len(img_resp.content)} bytes)")
            return f"/logos/{filename}"
    except Exception as e:
        print(f"    ロゴDLエラー: {e}")
    return None


def extract_logo(wikitext):
    """Wikiテキストからロゴファイル名を抽出"""
    match = re.search(r"\|image\s*=\s*(.+?)[\n|]", wikitext, re.IGNORECASE)
    if match:
        val = match.group(1).strip()
        if val and val.lower() != "n/a" and "." in val:
            return val
    return None


def extract_roster(wikitext):
    """Wikiテキストからアクティブロスターを抽出（複数パターン対応）"""
    members = []

    # パターン1: |p1=, |p2=, |p3= （TeamCard2形式）
    for i in range(1, 8):
        match = re.search(rf"\|p{i}\s*=\s*([^\n|]+)", wikitext)
        if match:
            name = match.group(1).strip()
            if name and name.lower() not in ("", "tbd", "n/a"):
                flag_m = re.search(rf"\|p{i}flag\s*=\s*([^\n|]+)", wikitext)
                role_m = re.search(rf"\|p{i}role\s*=\s*([^\n|]+)", wikitext)
                members.append({
                    "ign": name,
                    "nationality": flag_m.group(1).strip()[:2].upper() if flag_m else None,
                    "role": role_m.group(1).strip() if role_m else None,
                })

    # パターン2: |player= 形式
    if not members:
        for match in re.finditer(r"\|player\s*=\s*([^\n|}\]]+)", wikitext):
            name = match.group(1).strip()
            if name and name.lower() not in ("", "tbd", "n/a") and ":" not in name:
                members.append({"ign": name, "nationality": None, "role": None})

    # パターン3: {{TeamCard/player |p=Name}} 形式
    if not members:
        for match in re.finditer(r"\{\{TeamCard/player\s*\|p\s*=\s*([^|}\n]+)", wikitext):
            name = match.group(1).strip()
            if name and name.lower() not in ("", "tbd", "n/a"):
                members.append({"ign": name, "nationality": None, "role": None})

    # 最初の3-4人だけ返す（サブ含む場合あり）
    return members[:4] if members else []


def main():
    print("=== 不足データ補完スクリプト（3秒間隔） ===\n")

    teams = supabase_get("teams", {"select": "id,slug,name,logo_url,liquipedia_url,is_active"})
    players = supabase_get("players", {"select": "id,slug,ign"})
    rosters = supabase_get("team_rosters", {"select": "team_id"})

    player_by_ign = {p["ign"].lower(): p for p in players}
    teams_with_roster = set(r["team_id"] for r in rosters)

    active_teams = [t for t in teams if t.get("is_active")]
    logo_missing = [t for t in active_teams if not t.get("logo_url")]
    roster_missing = [t for t in active_teams if t["id"] not in teams_with_roster]

    print(f"ロゴなし: {len(logo_missing)} チーム")
    print(f"ロスターなし: {len(roster_missing)} チーム")
    print()

    # 全チームを処理（ロゴorロスターが不足しているもの）
    teams_to_process = {t["slug"]: t for t in active_teams if not t.get("logo_url") or t["id"] not in teams_with_roster}

    for slug, team in teams_to_process.items():
        lp_url = team.get("liquipedia_url", "")
        page_name = lp_url.split("/apexlegends/")[-1] if "/apexlegends/" in lp_url else None
        if not page_name:
            print(f"\n{team['name']}: Liquipedia URLなし → スキップ")
            continue

        print(f"\n{team['name']}...")

        # Liquipediaページ取得
        wiki = fetch_lp(page_name)
        time.sleep(RATE_LIMIT)

        if not wiki:
            print("  ページ取得失敗")
            continue

        # === ロゴ取得 ===
        if not team.get("logo_url"):
            logo_file = extract_logo(wiki)
            if logo_file:
                logo_url = fetch_lp_image_url(logo_file)
                time.sleep(RATE_LIMIT)

                if logo_url:
                    local_path = download_logo(slug, logo_url)
                    if local_path:
                        supabase_patch("teams", f"id=eq.{team['id']}", {"logo_url": local_path})
                        print(f"  ロゴ設定完了: {local_path}")
            else:
                print("  ロゴなし（Liquipediaにも未登録）")

        # === ロスター取得 ===
        if team["id"] not in teams_with_roster:
            members = extract_roster(wiki)
            if members:
                print(f"  ロスター: {[m['ign'] for m in members]}")

                new_rosters = []
                new_players = []

                for m in members:
                    player = player_by_ign.get(m["ign"].lower())
                    if player:
                        new_rosters.append({
                            "team_id": team["id"],
                            "player_id": player["id"],
                            "role": m.get("role"),
                            "joined_at": "2026-01-01",
                            "is_substitute": False,
                        })
                        print(f"    ✓ {m['ign']}")
                    else:
                        # 新規選手
                        p_slug = m["ign"].lower().replace(" ", "-").replace(".", "").replace("_", "-")
                        nat = m.get("nationality") or "JP"
                        region = "APAC_N"
                        if nat in ("US", "CA", "AU", "BR"):
                            region = "NA"
                        elif nat in ("SE", "NO", "DK", "FI", "DE", "FR", "GB", "ES", "IT"):
                            region = "EMEA"

                        new_players.append({
                            "slug": p_slug,
                            "ign": m["ign"],
                            "nationality": nat,
                            "region": region,
                            "role": m.get("role"),
                            "is_active": True,
                            "liquipedia_url": f"https://liquipedia.net/apexlegends/{m['ign'].replace(' ', '_')}",
                            "_team_id": team["id"],
                        })
                        print(f"    + {m['ign']} (新規)")

                # 新規選手を投入
                if new_players:
                    tid_map = {}
                    clean = []
                    for p in new_players:
                        tid_map[p["slug"]] = p.pop("_team_id")
                        clean.append(p)
                    result = supabase_insert("players", clean)
                    for p in result:
                        player_by_ign[p["ign"].lower()] = p
                        tid = tid_map.get(p["slug"])
                        if tid:
                            new_rosters.append({
                                "team_id": tid,
                                "player_id": p["id"],
                                "role": p.get("role"),
                                "joined_at": "2026-01-01",
                                "is_substitute": False,
                            })

                # ロスター投入
                if new_rosters:
                    result = supabase_insert("team_rosters", new_rosters)
                    print(f"  ロスター {len(result)} 件投入")
                    for r in new_rosters:
                        teams_with_roster.add(r["team_id"])
            else:
                print("  ロスター抽出できず")

    print("\n\n=== 完了 ===")
    # 最終統計
    final_teams = supabase_get("teams", {"select": "id,slug,logo_url,is_active"})
    final_rosters = supabase_get("team_rosters", {"select": "team_id"})
    final_players = supabase_get("players", {"select": "id"})
    final_with_roster = set(r["team_id"] for r in final_rosters)
    active = [t for t in final_teams if t.get("is_active")]

    print(f"総チーム数: {len(active)}")
    print(f"ロゴあり: {sum(1 for t in active if t.get('logo_url'))}")
    print(f"ロスターあり: {sum(1 for t in active if t['id'] in final_with_roster)}")
    print(f"総選手数: {len(final_players)}")


if __name__ == "__main__":
    main()
