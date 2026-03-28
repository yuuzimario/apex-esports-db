"""
Battlefy大会結果のリアルタイム更新スクリプト
→ 毎日1回実行（Windowsタスクスケジューラ）

やること:
1. Battlefy Majestic APIから現在のシーズン構造を取得
2. リーダーボードがあるイベントタイプの結果を更新
3. 新規大会は自動作成、既存大会は結果を上書き更新
4. 変動があればDiscord通知

使い方:
  python update_battlefy_live.py           # 本番実行
  python update_battlefy_live.py --dry-run # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse
from datetime import datetime

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

MAJESTIC_BASE = "https://majestic.battlefy.com"
CF_NEW = "https://d3q4fnxloga6gz.cloudfront.net"
BF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://battlefy.com",
    "Referer": "https://battlefy.com/",
    "Accept": "application/json",
}

# Discord通知
DISCORD_WEBHOOK = None
try:
    with open("C:/auto-content/api_keys.json", "r") as f:
        keys = json.load(f)
        DISCORD_WEBHOOK = keys.get("discord_webhook")
except Exception:
    pass

REGION_MAP = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}

# LAN大会等はリージョン別に作らない
SKIP_EVENT_TYPES = {
    "Year 5 Championship", "Year 6 Championship",
    "Championship Group Stage", "Championship",
    "Midseason Playoffs",
    "Last Chance Qualifier",
    "ALGS Open",
    "Pro League Playoffs - Split 1", "Pro League Playoffs - Split 2",
}

EVENT_TYPE_MAP = {
    "Online Opens": "open_qualifier",
    "Preseason Qualifiers": "open_qualifier",
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
    "BLGS Circuit": "community",
}

client = httpx.Client(timeout=30)
bf_client = httpx.Client(timeout=30, headers=BF_HEADERS)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def discord_notify(title, description):
    if not DISCORD_WEBHOOK:
        return
    try:
        import requests
        requests.post(DISCORD_WEBHOOK, json={
            "embeds": [{
                "title": f"🏆 APEX DB: {title}",
                "description": description,
                "color": 0xFF4500,
                "timestamp": datetime.utcnow().isoformat(),
            }]
        })
    except Exception:
        pass


def normalize_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return re.sub(r"-+", "-", slug) or "unknown"


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


def fetch_leaderboard(season_slug, lb_id, region, limit=200):
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
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]
    # プレフィックス/サフィックス対応
    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    for suffix in [" esports", " gaming", " e-sports", " esport", " gg"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]
        added = normalize_name(team_name + suffix)
        if added in teams_by_norm:
            return teams_by_norm[added]
    return None


def main():
    parser = argparse.ArgumentParser(description="Battlefyリアルタイム更新")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log("=" * 50)
    log("Battlefy リアルタイム更新")
    log("=" * 50)

    if args.dry_run:
        log("DRY-RUN モード")

    # 現在のシーズン（Year 6）
    CURRENT_YEAR = 6
    season_slug = f"algs-season-{CURRENT_YEAR}"
    portal_slug = f"apex-legends-global-series-year-{CURRENT_YEAR}"

    # シーズン構造取得
    resp = bf_client.get(f"{MAJESTIC_BASE}/algs/{portal_slug}/seasons")
    if resp.status_code != 200:
        log(f"シーズン取得失敗: {resp.status_code}")
        return
    season_data = resp.json()
    log(f"Year {CURRENT_YEAR}: {len(season_data.get('eventTypes', []))} event types")

    # DB既存データ
    existing_teams = supabase_get_all("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get_all("tournaments", {"select": "id,name,slug,series"})

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

    tournament_by_slug = {t["slug"]: t for t in existing_tournaments}

    stats = {"new_tournaments": 0, "updated": 0, "new_results": 0, "unchanged": 0}
    changes = []

    for et in season_data.get("eventTypes", []):
        et_name = et.get("name", "")
        lb_id = et.get("leaderboardSeasonID")

        if not lb_id:
            continue
        if et_name in SKIP_EVENT_TYPES:
            continue

        event_type = EVENT_TYPE_MAP.get(et_name, "community")

        # 日付を取得（全イベントのstartTimeから）
        starts, ends = [], []
        for ev in et.get("events", []):
            re_dict = ev.get("regionalEvents", {})
            if isinstance(re_dict, dict):
                for rdata in re_dict.values():
                    s = rdata.get("tournamentStartTime", "")
                    e = rdata.get("completedAt", "")
                    if s:
                        starts.append(s[:10])
                    if e:
                        ends.append(e[:10])

        start_date = min(starts) if starts else None
        end_date = max(ends) if ends else (max(starts) if starts else None)

        for bf_region, db_region in REGION_MAP.items():
            tourney_name = f"ALGS Year {CURRENT_YEAR} {et_name} - {db_region}"
            slug = make_slug(tourney_name)

            # リーダーボード取得
            teams = fetch_leaderboard(season_slug, lb_id, bf_region)
            if not teams:
                continue

            # 大会が存在するか確認
            existing = tournament_by_slug.get(slug)

            if not existing:
                # 新規大会作成
                if args.dry_run:
                    log(f"NEW: {tourney_name} ({len(teams)} teams)")
                    stats["new_tournaments"] += 1
                    continue

                resp = client.post(f"{SUPABASE_URL}/rest/v1/tournaments", json={
                    "name": tourney_name,
                    "slug": slug,
                    "series": f"ALGS Year {CURRENT_YEAR}",
                    "event_type": event_type,
                    "region": db_region,
                    "start_date": start_date,
                    "end_date": end_date,
                    "status": "completed" if end_date and end_date < datetime.now().strftime("%Y-%m-%d") else "ongoing",
                    "is_lan": False,
                }, headers={**DB_HEADERS, "Prefer": "return=representation"})

                if resp.status_code not in (200, 201):
                    log(f"  大会作成失敗: {resp.text[:100]}")
                    continue

                tournament_id = resp.json()[0]["id"]
                tournament_by_slug[slug] = {"id": tournament_id, "slug": slug}
                stats["new_tournaments"] += 1
                log(f"NEW: {tourney_name}")
                changes.append(f"🆕 {tourney_name}")
            else:
                tournament_id = existing["id"]

            # 既存結果を取得して比較
            old_results = supabase_get_all("tournament_results", {
                "select": "id,team_id,placement,total_points",
                "tournament_id": f"eq.{tournament_id}",
                "stage_id": "is.null",  # ステージなし（累計）のみ
            })
            old_by_team = {r["team_id"]: r for r in old_results}

            # 新しい結果を作成（TOP40）
            new_results = []
            for t in teams[:40]:
                team = match_team(t.get("name", ""), teams_by_norm)
                if not team:
                    continue
                new_results.append({
                    "team_id": team["id"],
                    "team_name": t.get("name", ""),
                    "placement": t.get("rank", 0),
                    "total_points": t.get("score", 0),
                })

            # 変更検出
            has_changes = False
            for nr in new_results:
                old = old_by_team.get(nr["team_id"])
                if not old:
                    has_changes = True
                    break
                if old.get("placement") != nr["placement"] or old.get("total_points") != nr["total_points"]:
                    has_changes = True
                    break

            if not has_changes:
                stats["unchanged"] += 1
                continue

            if args.dry_run:
                log(f"UPDATE: {tourney_name} ({len(new_results)} teams, changed)")
                stats["updated"] += 1
                continue

            # 古い結果を削除（ステージなしのみ）
            for old_r in old_results:
                client.delete(f"{SUPABASE_URL}/rest/v1/tournament_results", params={
                    "id": f"eq.{old_r['id']}"
                }, headers={**DB_HEADERS, "Prefer": "return=minimal"})

            # 新しい結果を挿入
            insert_data = [{
                "tournament_id": tournament_id,
                "team_id": nr["team_id"],
                "placement": nr["placement"],
                "total_points": nr["total_points"],
            } for nr in new_results]

            resp = client.post(f"{SUPABASE_URL}/rest/v1/tournament_results",
                json=insert_data,
                headers={**DB_HEADERS, "Prefer": "return=representation"})

            if resp.status_code in (200, 201):
                count = len(resp.json())
                stats["new_results"] += count
                stats["updated"] += 1

                # TOP3の変動をログ
                top3 = [f"#{nr['placement']} {nr['team_name']}" for nr in new_results[:3]]
                log(f"UPDATE: {tourney_name} → {', '.join(top3)}")
                changes.append(f"📊 {tourney_name}: {', '.join(top3)}")
            else:
                log(f"  結果挿入失敗: {resp.status_code}")

            # end_date更新
            if end_date:
                client.patch(f"{SUPABASE_URL}/rest/v1/tournaments", params={
                    "id": f"eq.{tournament_id}"
                }, json={"end_date": end_date}, headers={**DB_HEADERS, "Prefer": "return=minimal"})

            time.sleep(1)

    # レポート
    log("")
    log("=" * 50)
    log(f"新規大会: {stats['new_tournaments']}")
    log(f"更新: {stats['updated']}")
    log(f"変更なし: {stats['unchanged']}")
    log(f"結果登録: {stats['new_results']}")

    # Discord通知（変更があった場合のみ）
    if changes and not args.dry_run:
        discord_notify(
            f"大会結果更新 ({datetime.now().strftime('%m/%d')})",
            "\n".join(changes[:10]),
        )
        log("Discord通知送信")


if __name__ == "__main__":
    main()
