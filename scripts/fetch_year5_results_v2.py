"""
ALGS Year 5 大会結果v2: 未マッチチームを新規作成して完全投入
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
from datetime import datetime

BASE_URL = "https://prod-api.algstools.com/v1"
SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
Y5_SEASON_ID = "01JK2JQ40W0DDTZCWDB8WTWCBA"

REGION_MAP = {
    "Americas": "NA",
    "Europe Middle East and Africa": "EMEA",
    "Asia Pacific North": "APAC_N",
    "Asia Pacific South": "APAC_S",
    "Global": "GLOBAL",
}

# ALGS API名 → DB名のエイリアス
TEAM_ALIASES = {
    "falcons": "teamfalcons",
    "ag.al": "auroragaming",  # Alliance旧名?
    "nip": "ninjasinpyjamas",
    "ninjasinpyjamas": "ninjasinpyjamas",
    "navi": "natusvincerc",
    "natusvincere": "natusvincerc",
    "liquidalienware": "teamliquid",
    "crazyraccoon": "crazyraccoon",
    "rrx": "rrx",
}


def norm(name):
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def supabase_get(table, params=None):
    resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        # slug重複の場合はスキップ
        if "duplicate" in resp.text.lower():
            return []
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def find_or_create_team(team_name, region_code, teams_by_norm):
    """チームをDBで探す。なければ新規作成"""
    n = norm(team_name)

    # エイリアスチェック
    aliased = TEAM_ALIASES.get(n, n)
    if aliased in teams_by_norm:
        return teams_by_norm[aliased]["id"]

    # 直接マッチ
    if n in teams_by_norm:
        return teams_by_norm[n]["id"]

    # 部分一致
    for dn, dt in teams_by_norm.items():
        if n in dn or dn in n:
            return dt["id"]

    # 新規作成
    slug = make_slug(team_name)
    new_team = {
        "slug": slug,
        "name": team_name,
        "region": region_code if region_code != "GLOBAL" else None,
        "is_active": True,
    }
    result = supabase_insert("teams", [new_team])
    if result:
        teams_by_norm[n] = result[0]
        return result[0]["id"]

    # slug重複→リージョン付き
    new_team["slug"] = f"{slug}-{(region_code or 'global').lower().replace('_','-')}"
    result = supabase_insert("teams", [new_team])
    if result:
        teams_by_norm[n] = result[0]
        return result[0]["id"]

    return None


def main():
    print("=" * 60)
    print("ALGS Year 5 大会結果v2（未マッチチーム対応）")
    print("=" * 60)

    # DB チーム
    db_teams = supabase_get("teams", {"select": "id,name,slug"})
    teams_by_norm = {norm(t["name"]): t for t in db_teams}

    # 既存の大会
    db_tournaments = supabase_get("tournaments", {"select": "id,slug,name"})
    tournaments_by_slug = {t["slug"]: t for t in db_tournaments}

    # Year 5 構造
    y5 = client.get(f"{BASE_URL}/seasons/{Y5_SEASON_ID}/structure").json()

    TOURNAMENT_INFO = {
        "Split 1": {"series": "ALGS Year 5", "event_type": "pro_league", "start_date": "2025-03-01", "end_date": "2025-06-30", "is_lan": False},
        "ALGS Open": {"series": "ALGS Year 5", "event_type": "open_qualifier", "start_date": "2025-07-01", "end_date": "2025-07-31", "is_lan": False},
        "Midseason Playoffs": {"series": "ALGS Year 5", "event_type": "playoffs", "start_date": "2025-08-01", "end_date": "2025-08-15", "is_lan": True, "prize_pool": 1000000, "location": "Los Angeles, USA"},
        "Split 2": {"series": "ALGS Year 5", "event_type": "pro_league", "start_date": "2025-09-20", "end_date": "2025-12-15", "is_lan": False},
        "Championship": {"series": "ALGS Year 5", "event_type": "championship", "start_date": "2026-01-16", "end_date": "2026-01-19", "is_lan": True, "prize_pool": 2000000, "location": "Sapporo, Japan"},
    }

    total_results = 0
    teams_created = 0

    for tournament in y5.get("tournaments", []):
        t_name = tournament["name"]
        if t_name in ("scrims", "Pro League Qualifier", "Last Chance Qualifier"):
            continue

        t_info = TOURNAMENT_INFO.get(t_name, {})
        print(f"\n=== {t_name} ===")

        all_events = []
        for region in tournament.get("regions", []):
            for event in region.get("events", []):
                all_events.append((region["name"], event))
        for event in tournament.get("events", []):
            all_events.append(("Global", event))

        for region_name, event in all_events:
            region_code = REGION_MAP.get(region_name, "GLOBAL")
            event_id = event["id"]

            if region_code == "GLOBAL":
                full_name = f"ALGS Year 5 {t_name}"
            else:
                full_name = f"ALGS Year 5 {t_name} - {region_name}"
            slug = make_slug(full_name)

            # 大会取得or作成
            if slug in tournaments_by_slug:
                tournament_db_id = tournaments_by_slug[slug]["id"]
            else:
                new_t = {
                    "slug": slug, "name": full_name,
                    "series": t_info.get("series", "ALGS Year 5"),
                    "event_type": t_info.get("event_type", "pro_league"),
                    "region": region_code,
                    "start_date": t_info.get("start_date"),
                    "end_date": t_info.get("end_date"),
                    "prize_pool_usd": t_info.get("prize_pool"),
                    "is_lan": t_info.get("is_lan", False),
                    "location": t_info.get("location"),
                    "status": "completed",
                }
                result = supabase_insert("tournaments", [new_t])
                if not result:
                    continue
                tournament_db_id = result[0]["id"]
                tournaments_by_slug[slug] = result[0]

            # 既存結果のチームIDを取得（重複投入防止）
            existing = supabase_get("tournament_results", {
                "select": "team_id", "tournament_id": f"eq.{tournament_db_id}",
            })
            existing_team_ids = {e["team_id"] for e in existing}

            # standings取得
            resp = client.get(f"{BASE_URL}/events/{event_id}/standings")
            if resp.status_code != 200:
                continue
            standings = resp.json().get("standings", [])
            if not standings:
                continue

            results = []
            for s in standings:
                team_id = find_or_create_team(s["name"], region_code, teams_by_norm)
                if not team_id:
                    continue

                # 既に結果がある場合はスキップ
                if team_id in existing_team_ids:
                    continue

                prize = s.get("prizeMoney")
                prize_usd = int(prize) if prize and prize != "null" else None

                results.append({
                    "tournament_id": tournament_db_id,
                    "team_id": team_id,
                    "placement": s.get("position", 0),
                    "total_points": s.get("points"),
                    "prize_usd": prize_usd,
                })

            inserted = 0
            for i in range(0, len(results), 50):
                batch = results[i:i + 50]
                r = supabase_insert("tournament_results", batch)
                if r:
                    inserted += len(r)

            total_results += inserted
            new_count = len(teams_by_norm) - len(db_teams)
            print(f"  [{region_code}] {t_name}: {inserted}/{len(standings)}チーム投入")

    # 最終チーム数カウント
    final_teams = supabase_get("teams", {"select": "id"})
    new_teams = len(final_teams) - len(db_teams)

    print(f"\n{'=' * 60}")
    print(f"合計: {total_results}件の大会結果を投入")
    print(f"新規チーム: {new_teams}チーム作成")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
