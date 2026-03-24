"""
Liquipediaから各チームの最新ロースターを取得してDBを修正するスクリプト
既存のロスターを全削除→正確なデータで再投入
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import time
import re

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

client = httpx.Client(timeout=30)


def supabase_get(table: str, params: dict = None) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = client.get(url, params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def supabase_delete(table: str, params: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    resp = client.delete(url, headers=HEADERS)
    return resp.status_code


def supabase_insert(table: str, data: list[dict]) -> list[dict]:
    if not data:
        return []
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())
    normalized = [{k: row.get(k) for k in all_keys} for row in data]

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.post(url, json=normalized, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  エラー: {table} - {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def fetch_liquipedia_page(title: str) -> str | None:
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }
    try:
        resp = client.get(url, params=params, headers=LIQUIPEDIA_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                revisions = page.get("revisions", [])
                if revisions:
                    return revisions[0].get("*", "")
    except Exception as e:
        print(f"    Liquipedia取得エラー: {e}")
    return None


def parse_team_roster(wikitext: str) -> list[dict]:
    """チームページからアクティブロスターを抽出"""
    members = []

    # {{TeamCard}} 内のプレイヤーを探す
    # パターン: |p1=PlayerName |p1flag=xx |p1role=xxx
    # または {{TeamCard/slot |player=Name |flag=xx |role=xxx}}

    # 方法1: |pN= パターン（TeamCard2形式）
    for i in range(1, 8):
        pattern = rf"\|p{i}\s*=\s*([^\n|]+)"
        match = re.search(pattern, wikitext)
        if match:
            player_name = match.group(1).strip()
            if player_name and player_name.lower() not in ("", "tbd", "n/a"):
                role_pattern = rf"\|p{i}role\s*=\s*([^\n|]+)"
                role_match = re.search(role_pattern, wikitext)
                role = role_match.group(1).strip() if role_match else None

                flag_pattern = rf"\|p{i}flag\s*=\s*([^\n|]+)"
                flag_match = re.search(flag_pattern, wikitext)
                flag = flag_match.group(1).strip() if flag_match else None

                members.append({
                    "ign": player_name,
                    "role": role,
                    "nationality": flag,
                })

    # 方法2: {{RosterCard}} 形式
    if not members:
        # 複数のRosterCardを探す
        roster_pattern = r"\{\{RosterCard[^}]*\|player\s*=\s*([^|}\n]+)"
        for match in re.finditer(roster_pattern, wikitext):
            player_name = match.group(1).strip()
            if player_name and player_name.lower() not in ("", "tbd", "n/a"):
                members.append({"ign": player_name, "role": None, "nationality": None})

    # 方法3: 「Active」セクション内のプレイヤーリンクを探す
    if not members:
        # {{ActiveRoster の後のプレイヤーを探す
        active_section = re.search(r"===?\s*Active\s*===?(.*?)(?:===?\s*(?:Former|Inactive|Coach)|$)", wikitext, re.DOTALL | re.IGNORECASE)
        if active_section:
            section_text = active_section.group(1)
            # [[PlayerName]] パターン
            for match in re.finditer(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", section_text):
                name = match.group(1).strip()
                if name and not name.startswith("File:") and not name.startswith("Category:"):
                    members.append({"ign": name, "role": None, "nationality": None})

    return members


def main():
    print("=== ロースター修正スクリプト ===")
    print()

    # 既存データ取得
    teams = supabase_get("teams", {"select": "id,slug,name,liquipedia_url"})
    players = supabase_get("players", {"select": "id,slug,ign"})

    team_map = {t["slug"]: t for t in teams}
    # ignで検索できるようにする（大文字小文字無視）
    player_by_ign = {}
    for p in players:
        player_by_ign[p["ign"].lower()] = p

    print(f"チーム数: {len(teams)}")
    print(f"選手数: {len(players)}")

    # 既存ロスターを全削除
    print("\n既存ロスター削除中...")
    # DELETEポリシーを追加する必要があるかも
    # まず全ロスターのIDを取得
    rosters = supabase_get("team_rosters", {"select": "id"})
    if rosters:
        # 全件削除
        for r in rosters:
            client.delete(
                f"{SUPABASE_URL}/rest/v1/team_rosters?id=eq.{r['id']}",
                headers=HEADERS,
            )
        print(f"  {len(rosters)} 件削除")

    # 各チームのLiquipediaページからロスター取得
    print("\n各チームのロスター取得中...")
    new_rosters = []
    unmatched = []

    for team in teams:
        lp_url = team.get("liquipedia_url", "")
        if not lp_url:
            continue

        page_name = lp_url.split("/apexlegends/")[-1] if "/apexlegends/" in lp_url else None
        if not page_name:
            continue

        print(f"\n  {team['name']}...")
        wiki = fetch_liquipedia_page(page_name)
        time.sleep(2)

        if not wiki:
            print("    ページ取得失敗")
            continue

        members = parse_team_roster(wiki)
        if not members:
            print("    ロスター抽出できず")
            continue

        print(f"    メンバー: {[m['ign'] for m in members]}")

        for member in members:
            ign_lower = member["ign"].lower()
            player = player_by_ign.get(ign_lower)

            if player:
                new_rosters.append({
                    "team_id": team["id"],
                    "player_id": player["id"],
                    "role": member.get("role"),
                    "joined_at": "2025-01-01",
                    "is_substitute": False,
                })
                print(f"      ✓ {member['ign']} → マッチ")
            else:
                unmatched.append({
                    "team": team["name"],
                    "team_slug": team["slug"],
                    "ign": member["ign"],
                    "role": member.get("role"),
                    "nationality": member.get("nationality"),
                })
                print(f"      ✗ {member['ign']} → DB未登録")

    # マッチしたロスターを投入
    if new_rosters:
        result = supabase_insert("team_rosters", new_rosters)
        print(f"\n\nロスター投入: {len(result)} 件")

    # 未登録選手を新規追加
    if unmatched:
        print(f"\n\n=== DB未登録の選手 {len(unmatched)} 人 → 新規追加 ===")
        new_players = []
        new_roster_pending = []

        for u in unmatched:
            slug = u["ign"].lower().replace(" ", "-").replace(".", "").replace("_", "-")
            # 重複チェック
            if slug in [p.get("slug") for p in new_players]:
                continue

            player_data = {
                "slug": slug,
                "ign": u["ign"],
                "region": "APAC_N",  # デフォルト
                "is_active": True,
                "liquipedia_url": f"https://liquipedia.net/apexlegends/{u['ign'].replace(' ', '_')}",
            }

            if u.get("nationality"):
                nat = u["nationality"].upper()
                player_data["nationality"] = nat[:2]
                if nat in ("US", "CA", "AU", "BR"):
                    player_data["region"] = "NA"
                elif nat in ("SE", "NO", "DK", "FI", "DE", "FR", "GB", "UK", "ES", "IT", "PL", "RU"):
                    player_data["region"] = "EMEA"

            new_players.append(player_data)
            new_roster_pending.append({
                "team_slug": u["team_slug"],
                "player_slug": slug,
            })

        if new_players:
            result = supabase_insert("players", new_players)
            print(f"  新規選手追加: {len(result)} 人")

            # 追加した選手のロスターも紐付け
            new_player_ids = {p["slug"]: p["id"] for p in result}
            extra_rosters = []
            for rp in new_roster_pending:
                pid = new_player_ids.get(rp["player_slug"])
                tid = team_map.get(rp["team_slug"], {}).get("id")
                if pid and tid:
                    extra_rosters.append({
                        "team_id": tid,
                        "player_id": pid,
                        "role": None,
                        "joined_at": "2025-01-01",
                        "is_substitute": False,
                    })
            if extra_rosters:
                result = supabase_insert("team_rosters", extra_rosters)
                print(f"  追加ロスター: {len(result)} 件")

    print("\n\n=== 完了 ===")


if __name__ == "__main__":
    main()
