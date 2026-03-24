"""
Liquipedia + 手動データからSupabaseに初期データを投入するスクリプト
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import time
import json
import re

# Supabase設定
SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

LIQUIPEDIA_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app; contact@apex-esports-db.com)",
    "Accept-Encoding": "gzip",
}

client = httpx.Client(timeout=30)

def supabase_upsert(table: str, data: list[dict]) -> list[dict]:
    """Supabaseにデータをupsert（全レコードのキーを統一）"""
    if not data:
        return []
    # 全レコードのキーを統一（不足キーはNoneで埋める）
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())
    normalized = []
    for row in data:
        normalized.append({k: row.get(k) for k in all_keys})

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = client.post(url, json=normalized, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  エラー: {table} - {resp.status_code}: {resp.text}")
        return []
    return resp.json()


def fetch_liquipedia_page(title: str) -> str | None:
    """LiquipediaからページのWikiテキストを取得（レート制限: 2秒間隔）"""
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
        else:
            print(f"  Liquipedia API エラー: {resp.status_code}")
    except Exception as e:
        print(f"  Liquipedia取得エラー: {e}")
    time.sleep(2)  # レート制限
    return None


def parse_team_wiki(wikitext: str) -> dict:
    """Wikiテキストからチーム情報を抽出"""
    info = {}
    # |location=Japan みたいなパターン
    patterns = {
        "region": r"\|region\s*=\s*(.+?)[\n|]",
        "location": r"\|location\s*=\s*(.+?)[\n|]",
        "twitter": r"\|twitter\s*=\s*(.+?)[\n|]",
        "website": r"\|website\s*=\s*(.+?)[\n|]",
        "founded": r"\|created\s*=\s*(.+?)[\n|]",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, wikitext, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()
    return info


def parse_player_wiki(wikitext: str) -> dict:
    """Wikiテキストからプレイヤー情報を抽出"""
    info = {}
    patterns = {
        "id": r"\|id\s*=\s*(.+?)[\n|]",
        "name": r"\|name\s*=\s*(.+?)[\n|]",
        "romanized_name": r"\|romanized_name\s*=\s*(.+?)[\n|]",
        "nationality": r"\|country\s*=\s*(.+?)[\n|]",
        "role": r"\|role\s*=\s*(.+?)[\n|]",
        "twitter": r"\|twitter\s*=\s*(.+?)[\n|]",
        "twitch": r"\|twitch\s*=\s*(.+?)[\n|]",
        "youtube": r"\|youtube\s*=\s*(.+?)[\n|]",
        "team": r"\|team\s*=\s*(.+?)[\n|]",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, wikitext, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if val and val.lower() != "n/a":
                info[key] = val
    return info


# ==========================================
# APAC North 主要チーム（FIGHT NT + ALGS参加チーム）
# ==========================================
APAC_NORTH_TEAMS = [
    {"name": "FENNEL", "short_name": "FL", "slug": "fennel", "liquipedia": "FENNEL"},
    {"name": "REIGNITE", "short_name": "RIG", "slug": "reignite", "liquipedia": "Reignite"},
    {"name": "RIDDLE ORDER", "short_name": "RO", "slug": "riddle-order", "liquipedia": "RIDDLE_ORDER"},
    {"name": "REJECT", "short_name": "RC", "slug": "reject", "liquipedia": "REJECT"},
    {"name": "FNATIC", "short_name": "FNC", "slug": "fnatic", "liquipedia": "Fnatic"},
    {"name": "NOEZ FOXX", "short_name": "NF", "slug": "noez-foxx", "liquipedia": "NOEZ_FOXX"},
    {"name": "ENTER FORCE.36", "short_name": "EF36", "slug": "enter-force-36", "liquipedia": "ENTER_FORCE.36"},
    {"name": "SBI e-Sports", "short_name": "SBI", "slug": "sbi-esports", "liquipedia": "SBI_e-Sports"},
    {"name": "REALIZE", "short_name": "RLZ", "slug": "realize", "liquipedia": "REALIZE_(Japanese_Team)"},
    {"name": "Dreadnoughtus.", "short_name": "DRD", "slug": "dreadnoughtus", "liquipedia": "Dreadnoughtus."},
    {"name": "GROWGaming", "short_name": "GRW", "slug": "grow-gaming", "liquipedia": "GROWGaming"},
    {"name": "Meteor", "short_name": "MTR", "slug": "meteor", "liquipedia": "Meteor_(Japanese_Team)"},
    {"name": "Aquarium", "short_name": "AQR", "slug": "aquarium", "liquipedia": "Aquarium_(Japanese_Team)"},
    {"name": "GangRabbiT", "short_name": "GRT", "slug": "gangrabbit", "liquipedia": "GangRabbiT"},
    {"name": "Dory", "short_name": "DRY", "slug": "dory", "liquipedia": "Dory"},
    {"name": "WhiteGrimReaper", "short_name": "WGR", "slug": "whitegrimreaper", "liquipedia": "WhiteGrimReaper"},
    {"name": "GUNSO", "short_name": "GNS", "slug": "gunso", "liquipedia": "GUNSO"},
    {"name": "SukiSukiScream", "short_name": "SSS", "slug": "sukisukiscream", "liquipedia": "SukiSukiScream"},
    {"name": "BLACK Sheeps", "short_name": "BS", "slug": "black-sheeps", "liquipedia": "BLACK_Sheeps"},
    {"name": "BIG BOYS", "short_name": "BB", "slug": "big-boys", "liquipedia": "BIG_BOYS"},
    {"name": "LawsonTicketXone", "short_name": "LTX", "slug": "lawsonticketxone", "liquipedia": "LawsonTicketXone"},
]

# 主要な海外チーム（ALGS上位チーム）
GLOBAL_TEAMS = [
    {"name": "TSM", "short_name": "TSM", "slug": "tsm", "region": "NA", "liquipedia": "TSM"},
    {"name": "DarkZero Esports", "short_name": "DZ", "slug": "darkzero", "region": "NA", "liquipedia": "DarkZero_Esports"},
    {"name": "NRG Esports", "short_name": "NRG", "slug": "nrg", "region": "NA", "liquipedia": "NRG_Esports"},
    {"name": "Cloud9", "short_name": "C9", "slug": "cloud9", "region": "NA", "liquipedia": "Cloud9"},
    {"name": "OpTic Gaming", "short_name": "OPT", "slug": "optic-gaming", "region": "NA", "liquipedia": "OpTic_Gaming"},
    {"name": "Luminosity Gaming", "short_name": "LG", "slug": "luminosity", "region": "NA", "liquipedia": "Luminosity_Gaming"},
    {"name": "Alliance", "short_name": "ALL", "slug": "alliance", "region": "EMEA", "liquipedia": "Alliance"},
    {"name": "Acend", "short_name": "ACE", "slug": "acend", "region": "EMEA", "liquipedia": "Acend"},
    {"name": "Team Burger", "short_name": "BUR", "slug": "team-burger", "region": "NA", "liquipedia": "Team_Burger"},
    {"name": "Moist Esports", "short_name": "MST", "slug": "moist-esports", "region": "NA", "liquipedia": "Moist_Esports"},
]


def seed_teams():
    """チームデータを投入"""
    print("\n=== チームデータ投入 ===")
    teams_data = []

    # APAC Northチーム
    for team in APAC_NORTH_TEAMS:
        team_data = {
            "slug": team["slug"],
            "name": team["name"],
            "short_name": team["short_name"],
            "region": "APAC_N",
            "is_active": True,
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{team['liquipedia']}",
        }

        # Liquipediaから追加情報を取得
        print(f"  取得中: {team['name']}...")
        wiki = fetch_liquipedia_page(team["liquipedia"])
        if wiki:
            info = parse_team_wiki(wiki)
            if info.get("twitter"):
                team_data["twitter_url"] = f"https://x.com/{info['twitter']}"
            if info.get("website"):
                url = info["website"]
                if not url.startswith("http"):
                    url = f"https://{url}"
                team_data["website_url"] = url
        time.sleep(2)  # レート制限

        teams_data.append(team_data)

    # グローバルチーム
    for team in GLOBAL_TEAMS:
        team_data = {
            "slug": team["slug"],
            "name": team["name"],
            "short_name": team["short_name"],
            "region": team["region"],
            "is_active": True,
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{team['liquipedia']}",
        }

        print(f"  取得中: {team['name']}...")
        wiki = fetch_liquipedia_page(team["liquipedia"])
        if wiki:
            info = parse_team_wiki(wiki)
            if info.get("twitter"):
                team_data["twitter_url"] = f"https://x.com/{info['twitter']}"
            if info.get("website"):
                url = info["website"]
                if not url.startswith("http"):
                    url = f"https://{url}"
                team_data["website_url"] = url
        time.sleep(2)

        teams_data.append(team_data)

    result = supabase_upsert("teams", teams_data)
    print(f"  投入完了: {len(result)} チーム")
    return {t["slug"]: t["id"] for t in result}


# APAC North 主要選手（Liquipediaで確認済み）
APAC_NORTH_PLAYERS = [
    # FENNEL
    {"ign": "Selly", "slug": "selly", "team": "fennel", "nationality": "KR", "liquipedia": "Selly"},
    {"ign": "Cptjack", "slug": "cptjack", "team": "fennel", "nationality": "KR", "liquipedia": "Cptjack"},
    {"ign": "Restia", "slug": "restia", "team": "fennel", "nationality": "KR", "liquipedia": "Restia"},
    # FNATIC
    {"ign": "YukaF", "slug": "yukaf", "team": "fnatic", "nationality": "JP", "liquipedia": "YukaF"},
    {"ign": "Fisker", "slug": "fisker", "team": "fnatic", "nationality": "JP", "liquipedia": "Fisker"},
    {"ign": "Putend", "slug": "putend", "team": "fnatic", "nationality": "JP", "liquipedia": "Putend"},
    # RIDDLE ORDER
    {"ign": "obly", "slug": "obly", "team": "riddle-order", "nationality": "JP", "liquipedia": "Obly"},
    {"ign": "Mande", "slug": "mande-ro", "team": "riddle-order", "nationality": "JP", "liquipedia": "Mande_(Japanese_player)"},
    {"ign": "StylishNoob", "slug": "stylishnoob", "team": "riddle-order", "nationality": "JP", "liquipedia": "StylishNoob"},
    # REJECT
    {"ign": "Taisheen", "slug": "taisheen", "team": "reject", "nationality": "JP", "liquipedia": "Taisheen"},
    {"ign": "Parkha", "slug": "parkha", "team": "reject", "nationality": "KR", "liquipedia": "Parkha"},
    {"ign": "Ftyan", "slug": "ftyan", "team": "reject", "nationality": "JP", "liquipedia": "Ftyan"},
    # REIGNITE
    {"ign": "Lejetta", "slug": "lejetta", "team": "reignite", "nationality": "JP", "liquipedia": "Lejetta"},
    {"ign": "S4R", "slug": "s4r", "team": "reignite", "nationality": "JP", "liquipedia": "S4R"},
    {"ign": "CLaNz", "slug": "clanz", "team": "reignite", "nationality": "JP", "liquipedia": "CLaNz"},
    # SBI e-Sports
    {"ign": "mundo", "slug": "mundo", "team": "sbi-esports", "nationality": "JP", "liquipedia": "Mundo_(Japanese_player)"},
    {"ign": "KeePley", "slug": "keepley", "team": "sbi-esports", "nationality": "JP", "liquipedia": "KeePley"},
    {"ign": "rakunn", "slug": "rakunn", "team": "sbi-esports", "nationality": "JP", "liquipedia": "Rakunn"},
    # ENTER FORCE.36
    {"ign": "Baru", "slug": "baru", "team": "enter-force-36", "nationality": "KR", "liquipedia": "Baru"},
    {"ign": "Jusna", "slug": "jusna", "team": "enter-force-36", "nationality": "KR", "liquipedia": "Jusna"},
    {"ign": "Juno", "slug": "juno-ef", "team": "enter-force-36", "nationality": "KR", "liquipedia": "Juno_(Korean_Player)"},
    # NOEZ FOXX
    {"ign": "Aimbot", "slug": "aimbot-nf", "team": "noez-foxx", "nationality": "JP", "liquipedia": "Aimbot_(Japanese_player)"},
    {"ign": "Teleq", "slug": "teleq", "team": "noez-foxx", "nationality": "JP", "liquipedia": "Teleq"},
    {"ign": "Keni", "slug": "keni", "team": "noez-foxx", "nationality": "JP", "liquipedia": "Keni"},
]


def seed_players(team_ids: dict):
    """選手データを投入"""
    print("\n=== 選手データ投入 ===")
    players_data = []

    for p in APAC_NORTH_PLAYERS:
        player_data = {
            "slug": p["slug"],
            "ign": p["ign"],
            "nationality": p["nationality"],
            "region": "APAC_N",
            "is_active": True,
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{p['liquipedia']}",
        }

        # Liquipediaから追加情報を取得
        print(f"  取得中: {p['ign']}...")
        wiki = fetch_liquipedia_page(p["liquipedia"])
        if wiki:
            info = parse_player_wiki(wiki)
            if info.get("name"):
                player_data["real_name"] = info["name"]
            if info.get("romanized_name"):
                player_data["real_name_ja"] = info["romanized_name"]
            elif info.get("name") and p["nationality"] == "JP":
                # 日本人選手の場合、nameがそのまま日本語名の可能性
                player_data["real_name_ja"] = info["name"]
            if info.get("role"):
                player_data["role"] = info["role"]
            if info.get("twitter"):
                player_data["twitter_url"] = f"https://x.com/{info['twitter']}"
            if info.get("twitch"):
                player_data["twitch_url"] = f"https://twitch.tv/{info['twitch']}"
            if info.get("youtube"):
                player_data["youtube_url"] = f"https://youtube.com/{info['youtube']}"
        time.sleep(2)  # レート制限

        players_data.append(player_data)

    result = supabase_upsert("players", players_data)
    print(f"  投入完了: {len(result)} 選手")

    # player_id マッピング
    player_ids = {p["slug"]: p["id"] for p in result}

    # チームロスター紐付け
    print("\n=== ロスター紐付け ===")
    rosters = []
    for p in APAC_NORTH_PLAYERS:
        player_id = player_ids.get(p["slug"])
        team_id = team_ids.get(p["team"])
        if player_id and team_id:
            rosters.append({
                "team_id": team_id,
                "player_id": player_id,
                "role": None,
                "joined_at": "2025-01-01",  # 正確な日付はLiquipediaから後で修正
                "is_substitute": False,
            })

    if rosters:
        result = supabase_upsert("team_rosters", rosters)
        print(f"  投入完了: {len(result)} ロスター")


# 主要大会データ
TOURNAMENTS = [
    {
        "slug": "algs-year-4-championship",
        "name": "ALGS Year 4 Championship",
        "name_ja": "ALGS Year 4 チャンピオンシップ",
        "series": "ALGS",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2025-04-24",
        "end_date": "2025-04-27",
        "prize_pool_usd": 2000000,
        "is_lan": True,
        "location": "Los Angeles, USA",
        "status": "completed",
    },
    {
        "slug": "algs-year-5-split-1-pro-league-apac-n",
        "name": "ALGS Year 5 Split 1 Pro League - APAC North",
        "name_ja": "ALGS Year 5 Split 1 プロリーグ - APAC North",
        "series": "ALGS",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2026-01-15",
        "end_date": "2026-03-15",
        "is_lan": False,
        "status": "completed",
    },
    {
        "slug": "algs-year-5-split-2-pro-league-apac-n",
        "name": "ALGS Year 5 Split 2 Pro League - APAC North",
        "name_ja": "ALGS Year 5 Split 2 プロリーグ - APAC North",
        "series": "ALGS",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2026-04-01",
        "end_date": "2026-06-01",
        "is_lan": False,
        "status": "ongoing",
    },
    {
        "slug": "escl-apex-legends-2026",
        "name": "ESCL APEX Legends 2026",
        "name_ja": "ESCL APEX Legends 2026",
        "series": "ESCL",
        "event_type": "community",
        "region": "APAC_N",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "is_lan": False,
        "status": "ongoing",
    },
]


def seed_tournaments():
    """大会データを投入"""
    print("\n=== 大会データ投入 ===")
    result = supabase_upsert("tournaments", TOURNAMENTS)
    print(f"  投入完了: {len(result)} 大会")


def main():
    print("APEX Esports DB - 初期データ投入開始")
    print("=" * 50)

    # 1. チーム投入
    team_ids = seed_teams()

    # 2. 選手投入 + ロスター紐付け
    seed_players(team_ids)

    # 3. 大会投入
    seed_tournaments()

    print("\n" + "=" * 50)
    print("初期データ投入完了！")
    print(f"  チーム: {len(APAC_NORTH_TEAMS) + len(GLOBAL_TEAMS)} 件")
    print(f"  選手: {len(APAC_NORTH_PLAYERS)} 件")
    print(f"  大会: {len(TOURNAMENTS)} 件")


if __name__ == "__main__":
    main()
