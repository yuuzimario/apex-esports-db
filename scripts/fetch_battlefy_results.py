"""
Battlefy APIからOnline Opens/Challenger Circuit等の大会結果を取得
→ tournaments + tournament_results テーブルに投入

使い方:
  python fetch_battlefy_results.py --dry-run              # 確認のみ
  python fetch_battlefy_results.py --season 6             # Year 6のみ
  python fetch_battlefy_results.py --season 5             # Year 5のみ
  python fetch_battlefy_results.py                        # Year 5+6両方
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

MAJESTIC_BASE = "https://majestic.battlefy.com"
CF_NEW = "https://d3q4fnxloga6gz.cloudfront.net"
CF_OLD = "https://dtmwra1jsgyb0.cloudfront.net"

BF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://battlefy.com",
    "Referer": "https://battlefy.com/",
    "Accept": "application/json",
}

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
bf_client = httpx.Client(timeout=30, headers=BF_HEADERS)

REGION_MAP = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}

EVENT_TYPE_MAP = {
    "Online Opens": "open_qualifier",
    "Preseason Qualifiers": "open_qualifier",
    "ALGS Open": "open_qualifier",
    "Split 1 - Pro League": "pro_league",
    "Split 2 - Pro League": "pro_league",
    "Pro League Regular Season - Split 1": "pro_league",
    "Pro League Regular Season - Split 2": "pro_league",
    "Split 1 - Challenger Circuit": "challenger_circuit",
    "Split 2 - Challenger Circuit": "challenger_circuit",
    "Challenger Circuit - Split 1": "challenger_circuit",
    "Challenger Circuit - Split 2": "challenger_circuit",
    "Split 2 - PL Qualifiers": "open_qualifier",
    "Pro League Split 2 Qualifiers": "open_qualifier",
    "Pro League Playoffs - Split 1": "playoffs",
    "Pro League Playoffs - Split 2": "playoffs",
    "Midseason Playoffs": "playoffs",
    "Last Chance Qualifier": "open_qualifier",
    "Year 5 Championship": "championship",
    "Championship Group Stage": "championship",
    "BLGS Circuit": "community",
}


def normalize_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def supabase_get_all(table, params):
    all_data = []
    offset = 0
    while True:
        p = {**params, "limit": "1000", "offset": str(offset)}
        resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return all_data


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def fetch_season(year):
    """Battlefy Majestic APIからシーズン構造を取得"""
    slug = f"apex-legends-global-series-year-{year}"
    cache_file = os.path.join(CACHE_DIR, f"battlefy_year{year}_seasons.json")

    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if (time.time() - mtime) < 86400:  # 1日キャッシュ
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    resp = bf_client.get(f"{MAJESTIC_BASE}/algs/{slug}/seasons")
    if resp.status_code != 200:
        print(f"  シーズン取得失敗: {resp.status_code}")
        return None

    data = resp.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def fetch_leaderboard(season_slug, lb_id, region, limit=200):
    """リーダーボードからチームランキングを取得"""
    all_teams = []
    offset = 0
    while True:
        resp = bf_client.get(
            f"{CF_NEW}/algs/{season_slug}/team-leaderboards/{lb_id}",
            params={"region": region, "offset": str(offset), "limit": str(limit)},
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        teams = data.get("data", [])
        all_teams.extend(teams)
        if len(teams) < limit or offset + limit >= data.get("total", 0):
            break
        offset += limit
        time.sleep(1)
    return all_teams


def match_team(team_name, teams_by_norm):
    """チーム名マッチング"""
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]

    clean = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
    cn = normalize_name(clean)
    if cn and cn in teams_by_norm:
        return teams_by_norm[cn]

    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + team_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]

    for suffix in [" esports", " gaming", " e-sports", " esport", " gg"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]
        added = normalize_name(team_name + suffix)
        if added in teams_by_norm:
            return teams_by_norm[added]

    return None


def process_leaderboard_event(season_slug, event_type_name, event_name, lb_id, year, teams_by_norm, tournament_slugs, dry_run=False):
    """リーダーボード型イベントの結果を取得してDB投入"""
    stats = {"created": 0, "results": 0, "matched": 0, "unmatched": 0}

    for bf_region, db_region in REGION_MAP.items():
        tourney_name = f"ALGS Year {year} {event_name} - {db_region}"
        slug = make_slug(tourney_name)

        if slug in tournament_slugs:
            continue

        # リーダーボード取得
        teams = fetch_leaderboard(season_slug, lb_id, bf_region)
        if not teams:
            continue

        event_type = EVENT_TYPE_MAP.get(event_type_name, "community")
        print(f"  {tourney_name}: {len(teams)}チーム")

        if dry_run:
            matched = sum(1 for t in teams[:20] if match_team(t.get("name", ""), teams_by_norm))
            print(f"    TOP20マッチ率: {matched}/20")
            for t in teams[:5]:
                team = match_team(t.get("name", ""), teams_by_norm)
                status = "MATCH" if team else "MISS"
                print(f"    #{t.get('rank','?'):3} | {status} | {t.get('name','?'):30s} | {t.get('score',0)} pts")
            continue

        # 大会登録
        tourney_data = {
            "name": tourney_name,
            "slug": slug,
            "series": f"ALGS Year {year}",
            "event_type": event_type,
            "region": db_region,
            "status": "completed",
            "is_lan": False,
        }
        created = supabase_insert("tournaments", [tourney_data])
        if not created:
            continue

        tournament_id = created[0]["id"]
        tournament_slugs.add(slug)
        stats["created"] += 1

        # 結果登録（TOP40まで）
        results_to_insert = []
        for t in teams[:40]:
            team = match_team(t.get("name", ""), teams_by_norm)
            if team:
                stats["matched"] += 1
                results_to_insert.append({
                    "tournament_id": tournament_id,
                    "team_id": team["id"],
                    "placement": t.get("rank", 0),
                    "total_points": t.get("score", 0),
                })
            else:
                stats["unmatched"] += 1

        if results_to_insert:
            inserted = supabase_insert("tournament_results", results_to_insert)
            stats["results"] += len(inserted) if inserted else 0

        time.sleep(1)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Battlefy大会結果取得")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--season", type=int, choices=[4, 5, 6], help="特定のシーズンのみ")
    args = parser.parse_args()

    print("=" * 60)
    print("Battlefy 大会結果取得")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN\n")

    # 既存データ
    print("--- 既存データ取得 ---")
    existing_teams = supabase_get_all("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get_all("tournaments", {"select": "id,name,slug"})

    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        name = t["name"]
        if name.lower().startswith("team "):
            teams_by_norm[normalize_name(name[5:])] = t
        for sfx in [" esports", " gaming", " e-sports"]:
            if name.lower().endswith(sfx):
                teams_by_norm[normalize_name(name[:len(name) - len(sfx)])] = t

    tournament_slugs = {t["slug"] for t in existing_tournaments}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)}")

    seasons_to_process = []
    if args.season:
        seasons_to_process = [args.season]
    else:
        seasons_to_process = [4, 5, 6]

    total_stats = {"created": 0, "results": 0, "matched": 0, "unmatched": 0}

    for year in seasons_to_process:
        print(f"\n{'='*60}")
        print(f"Year {year}")
        print(f"{'='*60}")

        season_data = fetch_season(year)
        if not season_data:
            print(f"  シーズンデータ取得失敗")
            continue

        season_slug = f"algs-season-{year}"

        for et in season_data.get("eventTypes", []):
            et_name = et.get("name", "")
            lb_id = et.get("leaderboardSeasonID")

            if not lb_id:
                print(f"\n--- {et_name}: リーダーボードIDなし、スキップ ---")
                continue

            events = et.get("events", [])
            print(f"\n--- {et_name} (LB: {lb_id}, {len(events)} events) ---")

            # リーダーボードはイベントタイプごとに累計ポイント
            # → イベントタイプにつき1大会（リージョン別）として登録
            stats = process_leaderboard_event(
                season_slug, et_name, et_name, lb_id, year,
                teams_by_norm, tournament_slugs, dry_run=args.dry_run,
            )
            for k in total_stats:
                total_stats[k] += stats.get(k, 0)

    # レポート
    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  大会登録: {total_stats['created']}")
    print(f"  結果登録: {total_stats['results']}")
    print(f"  チームマッチ: {total_stats['matched']}")
    print(f"  チーム未マッチ: {total_stats['unmatched']}")


if __name__ == "__main__":
    main()
