"""
Battlefy ALGS Year 6 — リーダーボードの全リージョンデータ取得
前回EMEAのみ成功、残り3リージョン + qualified teams をリトライ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
import httpx

CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"
CF_BASE = "https://d3q4fnxloga6gz.cloudfront.net"
SEASON_SLUG = "algs-season-6"

REGIONS = ["americas", "asia-pacific-north", "asia-pacific-south", "europe-middle-east-and-africa"]
REGION_SHORT = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Origin": "https://battlefy.com",
    "Referer": "https://battlefy.com/",
    "Accept": "application/json",
}

# 既存の発見データを読み込む
with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
    discovery = json.load(f)

events = discovery.get("events", [])
leaderboards = discovery.get("leaderboards", {})


def fetch_with_retry(client, url, max_retries=3):
    """リトライ付きfetch"""
    for attempt in range(max_retries):
        try:
            resp = client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"    [{resp.status_code}] attempt {attempt+1}")
        except Exception as e:
            print(f"    Timeout attempt {attempt+1}: {e}")
            time.sleep(2)
    return None


def main():
    print("=" * 70)
    print("Battlefy リーダーボード全リージョン取得")
    print("=" * 70)

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        # リーダーボード取得
        print("\n--- リーダーボード (leaderboardSeasonID=177) ---")
        lb_id = 177
        for region in REGIONS:
            rs = REGION_SHORT[region]
            key = f"Online Opens|{rs}"

            if key in leaderboards and leaderboards[key].get("total", 0) > 0:
                print(f"  {rs}: 既に{leaderboards[key]['total']}チーム取得済み — スキップ")
                continue

            url = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_id}?region={region}&offset=0&limit=200"
            print(f"  {rs}: ", end="")
            data = fetch_with_retry(client, url)
            if data and data.get("total", 0) > 0:
                total = data["total"]
                teams = data.get("data", [])

                # ページネーション
                while len(teams) < total:
                    offset = len(teams)
                    url2 = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_id}?region={region}&offset={offset}&limit=200"
                    data2 = fetch_with_retry(client, url2)
                    if data2 and data2.get("data"):
                        teams.extend(data2["data"])
                    else:
                        break

                leaderboards[key] = {
                    "total": total,
                    "teams": teams,
                    "lb_id": lb_id,
                    "region": region,
                }
                print(f"{total} teams ({len(teams)} fetched)")
                for t in teams[:5]:
                    name = t.get("name", "?")
                    score = t.get("score", "?")
                    rank = t.get("rank", "?")
                    players = [b.get("name", "?") for b in t.get("breakdown", [])]
                    print(f"    {rank}. {name} ({score} pts) — {', '.join(players)}")
            else:
                print("no data (all retries failed)")

        # Qualified teams取得
        print("\n--- Qualified teams ---")
        qualified = discovery.get("qualified_teams", {})
        for ev in events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            if ename in qualified and len(qualified[ename]) > 0:
                print(f"  {ename}: 既に{len(qualified[ename])}チーム取得済み — スキップ")
                continue

            url = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{eid}"
            print(f"  {ename}: ", end="")
            data = fetch_with_retry(client, url)
            if data and isinstance(data, list) and len(data) > 0:
                qualified[ename] = data
                print(f"{len(data)} teams")
                for t in data[:3]:
                    print(f"    {t.get('name', '?')} | placement: {t.get('placement', '?')}")
            else:
                print("no data")

        # Leaderboard をイベントIDでも試す（Online Opens以外用）
        print("\n--- イベント別リーダーボード ---")
        for ev in events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            et = ev["event_type"]
            if et == "Online Opens":
                continue  # 既にlb_id=177で取得済み

            for region in REGIONS:
                rs = REGION_SHORT[region]
                key = f"{ename}|{rs}"
                if key in leaderboards and leaderboards[key].get("total", 0) > 0:
                    continue

                # イベントIDでリーダーボード
                url = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{eid}?region={region}&offset=0&limit=200"
                data = fetch_with_retry(client, url, max_retries=1)
                if data and data.get("total", 0) > 0:
                    total = data["total"]
                    teams = data.get("data", [])
                    leaderboards[key] = {"total": total, "teams": teams, "region": region}
                    print(f"  {key}: {total} teams")

        discovery["leaderboards"] = leaderboards
        discovery["qualified_teams"] = qualified

    # === サマリー ===
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_teams_all = 0
    total_players_all = set()

    print(f"\nリーダーボード: {len(leaderboards)} datasets")
    for key, lb in sorted(leaderboards.items()):
        total = lb.get("total", 0)
        teams = lb.get("teams", [])
        total_teams_all += len(teams)
        for t in teams:
            for b in t.get("breakdown", []):
                total_players_all.add(b.get("subID", ""))
        print(f"  {key}: {total} teams, {len(teams)} fetched")

    print(f"\nQualified teams: {len(qualified)} events")
    for key, qt in sorted(qualified.items()):
        print(f"  {key}: {len(qt)} teams")

    print(f"\n合計: {total_teams_all} チームエントリ, {len(total_players_all)} ユニークプレイヤー")

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(discovery, f, ensure_ascii=False, indent=2, default=str)

    file_size = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n保存完了: {OUTPUT_FILE} ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
