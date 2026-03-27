"""
ALGS公式APIからYear 5+6の全イベント結果を取得してDBに投入

取得対象:
- Year 5: Split 1/2 (4リージョン), ALGS Open, Midseason Playoffs, Championship
- Year 6: Split 1 (4リージョン) ※進行中

使い方:
  python fetch_algs_event_results.py          # 本番実行
  python fetch_algs_event_results.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import re
import argparse
import time

ALGS_BASE = "https://prod-api.algstools.com/v1"
SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
db_client = httpx.Client(timeout=30)

# リージョン名のマッピング
REGION_MAP = {
    "Americas": "NA",
    "Europe Middle East and Africa": "EMEA",
    "Asia Pacific North": "APAC_N",
    "Asia Pacific South": "APAC_S",
    "Global": "GLOBAL",
}

# DBの大会名→ALGS APIの対応
TOURNAMENT_NAME_MAP = {
    "Split 1": "split_1",
    "Split 2": "split_2",
    "ALGS Open": "open",
    "Midseason Playoffs": "playoffs",
    "Championship": "championship",
    "Pro League Qualifier": "qualifier",
    "Last Chance Qualifier": "lcq",
}


def normalize_name(name):
    if not name:
        return ""
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def supabase_get(table, params=None):
    all_data = []
    offset = 0
    while True:
        p = {**(params or {}), "limit": "1000", "offset": str(offset)}
        resp = db_client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            print(f"  GET エラー: {resp.status_code}")
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
    resp = db_client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def supabase_upsert(table, data, on_conflict="id"):
    if not data:
        return []
    headers = {**DB_HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = db_client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  UPSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def get_season_events(season_id):
    """シーズンの全イベントを取得"""
    r = client.get(f"{ALGS_BASE}/series/seasons/{season_id}")
    if r.status_code != 200:
        return []

    series_data = r.json().get("series", [])
    # イベントをユニークに収集
    events = {}
    for s in series_data:
        e = s.get("event", {}) or {}
        eid = e.get("id")
        if not eid or eid in events:
            continue

        region = (s.get("region", {}) or {}).get("name", "?")
        tournament = (s.get("tournament", {}) or {}).get("name", "?")
        events[eid] = {
            "event_id": eid,
            "event_name": e.get("name", "?"),
            "tournament_name": tournament,
            "region": region,
            "region_code": REGION_MAP.get(region, "GLOBAL"),
        }

    return list(events.values())


def get_event_standings(event_id):
    """イベントのstandingsを取得"""
    r = client.get(f"{ALGS_BASE}/events/{event_id}/standings")
    if r.status_code != 200:
        return []
    return r.json().get("standings", [])


def match_team_by_algs(algs_name, algs_team_id, teams_by_norm, teams_by_algs_id):
    """ALGSのチーム名/IDからDBチームをマッチ"""
    if not algs_name:
        return None

    # ALGS teamId でマッチ
    if algs_team_id in teams_by_algs_id:
        return teams_by_algs_id[algs_team_id]

    # 名前でマッチ
    tn = normalize_name(algs_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]

    # "Team " prefix
    if algs_name.lower().startswith("team "):
        short = normalize_name(algs_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + algs_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]

    # サフィックス除去
    for suffix in [" esports", " gaming", " e-sports"]:
        if algs_name.lower().endswith(suffix):
            short = normalize_name(algs_name[: len(algs_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("ALGS公式API → Year 5+6 全イベント結果取得")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # DB既存データ取得
    print("--- DB既存データ取得 ---")
    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get("tournaments", {"select": "id,name,slug"})
    existing_results = supabase_get("tournament_results", {"select": "tournament_id,team_id"})

    # チームマッチング辞書
    teams_by_norm = {}
    teams_by_algs_id = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        name = t["name"]
        if name.lower().startswith("team "):
            teams_by_norm[normalize_name(name[5:])] = t
        for sfx in [" Esports", " Gaming", " E-Sports"]:
            if name.endswith(sfx):
                teams_by_norm[normalize_name(name[: len(name) - len(sfx)])] = t

    tournament_slugs = {t["slug"]: t for t in existing_tournaments}
    existing_result_keys = {(r["tournament_id"], r["team_id"]) for r in existing_results}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)} / 既存結果: {len(existing_result_keys)}")

    # シーズン一覧
    seasons = [
        ("01JK2JQ40W0DDTZCWDB8WTWCBA", "Year 5", "ALGS Year 5"),
        ("01KEAJYDXP9CBK44PPW7XWDNB3", "Year 6", "ALGS Year 6"),
    ]

    stats = {
        "tournaments_created": 0,
        "tournaments_skipped": 0,
        "results_created": 0,
        "results_skipped": 0,
        "teams_created": 0,
        "unmatched": 0,
    }

    for season_id, season_name, series_prefix in seasons:
        print(f"\n{'='*60}")
        print(f"  {season_name}")
        print(f"{'='*60}")

        events = get_season_events(season_id)
        print(f"  イベント数: {len(events)}")

        for ev in sorted(events, key=lambda x: x["event_name"]):
            event_name = ev["event_name"]
            region_code = ev["region_code"]
            region_name = ev["region"]

            # DB用大会名
            if region_code == "GLOBAL":
                db_tournament_name = f"{series_prefix} {event_name}"
            else:
                db_tournament_name = f"{series_prefix} {event_name} - {region_name}"

            slug = make_slug(db_tournament_name)
            print(f"\n--- {db_tournament_name} ---")

            # イベントタイプ判定
            event_type = TOURNAMENT_NAME_MAP.get(ev["tournament_name"], "other")

            # standings取得
            standings = get_event_standings(ev["event_id"])
            if not standings:
                print("  standings なし")
                continue
            print(f"  standings: {len(standings)} teams")

            # 既存大会チェック
            existing_tournament = tournament_slugs.get(slug)
            tournament_id = None

            if existing_tournament:
                tournament_id = existing_tournament["id"]
                print(f"  既存大会: {tournament_id[:15]}...")
            elif not args.dry_run:
                # 新規大会作成
                tourney_data = {
                    "name": db_tournament_name,
                    "slug": slug,
                    "series": series_prefix,
                    "event_type": event_type,
                    "region": region_code,
                    "status": "completed",
                    "is_lan": event_type in ("championship", "playoffs", "open"),
                }
                created = supabase_insert("tournaments", [tourney_data])
                if created:
                    tournament_id = created[0]["id"]
                    tournament_slugs[slug] = created[0]
                    stats["tournaments_created"] += 1
                    print(f"  新規大会作成: {tournament_id[:15]}...")
                else:
                    print("  大会作成失敗")
                    continue

            # standings → tournament_results
            to_insert = []
            for standing in standings:
                team_name = standing.get("name") or "Unknown"
                algs_team_id = standing.get("teamId")
                position = standing.get("position")
                points = standing.get("points")
                prize_money = standing.get("prizeMoney")

                # チームマッチ
                team = match_team_by_algs(team_name, algs_team_id or "", teams_by_norm, teams_by_algs_id)

                if not team and not args.dry_run:
                    # 新規チーム追加
                    new_team_data = {
                        "name": team_name,
                        "slug": make_slug(team_name),
                        "region": region_code if region_code != "GLOBAL" else None,
                        "is_active": True,
                    }
                    created = supabase_insert("teams", [new_team_data])
                    if created:
                        team = created[0]
                        teams_by_norm[normalize_name(team_name)] = team
                        stats["teams_created"] += 1
                        print(f"    新規チーム: {team_name}")

                if not team:
                    if args.dry_run:
                        status = "??"
                    else:
                        stats["unmatched"] += 1
                        continue
                else:
                    status = "OK"

                if args.dry_run and position and position <= 5:
                    pts = points or "-"
                    prize = f"${int(prize_money):,}" if prize_money else "-"
                    print(f"    {position:3d}位 [{status}] {team_name:30s} pts={pts} prize={prize}")

                if tournament_id and team:
                    # 既存結果チェック
                    if (tournament_id, team["id"]) in existing_result_keys:
                        stats["results_skipped"] += 1
                        continue

                    to_insert.append({
                        "tournament_id": tournament_id,
                        "team_id": team["id"],
                        "placement": position,
                        "total_points": points,
                        "prize_usd": int(prize_money) if prize_money else None,
                    })

            if args.dry_run:
                if len(standings) > 5:
                    print(f"    ... 他 {len(standings) - 5} teams")
                continue

            if to_insert:
                # バッチ挿入（50件ずつ）
                total_inserted = 0
                for i in range(0, len(to_insert), 50):
                    batch = to_insert[i : i + 50]
                    inserted = supabase_insert("tournament_results", batch)
                    total_inserted += len(inserted) if inserted else 0
                stats["results_created"] += total_inserted
                print(f"  結果登録: {total_inserted}件")

            time.sleep(0.5)  # API負荷対策

    # レポート
    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  大会新規作成: {stats['tournaments_created']}")
    print(f"  大会スキップ: {stats['tournaments_skipped']}")
    print(f"  結果登録: {stats['results_created']}件")
    print(f"  結果スキップ（既存）: {stats['results_skipped']}件")
    print(f"  チーム新規追加: {stats['teams_created']}")
    print(f"  未マッチ: {stats['unmatched']}")


if __name__ == "__main__":
    main()
