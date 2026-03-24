"""
2026年APEX競技シーン 全チーム・全ロスター投入スクリプト
リサーチ結果に基づく網羅的データ
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

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "logos")
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app; contact@apex-esports-db.com)",
}

client = httpx.Client(timeout=30)


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
        print(f"  INSERT エラー: {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


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


def fetch_lp_logo(page_name, team_slug):
    """Liquipediaからロゴを取得してpublic/logos/に保存"""
    filepath = os.path.join(LOGO_DIR, f"{team_slug}.png")
    if os.path.exists(filepath):
        return f"/logos/{team_slug}.png"

    try:
        # ページ取得
        params = {"action": "query", "titles": page_name, "prop": "revisions", "rvprop": "content", "format": "json"}
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

        # ロゴファイル名抽出
        match = re.search(r"\|image\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            match = re.search(r"\|imagedark\s*=\s*(.+?)[\n|]", wiki, re.IGNORECASE)
        if not match:
            return None

        logo_file = match.group(1).strip()

        # 画像URL取得
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
            print(f"    ロゴ保存: {team_slug}.png ({len(img_resp.content)} bytes)")
            return f"/logos/{team_slug}.png"
    except Exception as e:
        print(f"    ロゴ取得エラー: {e}")
    return None


# =============================================
# 2026年 全チーム定義（リサーチ結果）
# =============================================
ALL_TEAMS_2026 = [
    # === APAC North ===
    {"slug": "zeta-division", "name": "ZETA DIVISION", "short_name": "ZETA", "region": "APAC_N", "lp": "ZETA_DIVISION"},
    {"slug": "crazy-thieves", "name": "Crazy Thieves", "short_name": "CT", "region": "APAC_N", "lp": "Crazy_Thieves"},
    {"slug": "scarz", "name": "SCARZ", "short_name": "SZ", "region": "APAC_N", "lp": "SCARZ"},

    # === Americas ===
    {"slug": "oblivion", "name": "Oblivion", "short_name": "OBL", "region": "NA", "lp": "Oblivion_(American_Team)"},

    # === EMEA ===
    {"slug": "aurora-gaming", "name": "Aurora Gaming", "short_name": "ARR", "region": "EMEA", "lp": "Aurora_Gaming"},
    {"slug": "gaimin-gladiators", "name": "Gaimin Gladiators", "short_name": "GG", "region": "EMEA", "lp": "Gaimin_Gladiators"},
    {"slug": "faze-clan", "name": "FaZe Clan", "short_name": "FaZe", "region": "EMEA", "lp": "FaZe_Clan"},
    {"slug": "team-falcons", "name": "Team Falcons", "short_name": "FLCN", "region": "EMEA", "lp": "Team_Falcons"},

    # === APAC South ===
    {"slug": "rrq", "name": "Rex Regum Qeon", "short_name": "RRQ", "region": "APAC_S", "lp": "Rex_Regum_Qeon"},
]

# 既存チームで再アクティブ化+ロスター更新が必要なもの
REACTIVATE_TEAMS = {
    "fennel": {"name": "FENNEL"},  # BLACK Sheepsロスターを獲得
    "riddle-order": {"name": "RIDDLE ORDER"},  # 新ロスター
    "black-sheeps": None,  # FENNELに吸収 → 非アクティブのまま
}

# =============================================
# 2026年 全ロスター定義
# =============================================
ALL_ROSTERS_2026 = {
    # === APAC North ===
    "fnatic": [
        {"ign": "Kernerl", "nationality": "JP", "role": "IGL"},
        {"ign": "ILY", "nationality": "KR"},
        {"ign": "Ein", "nationality": "JP"},
    ],
    "enter-force-36": [
        {"ign": "Cinap", "nationality": "KR"},
        {"ign": "Jusna", "nationality": "KR"},
        {"ign": "Obly", "nationality": "JP"},
    ],
    "reject": [
        {"ign": "Sharky", "nationality": "JP"},
        {"ign": "Prycyy", "nationality": "AU"},
        {"ign": "Emtee", "nationality": "JP"},
    ],
    "sbi-esports": [
        {"ign": "Fukusima", "nationality": "JP"},
        {"ign": "ImMikeyyyz", "nationality": "JP"},
        {"ign": "egoist", "nationality": "JP"},
    ],
    "noez-foxx": [
        {"ign": "MiaK", "nationality": "JP"},
        {"ign": "kakigoori7", "nationality": "JP"},
        {"ign": "gavomk", "nationality": "JP"},
    ],
    "dreadnoughtus": [
        {"ign": "jirozon", "nationality": "JP"},
        {"ign": "yamatai", "nationality": "JP"},
        {"ign": "Duckz", "nationality": "JP"},
    ],
    "dory": [
        {"ign": "Hiromune", "nationality": "JP"},
        {"ign": "sho", "nationality": "JP"},
        {"ign": "KatsuKing", "nationality": "JP"},
    ],
    "reignite": [
        {"ign": "DizzyMizLizyy", "nationality": "JP"},
        {"ign": "788", "nationality": "JP"},
        {"ign": "Curihara", "nationality": "JP"},
    ],
    "fennel": [
        {"ign": "izzxxv", "nationality": "JP"},
        {"ign": "Sumiyoshii", "nationality": "JP"},
        {"ign": "14L0st", "nationality": "JP"},
    ],
    "lawsonticketxone": [
        {"ign": "5CG", "nationality": "JP"},
        {"ign": "wqtagashi", "nationality": "JP"},
        {"ign": "Right", "nationality": "JP"},
    ],
    "zeta-division": [
        {"ign": "YukaF", "nationality": "JP"},
        {"ign": "Mike", "nationality": "JP"},
        {"ign": "satuki", "nationality": "JP"},
    ],
    "crazy-thieves": [
        {"ign": "Phony", "nationality": "US"},
        {"ign": "Genburten", "nationality": "AU"},
        {"ign": "Verhulst", "nationality": "US"},
    ],

    # === Americas ===
    "nrg": [
        {"ign": "sSikezz", "nationality": "US"},
        {"ign": "iiTzTimmy", "nationality": "US", "role": "IGL"},
        {"ign": "YanYa", "nationality": "US"},
    ],
    "oblivion": [
        {"ign": "Blinkzr", "nationality": "US"},
        {"ign": "Monsoon", "nationality": "US"},
        {"ign": "FunFPS", "nationality": "US"},
    ],

    # === EMEA ===
    "alliance": [
        {"ign": "Hakis", "nationality": "SE", "role": "IGL"},
        {"ign": "Unlucky", "nationality": "DE"},
        {"ign": "akku", "nationality": "DE"},
    ],
    "aurora-gaming": [
        {"ign": "Effect", "nationality": "RU"},
        {"ign": "ojrein", "nationality": "RU"},
        {"ign": "Hardecki", "nationality": "RU"},
    ],
    "gaimin-gladiators": [
        {"ign": "Lufka", "nationality": "PL"},
        {"ign": "Blasts", "nationality": "DK"},
        {"ign": "Zaine", "nationality": "GB"},
    ],
    "faze-clan": [
        {"ign": "Naghz", "nationality": "SE"},
        {"ign": "Jmw", "nationality": "SE"},
        {"ign": "Sinetic", "nationality": "SE"},
    ],
    "team-falcons": [
        {"ign": "Mande", "nationality": "NO"},
        {"ign": "Kswinnie", "nationality": "SA"},
        {"ign": "Resultuh", "nationality": "US"},
    ],

    # === APAC South ===
    "rrq": [
        {"ign": "StrafingFlame", "nationality": "ID", "role": "IGL"},
        {"ign": "Prycyy_RRQ", "nationality": "AU"},
        {"ign": "Metro", "nationality": "AU"},
    ],
}

# 大会データ追加
ADDITIONAL_TOURNAMENTS = [
    {
        "slug": "algs-year-5-championship-2026",
        "name": "ALGS Year 5 Championship 2026",
        "name_ja": "ALGS Year 5 チャンピオンシップ 2026",
        "series": "ALGS",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2026-01-16",
        "end_date": "2026-01-19",
        "prize_pool_usd": 2000000,
        "is_lan": True,
        "location": "Sapporo, Japan",
        "status": "completed",
    },
    {
        "slug": "algs-year-6-split-1-pro-league-apac-n",
        "name": "ALGS Year 6 Split 1 Pro League - APAC North",
        "name_ja": "ALGS Year 6 Split 1 プロリーグ - APAC North",
        "series": "ALGS",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2026-04-05",
        "end_date": "2026-06-15",
        "prize_pool_usd": None,
        "is_lan": False,
        "location": None,
        "status": "ongoing",
    },
    {
        "slug": "algs-year-6-split-1-pro-league-americas",
        "name": "ALGS Year 6 Split 1 Pro League - Americas",
        "name_ja": "ALGS Year 6 Split 1 プロリーグ - Americas",
        "series": "ALGS",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2026-04-05",
        "end_date": "2026-06-15",
        "prize_pool_usd": None,
        "is_lan": False,
        "location": None,
        "status": "ongoing",
    },
    {
        "slug": "algs-year-6-split-1-pro-league-emea",
        "name": "ALGS Year 6 Split 1 Pro League - EMEA",
        "name_ja": "ALGS Year 6 Split 1 プロリーグ - EMEA",
        "series": "ALGS",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2026-04-05",
        "end_date": "2026-06-15",
        "prize_pool_usd": None,
        "is_lan": False,
        "location": None,
        "status": "ongoing",
    },
]


def get_region(nationality):
    if nationality in ("JP", "KR", "TW", "HK"):
        return "APAC_N"
    elif nationality in ("US", "CA", "AU", "BR", "MX"):
        return "NA"
    elif nationality in ("SE", "NO", "DK", "FI", "DE", "FR", "GB", "ES", "IT", "PL", "RU", "SA"):
        return "EMEA"
    elif nationality in ("ID", "TH", "PH", "SG", "MY", "VN", "IN"):
        return "APAC_S"
    return "APAC_N"


def main():
    print("=== 2026年 APEX競技シーン 全データ投入 ===\n")

    # 既存データ取得
    existing_teams = supabase_get("teams", {"select": "id,slug,name,is_active"})
    existing_players = supabase_get("players", {"select": "id,slug,ign"})
    existing_rosters = supabase_get("team_rosters", {"select": "id,team_id"})

    team_map = {t["slug"]: t for t in existing_teams}
    player_by_ign = {p["ign"].lower(): p for p in existing_players}

    # === 1. 新規チーム追加 ===
    print("=== 新規チーム追加 ===")
    new_teams = []
    for t in ALL_TEAMS_2026:
        if t["slug"] not in team_map:
            new_teams.append({
                "slug": t["slug"],
                "name": t["name"],
                "short_name": t["short_name"],
                "region": t["region"],
                "is_active": True,
                "liquipedia_url": f"https://liquipedia.net/apexlegends/{t['lp']}",
            })
            print(f"  + {t['name']}")

    if new_teams:
        result = supabase_upsert("teams", new_teams)
        print(f"  {len(result)} チーム追加完了")
        for t in result:
            team_map[t["slug"]] = t

    # === 2. FENNELを再アクティブ化 ===
    print("\n=== チーム再アクティブ化 ===")
    for slug, info in REACTIVATE_TEAMS.items():
        if info and slug in team_map:
            resp = client.patch(
                f"{SUPABASE_URL}/rest/v1/teams?slug=eq.{slug}",
                json={"is_active": True},
                headers={**HEADERS, "Prefer": "return=representation"},
            )
            if resp.status_code in (200, 204):
                print(f"  ✓ {info['name']} 再アクティブ化")
                team_map[slug]["is_active"] = True

    # === 3. ロゴ取得（新規チーム） ===
    print("\n=== ロゴ取得（3秒間隔） ===")
    for t in ALL_TEAMS_2026:
        slug = t["slug"]
        team = team_map.get(slug)
        if not team:
            continue

        # 既存ロゴチェック
        existing = supabase_get("teams", {"select": "logo_url", "slug": f"eq.{slug}"})
        if existing and existing[0].get("logo_url"):
            print(f"  スキップ（既存）: {t['name']}")
            continue

        print(f"  {t['name']}...")
        logo_path = fetch_lp_logo(t["lp"], slug)
        if logo_path:
            client.patch(
                f"{SUPABASE_URL}/rest/v1/teams?slug=eq.{slug}",
                json={"logo_url": logo_path},
                headers={**HEADERS, "Prefer": "return=representation"},
            )
            print(f"    ロゴ設定完了")

    # === 4. 既存ロスター削除 ===
    print("\n=== 既存ロスター全削除 ===")
    rosters = supabase_get("team_rosters", {"select": "id"})
    for r in rosters:
        client.delete(f"{SUPABASE_URL}/rest/v1/team_rosters?id=eq.{r['id']}", headers=HEADERS)
    print(f"  {len(rosters)} 件削除")

    # === 5. 全ロスター投入 ===
    print("\n=== 全ロスター投入 ===")
    all_new_rosters = []
    new_players = []

    for team_slug, members in ALL_ROSTERS_2026.items():
        team = team_map.get(team_slug)
        if not team:
            print(f"  チーム未登録: {team_slug}")
            continue

        print(f"\n  {team.get('name', team_slug)}:")
        for m in members:
            ign_lower = m["ign"].lower()
            player = player_by_ign.get(ign_lower)

            if player:
                print(f"    ✓ {m['ign']}")
                all_new_rosters.append({
                    "team_id": team["id"],
                    "player_id": player["id"],
                    "role": m.get("role"),
                    "joined_at": "2026-01-01",
                    "is_substitute": False,
                })
            else:
                print(f"    + {m['ign']} (新規)")
                p_slug = m["ign"].lower().replace(" ", "-").replace(".", "").replace("_", "-")
                region = get_region(m.get("nationality", "JP"))
                new_players.append({
                    "slug": p_slug,
                    "ign": m["ign"],
                    "nationality": m.get("nationality", "JP"),
                    "region": region,
                    "role": m.get("role"),
                    "is_active": True,
                    "_team_id": team["id"],
                })

    # 新規選手投入
    if new_players:
        tid_map = {}
        clean = []
        for p in new_players:
            tid_map[p["slug"]] = p.pop("_team_id")
            clean.append(p)

        result = supabase_insert("players", clean)
        print(f"\n  新規選手 {len(result)} 人追加")

        for p in result:
            player_by_ign[p["ign"].lower()] = p
            tid = tid_map.get(p["slug"])
            if tid:
                all_new_rosters.append({
                    "team_id": tid,
                    "player_id": p["id"],
                    "role": p.get("role"),
                    "joined_at": "2026-01-01",
                    "is_substitute": False,
                })

    # ロスター一括投入
    if all_new_rosters:
        result = supabase_insert("team_rosters", all_new_rosters)
        print(f"\n  ロスター {len(result)} 件投入完了")

    # === 6. 大会データ追加 ===
    print("\n=== 大会データ追加 ===")
    result = supabase_upsert("tournaments", ADDITIONAL_TOURNAMENTS)
    print(f"  {len(result)} 大会追加")

    # === 最終統計 ===
    print("\n" + "=" * 50)
    final_teams = supabase_get("teams", {"select": "id,slug,name,logo_url,is_active"})
    final_rosters = supabase_get("team_rosters", {"select": "team_id"})
    final_players = supabase_get("players", {"select": "id"})
    final_tournaments = supabase_get("tournaments", {"select": "id"})

    active = [t for t in final_teams if t.get("is_active")]
    with_roster = set(r["team_id"] for r in final_rosters)
    with_logo = sum(1 for t in active if t.get("logo_url"))

    print(f"アクティブチーム: {len(active)}")
    print(f"  ロゴあり: {with_logo}")
    print(f"  ロスターあり: {sum(1 for t in active if t['id'] in with_roster)}")
    print(f"総選手数: {len(final_players)}")
    print(f"総大会数: {len(final_tournaments)}")
    print()

    # ロスターなしチーム一覧
    no_roster = [t for t in active if t["id"] not in with_roster]
    if no_roster:
        print("ロスターなし:")
        for t in no_roster:
            print(f"  - {t['name']}")


if __name__ == "__main__":
    main()
