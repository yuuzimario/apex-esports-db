"""
Step 1: ALGS公式API (prod-api.algstools.com) から Year 6 Split 1 全ロースターを取得
認証不要の公開API。各リージョン30チーム × 4リージョン = 120チーム
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
from datetime import datetime

BASE_URL = "https://prod-api.algstools.com/v1"
OUTPUT_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Year 6 Split 1 Pro League の eventId（探索で発見済み）
EVENTS = {
    "APAC_N": "01KH745JD7DQQQC978CZM83R0Z",
    "APAC_S": "01KH74518P0RXFSHRZJDD7Y0SA",
    "EMEA":   "01KH43605SY64S6ED2VC1TQCDN",
    "NA":     "01KH2GCEGZH7ZYY3FFKW8R4BAF",
}

# リージョン名の正規化マッピング
REGION_MAP = {
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-africa": "EMEA",
    "americas": "NA",
}

client = httpx.Client(timeout=30)


def fetch_teams(region_key, event_id):
    """1リージョンのチーム+ロースターを取得"""
    url = f"{BASE_URL}/events/{event_id}/teams"
    resp = client.get(url)
    if resp.status_code != 200:
        print(f"  エラー: {resp.status_code}")
        return []

    data = resp.json()
    raw_teams = data.get("teams", data) if isinstance(data, dict) else data
    teams = []
    for t in raw_teams:
        # 選手情報を整理
        players = []
        for p in t.get("players", []):
            players.append({
                "algs_id": p["id"],
                "ign": p["name"],
                "role": p.get("role", "player"),
                "image_url": p.get("frontImage"),
            })

        teams.append({
            "algs_team_id": t["teamId"],
            "algs_team_version_id": t["teamVersionId"],
            "name": t["name"],
            "short_name": t.get("shortName", ""),
            "region": region_key,
            "api_region": t.get("region", ""),
            "group": t.get("group", ""),
            "logo_dark": t.get("logoDark"),
            "logo_light": t.get("logoLight"),
            "disbanded": t.get("disbanded", False),
            "players": players,
        })

    return teams


def main():
    print("=" * 60)
    print("Step 1: ALGS公式API ロースター取得")
    print("=" * 60)

    all_data = {
        "source": "prod-api.algstools.com",
        "fetched_at": datetime.now().isoformat(),
        "season": "Year 6 Split 1 Pro League",
        "regions": {},
    }

    total_teams = 0
    total_players = 0

    for region_key, event_id in EVENTS.items():
        print(f"\n--- {region_key} (eventId: {event_id}) ---")
        teams = fetch_teams(region_key, event_id)
        all_data["regions"][region_key] = teams

        player_count = sum(len(t["players"]) for t in teams)
        total_teams += len(teams)
        total_players += player_count

        print(f"  チーム: {len(teams)}, 選手: {player_count}")
        for t in teams:
            ps = ", ".join(p["ign"] for p in t["players"][:3])
            extra = f" +{len(t['players'])-3}" if len(t["players"]) > 3 else ""
            print(f"    {t['name']}: {ps}{extra}")

    # 保存
    output_path = os.path.join(OUTPUT_DIR, "algs_rosters.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"合計: {total_teams} チーム, {total_players} 選手")
    print(f"保存先: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
