"""
ALGS Year 5 全大会結果を取得→Supabase投入
11イベントの順位・ポイント・賞金データ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
from datetime import datetime

BASE_URL = "https://prod-api.algstools.com/v1"
CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)

Y5_SEASON_ID = "01JK2JQ40W0DDTZCWDB8WTWCBA"

# リージョン名の正規化
REGION_MAP = {
    "Americas": "NA",
    "Europe Middle East and Africa": "EMEA",
    "Asia Pacific North": "APAC_N",
    "Asia Pacific South": "APAC_S",
    "Global": "GLOBAL",
}


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def normalize_team_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def supabase_get(table, params=None):
    resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def supabase_upsert(table, data):
    if not data:
        return []
    headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  UPSERT エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def main():
    print("=" * 60)
    print("ALGS Year 5 大会結果投入")
    print("=" * 60)

    # 既存のDB チームを取得（名前→ID マッピング用）
    db_teams = supabase_get("teams", {"select": "id,name,slug", "is_active": "eq.true"})
    teams_by_norm = {normalize_team_name(t["name"]): t for t in db_teams}
    # 既存の大会を取得
    db_tournaments = supabase_get("tournaments", {"select": "id,slug,name"})
    tournaments_by_slug = {t["slug"]: t for t in db_tournaments}

    # Year 5の構造を取得
    resp = client.get(f"{BASE_URL}/seasons/{Y5_SEASON_ID}/structure")
    y5 = resp.json()

    # 大会情報定義
    TOURNAMENT_INFO = {
        "Split 1": {"series": "ALGS Year 5", "event_type": "pro_league", "start_date": "2025-03-01", "end_date": "2025-06-30", "is_lan": False},
        "ALGS Open": {"series": "ALGS Year 5", "event_type": "open_qualifier", "start_date": "2025-07-01", "end_date": "2025-07-31", "is_lan": False},
        "Midseason Playoffs": {"series": "ALGS Year 5", "event_type": "playoffs", "start_date": "2025-08-01", "end_date": "2025-08-15", "is_lan": True, "prize_pool": 1000000, "location": "Los Angeles, USA"},
        "Pro League Qualifier": {"series": "ALGS Year 5", "event_type": "open_qualifier", "start_date": "2025-08-20", "end_date": "2025-09-15", "is_lan": False},
        "Split 2": {"series": "ALGS Year 5", "event_type": "pro_league", "start_date": "2025-09-20", "end_date": "2025-12-15", "is_lan": False},
        "Last Chance Qualifier": {"series": "ALGS Year 5", "event_type": "open_qualifier", "start_date": "2025-12-20", "end_date": "2026-01-05", "is_lan": False},
        "Championship": {"series": "ALGS Year 5", "event_type": "championship", "start_date": "2026-01-16", "end_date": "2026-01-19", "is_lan": True, "prize_pool": 2000000, "location": "Sapporo, Japan"},
    }

    total_results = 0

    for tournament in y5.get("tournaments", []):
        t_name = tournament["name"]
        if t_name == "scrims":
            continue

        t_info = TOURNAMENT_INFO.get(t_name, {})
        print(f"\n=== {t_name} ===")

        # イベント（リージョン別 or Global）を処理
        all_events = []
        for region in tournament.get("regions", []):
            for event in region.get("events", []):
                all_events.append((region["name"], event))
        for event in tournament.get("events", []):
            all_events.append(("Global", event))

        for region_name, event in all_events:
            region_code = REGION_MAP.get(region_name, "GLOBAL")
            event_id = event["id"]

            # 大会名
            if region_code == "GLOBAL":
                full_name = f"ALGS Year 5 {t_name}"
            else:
                full_name = f"ALGS Year 5 {t_name} - {region_name}"

            slug = make_slug(full_name)

            # 大会がDBに既にあるかチェック
            if slug in tournaments_by_slug:
                tournament_db_id = tournaments_by_slug[slug]["id"]
                print(f"  [{region_code}] {full_name}: 既存")
            else:
                # 大会を作成
                new_tournament = {
                    "slug": slug,
                    "name": full_name,
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
                result = supabase_insert("tournaments", [new_tournament])
                if result:
                    tournament_db_id = result[0]["id"]
                    tournaments_by_slug[slug] = result[0]
                    print(f"  [{region_code}] {full_name}: 作成")
                else:
                    print(f"  [{region_code}] {full_name}: 作成失敗")
                    continue

            # standings取得
            resp = client.get(f"{BASE_URL}/events/{event_id}/standings")
            if resp.status_code != 200:
                print(f"    standings取得失敗: {resp.status_code}")
                continue

            standings = resp.json().get("standings", [])
            if not standings:
                print(f"    standings空")
                continue

            # 既存の結果をチェック
            existing_results = supabase_get("tournament_results", {
                "select": "id",
                "tournament_id": f"eq.{tournament_db_id}",
            })
            if existing_results:
                print(f"    結果{len(existing_results)}件 既存→スキップ")
                continue

            # standings → tournament_results に変換
            results_to_insert = []
            for s in standings:
                team_name = s.get("name", "")
                team_norm = normalize_team_name(team_name)

                # DBのチームIDを検索
                db_team = teams_by_norm.get(team_norm)
                if not db_team:
                    # 部分一致で再検索
                    for tn, t in teams_by_norm.items():
                        if team_norm in tn or tn in team_norm:
                            db_team = t
                            break

                if not db_team:
                    continue

                prize_money = s.get("prizeMoney")
                prize_usd = int(prize_money) if prize_money and prize_money != "null" else None

                results_to_insert.append({
                    "tournament_id": tournament_db_id,
                    "team_id": db_team["id"],
                    "placement": s.get("position", 0),
                    "total_points": s.get("points"),
                    "prize_usd": prize_usd,
                })

            # DB投入（50件ずつ）
            inserted = 0
            for i in range(0, len(results_to_insert), 50):
                batch = results_to_insert[i:i + 50]
                result = supabase_insert("tournament_results", batch)
                if result:
                    inserted += len(result)

            total_results += inserted
            print(f"    {inserted}/{len(standings)}チームの結果を投入")

    # シーズン総合順位も取得
    print(f"\n=== Year 5 シーズン総合順位 ===")
    resp = client.get(f"{BASE_URL}/seasons/{Y5_SEASON_ID}/standings/teams")
    if resp.status_code == 200:
        team_standings = resp.json().get("standings", [])
        print(f"  {len(team_standings)}チーム")
        # 上位10チーム表示
        for s in team_standings[:10]:
            print(f"    #{s.get('rank','-')} {s.get('teamName','?')} ({s.get('points',0)}pts)")

    print(f"\n{'=' * 60}")
    print(f"合計: {total_results}件の大会結果を投入")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
