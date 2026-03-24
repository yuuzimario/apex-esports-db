"""
2026年最新ロースターを手動で正確に設定するスクリプト
リサーチ結果に基づく
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
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
        print(f"  エラー: {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


# =============================================
# 2026年3月時点の最新ロースター（リサーチ結果）
# =============================================
CURRENT_ROSTERS = {
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
        {"ign": "Prycyy", "nationality": "JP"},
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
    # Alliance (EMEA)
    "alliance": [
        {"ign": "Hakis", "nationality": "SE", "role": "IGL"},
        {"ign": "Unlucky", "nationality": "DE"},
        {"ign": "akku", "nationality": "DE"},
    ],
}

# TSMは2026年2月にロスター解散
# DarkZeroはNRGに買収されて消滅
# Cloud9もロスター不在


def main():
    print("=== 2026最新ロースター設定 ===\n")

    # 既存データ取得
    teams = supabase_get("teams", {"select": "id,slug,name"})
    players = supabase_get("players", {"select": "id,slug,ign"})

    team_map = {t["slug"]: t for t in teams}
    player_by_ign = {}
    for p in players:
        player_by_ign[p["ign"].lower()] = p

    # 既存ロスターを全削除
    print("既存ロスター全削除...")
    rosters = supabase_get("team_rosters", {"select": "id"})
    for r in rosters:
        client.delete(f"{SUPABASE_URL}/rest/v1/team_rosters?id=eq.{r['id']}", headers=HEADERS)
    print(f"  {len(rosters)} 件削除完了\n")

    # 新規選手追加が必要なリスト
    new_players_to_add = []
    new_rosters = []
    stats = {"matched": 0, "new": 0}

    for team_slug, members in CURRENT_ROSTERS.items():
        team = team_map.get(team_slug)
        if not team:
            print(f"  チーム未登録: {team_slug}")
            continue

        print(f"{team['name']}:")
        for member in members:
            ign_lower = member["ign"].lower()
            player = player_by_ign.get(ign_lower)

            if player:
                print(f"  ✓ {member['ign']} (既存)")
                new_rosters.append({
                    "team_id": team["id"],
                    "player_id": player["id"],
                    "role": member.get("role"),
                    "joined_at": "2026-01-01",
                    "is_substitute": False,
                })
                stats["matched"] += 1
            else:
                print(f"  + {member['ign']} (新規追加)")
                slug = member["ign"].lower().replace(" ", "-").replace(".", "").replace("_", "-")
                nat = member.get("nationality", "JP")
                region = "APAC_N"
                if nat in ("US", "CA", "AU", "BR"):
                    region = "NA"
                elif nat in ("SE", "NO", "DK", "FI", "DE", "FR", "GB", "ES", "IT"):
                    region = "EMEA"

                new_players_to_add.append({
                    "slug": slug,
                    "ign": member["ign"],
                    "nationality": nat,
                    "region": region,
                    "role": member.get("role"),
                    "is_active": True,
                    "liquipedia_url": f"https://liquipedia.net/apexlegends/{member['ign'].replace(' ', '_')}",
                    "_team_id": team["id"],  # 後でロスターに使う
                })
                stats["new"] += 1

    # 新規選手を投入
    if new_players_to_add:
        # _team_idを一時保存して削除
        team_id_map = {}
        clean_players = []
        for p in new_players_to_add:
            team_id_map[p["slug"]] = p.pop("_team_id")
            clean_players.append(p)

        result = supabase_insert("players", clean_players)
        print(f"\n新規選手 {len(result)} 人追加完了")

        for p in result:
            tid = team_id_map.get(p["slug"])
            if tid:
                new_rosters.append({
                    "team_id": tid,
                    "player_id": p["id"],
                    "role": p.get("role"),
                    "joined_at": "2026-01-01",
                    "is_substitute": False,
                })

    # ロスター一括投入
    if new_rosters:
        result = supabase_insert("team_rosters", new_rosters)
        print(f"\nロスター {len(result)} 件投入完了")

    # TSMを非アクティブに
    tsm = team_map.get("tsm")
    if tsm:
        client.patch(
            f"{SUPABASE_URL}/rest/v1/teams?id=eq.{tsm['id']}",
            json={"is_active": True},  # チームページは残す。ロスターは空にする
            headers={**HEADERS, "Prefer": "return=representation"},
        )

    print(f"\n=== 完了 ===")
    print(f"マッチした選手: {stats['matched']}")
    print(f"新規追加選手: {stats['new']}")
    print(f"ロスター合計: {len(new_rosters)}")
    print(f"\n注意: ロスターデータがないチームは空のままです")
    print(f"（FENNEL, RIDDLE ORDER, GROWGaming, Meteor, Aquarium, GangRabbiT, WhiteGrimReaper等）")


if __name__ == "__main__":
    main()
