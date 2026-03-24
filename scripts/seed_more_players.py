"""
残りのAPAC Northチーム + 海外チームの選手を投入するスクリプト
Liquipedia APIレート制限: 2秒間隔を厳守
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
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())
    normalized = [{k: row.get(k) for k in all_keys} for row in data]

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = client.post(url, json=normalized, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  エラー: {table} - {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def supabase_get(table: str, params: dict = None) -> list[dict]:
    """Supabaseからデータ取得"""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = client.get(url, params=params or {}, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return []


def fetch_liquipedia_page(title: str) -> str | None:
    """LiquipediaからページのWikiテキストを取得"""
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


def fetch_liquipedia_image_url(filename: str) -> str | None:
    """Liquipediaから画像の直接URLを取得"""
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        resp = client.get(url, params=params, headers=LIQUIPEDIA_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    return imageinfo[0].get("url")
    except Exception as e:
        print(f"    画像URL取得エラー: {e}")
    return None


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
        "image": r"\|image\s*=\s*(.+?)[\n|]",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, wikitext, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if val and val.lower() != "n/a" and val.lower() != "":
                info[key] = val
    return info


def parse_team_logo(wikitext: str) -> str | None:
    """Wikiテキストからチームロゴファイル名を抽出"""
    match = re.search(r"\|image\s*=\s*(.+?)[\n|]", wikitext, re.IGNORECASE)
    if match:
        val = match.group(1).strip()
        if val and val.lower() != "n/a":
            return val
    return None


# ==========================================
# 追加選手データ（残りのAPAC Northチーム）
# ==========================================
ADDITIONAL_PLAYERS = [
    # REALIZE
    {"ign": "Ras", "slug": "ras", "team": "realize", "nationality": "JP", "liquipedia": "Ras"},
    {"ign": "Saku", "slug": "saku", "team": "realize", "nationality": "JP", "liquipedia": "Saku"},
    {"ign": "takaf", "slug": "takaf", "team": "realize", "nationality": "JP", "liquipedia": "Takaf"},
    # Dreadnoughtus.
    {"ign": "Zeder", "slug": "zeder", "team": "dreadnoughtus", "nationality": "JP", "liquipedia": "Zeder"},
    {"ign": "ATR", "slug": "atr", "team": "dreadnoughtus", "nationality": "JP", "liquipedia": "ATR"},
    {"ign": "Runa", "slug": "runa-drd", "team": "dreadnoughtus", "nationality": "JP", "liquipedia": "Runa_(Japanese_player)"},
    # GROWGaming
    {"ign": "Buz", "slug": "buz", "team": "grow-gaming", "nationality": "JP", "liquipedia": "Buz"},
    {"ign": "KeepAim", "slug": "keepaim", "team": "grow-gaming", "nationality": "JP", "liquipedia": "KeepAim"},
    {"ign": "aceu7", "slug": "aceu7", "team": "grow-gaming", "nationality": "JP", "liquipedia": "Aceu7"},
    # Meteor
    {"ign": "Shomaru", "slug": "shomaru", "team": "meteor", "nationality": "JP", "liquipedia": "Shomaru"},
    {"ign": "NicoNico", "slug": "niconico", "team": "meteor", "nationality": "JP", "liquipedia": "NicoNico_(Japanese_player)"},
    {"ign": "Eriyori", "slug": "eriyori", "team": "meteor", "nationality": "JP", "liquipedia": "Eriyori"},
    # Aquarium
    {"ign": "IShiGaKi", "slug": "ishigaki", "team": "aquarium", "nationality": "JP", "liquipedia": "IShiGaKi"},
    {"ign": "Mimi", "slug": "mimi-aqr", "team": "aquarium", "nationality": "JP", "liquipedia": "Mimi_(Japanese_player)"},
    {"ign": "Koyful", "slug": "koyful", "team": "aquarium", "nationality": "JP", "liquipedia": "Koyful"},
    # GangRabbiT
    {"ign": "Waigoren", "slug": "waigoren", "team": "gangrabbit", "nationality": "JP", "liquipedia": "Waigoren"},
    {"ign": "Refa", "slug": "refa", "team": "gangrabbit", "nationality": "JP", "liquipedia": "Refa"},
    {"ign": "VaNish", "slug": "vanish-grt", "team": "gangrabbit", "nationality": "JP", "liquipedia": "VaNish_(Japanese_player)"},
    # Dory
    {"ign": "LiaqN", "slug": "liaqn", "team": "dory", "nationality": "JP", "liquipedia": "LiaqN"},
    {"ign": "K4miy4m4", "slug": "k4miy4m4", "team": "dory", "nationality": "JP", "liquipedia": "K4miy4m4"},
    {"ign": "deiru", "slug": "deiru", "team": "dory", "nationality": "JP", "liquipedia": "Deiru"},
    # WhiteGrimReaper
    {"ign": "Dizzy", "slug": "dizzy-wgr", "team": "whitegrimreaper", "nationality": "JP", "liquipedia": "Dizzy_(Japanese_player)"},
    {"ign": "Karonpe", "slug": "karonpe", "team": "whitegrimreaper", "nationality": "JP", "liquipedia": "Karonpe"},
    {"ign": "FuruBon", "slug": "furubon", "team": "whitegrimreaper", "nationality": "JP", "liquipedia": "FuruBon"},

    # === 海外主要チーム ===
    # TSM
    {"ign": "ImperialHal", "slug": "imperialhal", "team": "tsm", "nationality": "US", "liquipedia": "ImperialHal"},
    {"ign": "Verhulst", "slug": "verhulst", "team": "tsm", "nationality": "US", "liquipedia": "Verhulst"},
    {"ign": "Reps", "slug": "reps", "team": "tsm", "nationality": "US", "liquipedia": "Reps"},
    # DarkZero
    {"ign": "Genburten", "slug": "genburten", "team": "darkzero", "nationality": "AU", "liquipedia": "Genburten"},
    {"ign": "Zer0", "slug": "zer0-dz", "team": "darkzero", "nationality": "AU", "liquipedia": "Zer0"},
    {"ign": "Brynn", "slug": "brynn", "team": "darkzero", "nationality": "US", "liquipedia": "Brynn"},
    # NRG
    {"ign": "sweet", "slug": "sweet-nrg", "team": "nrg", "nationality": "US", "liquipedia": "Sweet"},
    {"ign": "Nafen", "slug": "nafen", "team": "nrg", "nationality": "US", "liquipedia": "Nafen"},
    {"ign": "rocker", "slug": "rocker", "team": "nrg", "nationality": "US", "liquipedia": "Rocker"},
    # Cloud9
    {"ign": "Zach", "slug": "zach-c9", "team": "cloud9", "nationality": "US", "liquipedia": "Zach_(American_player)"},
    {"ign": "Naughty", "slug": "naughty", "team": "cloud9", "nationality": "US", "liquipedia": "Naughty"},
    {"ign": "Albralelie", "slug": "albralelie", "team": "cloud9", "nationality": "US", "liquipedia": "Albralelie"},
    # Alliance
    {"ign": "Hakis", "slug": "hakis", "team": "alliance", "nationality": "SE", "liquipedia": "Hakis"},
    {"ign": "Yuki", "slug": "yuki-all", "team": "alliance", "nationality": "JP", "liquipedia": "Yuki_(Japanese_player)"},
    {"ign": "Vaifs", "slug": "vaifs", "team": "alliance", "nationality": "SE", "liquipedia": "Vaifs"},
]


def get_team_ids() -> dict:
    """既存のチームIDマッピングを取得"""
    teams = supabase_get("teams", {"select": "id,slug"})
    return {t["slug"]: t["id"] for t in teams}


def get_existing_player_slugs() -> set:
    """既存の選手slugを取得"""
    players = supabase_get("players", {"select": "slug"})
    return {p["slug"] for p in players}


def seed_additional_players(team_ids: dict, existing_slugs: set):
    """追加選手を投入"""
    print("\n=== 追加選手データ投入 ===")
    players_data = []
    roster_data = []

    for p in ADDITIONAL_PLAYERS:
        if p["slug"] in existing_slugs:
            print(f"  スキップ（既存）: {p['ign']}")
            continue

        player_data = {
            "slug": p["slug"],
            "ign": p["ign"],
            "nationality": p["nationality"],
            "region": "APAC_N" if p["nationality"] in ("JP", "KR") else ("NA" if p["nationality"] in ("US", "CA", "AU") else "EMEA"),
            "is_active": True,
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{p['liquipedia']}",
        }

        print(f"  取得中: {p['ign']}...")
        wiki = fetch_liquipedia_page(p["liquipedia"])
        if wiki:
            info = parse_player_wiki(wiki)
            if info.get("name"):
                player_data["real_name"] = info["name"]
            if info.get("romanized_name"):
                player_data["real_name_ja"] = info["romanized_name"]
            elif info.get("name") and p["nationality"] == "JP":
                player_data["real_name_ja"] = info["name"]
            if info.get("role"):
                player_data["role"] = info["role"]
            if info.get("twitter"):
                player_data["twitter_url"] = f"https://x.com/{info['twitter']}"
            if info.get("twitch"):
                player_data["twitch_url"] = f"https://twitch.tv/{info['twitch']}"
            if info.get("youtube"):
                player_data["youtube_url"] = f"https://youtube.com/{info['youtube']}"

            # 選手画像
            if info.get("image"):
                img_url = fetch_liquipedia_image_url(info["image"])
                if img_url:
                    player_data["profile_image_url"] = img_url
                time.sleep(2)

        time.sleep(2)  # レート制限

        players_data.append(player_data)
        roster_data.append({
            "team_slug": p["team"],
            "player_slug": p["slug"],
        })

    if players_data:
        result = supabase_upsert("players", players_data)
        print(f"  投入完了: {len(result)} 選手")

        # ロスター紐付け
        player_ids = {p["slug"]: p["id"] for p in result}
        rosters = []
        for r in roster_data:
            pid = player_ids.get(r["player_slug"])
            tid = team_ids.get(r["team_slug"])
            if pid and tid:
                rosters.append({
                    "team_id": tid,
                    "player_id": pid,
                    "role": None,
                    "joined_at": "2025-01-01",
                    "is_substitute": False,
                })
        if rosters:
            result = supabase_upsert("team_rosters", rosters)
            print(f"  ロスター投入: {len(result)} 件")
    else:
        print("  投入する選手がありません")


def update_team_logos(team_ids: dict):
    """チームロゴURLを取得して更新"""
    print("\n=== チームロゴ取得 ===")

    # 既存チーム情報を取得
    teams = supabase_get("teams", {"select": "id,slug,liquipedia_url"})

    for team in teams:
        lp_url = team.get("liquipedia_url", "")
        if not lp_url:
            continue

        # URLからLiquipediaページ名を取得
        page_name = lp_url.split("/apexlegends/")[-1] if "/apexlegends/" in lp_url else None
        if not page_name:
            continue

        print(f"  ロゴ取得中: {team['slug']}...")
        wiki = fetch_liquipedia_page(page_name)
        if wiki:
            logo_file = parse_team_logo(wiki)
            if logo_file:
                # ロゴの直接URLを取得
                logo_url = fetch_liquipedia_image_url(logo_file)
                if logo_url:
                    # Supabaseでlogo_urlを更新
                    url = f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}"
                    headers = {**HEADERS, "Prefer": "return=representation"}
                    resp = client.patch(url, json={"logo_url": logo_url}, headers=headers)
                    if resp.status_code in (200, 204):
                        print(f"    ロゴ設定完了: {logo_file}")
                    else:
                        print(f"    ロゴ更新エラー: {resp.status_code}")
                time.sleep(2)
        time.sleep(2)


def main():
    print("APEX Esports DB - 追加データ投入")
    print("=" * 50)

    team_ids = get_team_ids()
    existing_slugs = get_existing_player_slugs()

    print(f"既存チーム: {len(team_ids)} 件")
    print(f"既存選手: {len(existing_slugs)} 人")

    # 1. 追加選手投入
    seed_additional_players(team_ids, existing_slugs)

    # 2. チームロゴ取得
    update_team_logos(team_ids)

    print("\n" + "=" * 50)
    print("追加データ投入完了！")


if __name__ == "__main__":
    main()
