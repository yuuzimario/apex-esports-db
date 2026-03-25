"""
ALGS Year 5: シリーズ別キル・試合数データを取得→Supabase tournament_results更新

1. ALGS API Year 5のシーズン構造を取得
2. 各イベントのフェーズ→シリーズを列挙
3. 完了済みシリーズごとにstatsを取得（チーム別kills）
4. イベント単位でチームごとにkills/games_playedを集計
5. Supabaseのtournament_resultsテーブルをUPDATE
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
from collections import defaultdict

BASE_URL = "https://prod-api.algstools.com/v1"
CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

client = httpx.Client(timeout=30)

Y5_SEASON_ID = "01JK2JQ40W0DDTZCWDB8WTWCBA"

# スキップするトーナメント名パターン
SKIP_PATTERNS = ["scrims", "Pro League Qualifier", "Last Chance Qualifier"]

# ALGS APIリージョン名→Supabaseトーナメント名のマッピング用
REGION_NAME_MAP = {
    "Americas": "Americas",
    "Europe Middle East and Africa": "Europe Middle East and Africa",
    "Asia Pacific North": "Asia Pacific North",
    "Asia Pacific South": "Asia Pacific South",
    "Global": None,  # グローバル大会は別マッピング
}


def normalize_team_name(name):
    """チーム名を正規化（小文字、英数字のみ）"""
    return "".join(c.lower() for c in name if c.isalnum())


def build_supabase_tournament_name(tournament_name, region_name):
    """ALGS API名からSupabaseトーナメント名を構築"""
    if region_name == "Global":
        return f"ALGS Year 5 {tournament_name}"
    return f"ALGS Year 5 {tournament_name} - {region_name}"


def fetch_with_cache(url, cache_key):
    """APIレスポンスをキャッシュ付きで取得"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    time.sleep(1)  # レート制限対策
    resp = client.get(url)
    resp.raise_for_status()
    data = resp.json()

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def get_supabase_teams():
    """Supabaseから全チームを取得→正規化名でマッピング"""
    teams = {}
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/teams",
            params={"select": "id,name", "offset": offset, "limit": 500},
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for t in batch:
            norm = normalize_team_name(t["name"])
            teams[norm] = t
        offset += len(batch)
    return teams


def get_supabase_tournaments():
    """Supabaseから全Year 5トーナメントを取得"""
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/tournaments",
        params={"select": "id,name", "name": "like.*Year 5*"},
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    tournaments = {}
    for t in resp.json():
        tournaments[t["name"]] = t["id"]
    return tournaments


def get_tournament_results(tournament_id):
    """指定トーナメントの全結果レコードを取得"""
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/tournament_results",
        params={
            "select": "id,team_id,total_kills,games_played",
            "tournament_id": f"eq.{tournament_id}",
            "limit": 500,
        },
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def update_tournament_result(result_id, total_kills, games_played):
    """tournament_resultsレコードを更新"""
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/tournament_results",
        params={"id": f"eq.{result_id}"},
        headers=SUPABASE_HEADERS,
        json={"total_kills": total_kills, "games_played": games_played},
    )
    resp.raise_for_status()


def should_skip(tournament_name):
    """スキップすべきトーナメントか判定"""
    for pattern in SKIP_PATTERNS:
        if pattern.lower() in tournament_name.lower():
            return True
    return False


def main():
    print("=" * 60)
    print("ALGS Year 5: キル・試合数データ取得＆更新")
    print("=" * 60)

    # 1. Supabaseデータ取得
    print("\n[1/5] Supabaseからチーム・トーナメント情報を取得中...")
    sb_teams = get_supabase_teams()
    print(f"  チーム数: {len(sb_teams)}")

    sb_tournaments = get_supabase_tournaments()
    print(f"  Year 5トーナメント数: {len(sb_tournaments)}")
    for name, tid in sb_tournaments.items():
        print(f"    {name}")

    # 2. ALGS APIからシーズン構造を取得
    print("\n[2/5] ALGS APIからYear 5シーズン構造を取得中...")
    season = fetch_with_cache(
        f"{BASE_URL}/seasons/{Y5_SEASON_ID}/structure",
        "year5_structure"
    )
    print(f"  トーナメント数: {len(season['tournaments'])}")

    # 3. 各イベントのシリーズからstatsを集計
    print("\n[3/5] 各イベントのシリーズstatsを取得・集計中...")

    # イベントID→集計データのマッピング
    # event_stats[supabase_tournament_name] = { normalized_team_name: { kills: int, games: int, algs_name: str } }
    event_stats = {}

    for tournament in season["tournaments"]:
        t_name = tournament["name"]

        if should_skip(t_name):
            print(f"\n  [SKIP] {t_name}")
            continue

        print(f"\n  === {t_name} ===")

        for region in tournament["regions"]:
            r_name = region["name"]

            for event in region["events"]:
                e_id = event["id"]
                e_name = event["name"]
                sb_tournament_name = build_supabase_tournament_name(t_name, r_name)

                print(f"\n    Region: {r_name} | Event: {e_name}")
                print(f"    → Supabase名: {sb_tournament_name}")

                if sb_tournament_name not in sb_tournaments:
                    print(f"    ⚠ Supabaseにトーナメントが見つからない、スキップ")
                    continue

                # イベント構造を取得（フェーズ→シリーズ一覧）
                event_data = fetch_with_cache(
                    f"{BASE_URL}/events/{e_id}/structure",
                    f"event_{e_id}"
                )

                # チームごとの集計
                team_agg = defaultdict(lambda: {"kills": 0, "games": 0, "algs_name": ""})
                total_series = 0
                completed_series = 0

                for phase in event_data.get("phases", []):
                    for series in phase.get("series", []):
                        total_series += 1
                        s_id = series["id"]
                        s_status = series["status"]
                        s_name = series["name"]
                        num_matches = len(series.get("matches", []))

                        if s_status != "completed":
                            print(f"      シリーズ '{s_name}' はstatus={s_status}、スキップ")
                            continue

                        completed_series += 1

                        # シリーズstatsを取得
                        stats = fetch_with_cache(
                            f"{BASE_URL}/stats/series/{s_id}",
                            f"series_stats_{s_id}"
                        )

                        for team in stats.get("teams", []):
                            team_name = team["name"]
                            norm = normalize_team_name(team_name)
                            kills = team.get("kills", 0) or 0
                            team_agg[norm]["kills"] += kills
                            team_agg[norm]["games"] += num_matches
                            team_agg[norm]["algs_name"] = team_name

                print(f"    シリーズ: {completed_series}/{total_series} 完了")
                print(f"    チーム数: {len(team_agg)}")

                if team_agg:
                    event_stats[sb_tournament_name] = dict(team_agg)

    # 4. チーム名マッチング確認
    print("\n[4/5] チーム名マッチング...")
    unmatched_teams = set()
    matched_count = 0

    for sb_t_name, teams_data in event_stats.items():
        for norm_name, data in teams_data.items():
            if norm_name in sb_teams:
                matched_count += 1
            else:
                unmatched_teams.add((data["algs_name"], norm_name))

    print(f"  マッチ成功: {matched_count}")
    if unmatched_teams:
        print(f"  マッチ失敗: {len(unmatched_teams)}")
        for algs_name, norm in sorted(unmatched_teams):
            # ファジーマッチを試行（部分一致）
            partial_matches = [
                (sb_norm, sb_teams[sb_norm]["name"])
                for sb_norm in sb_teams
                if norm in sb_norm or sb_norm in norm
            ]
            if partial_matches:
                print(f"    '{algs_name}' → 候補: {partial_matches[:3]}")
            else:
                print(f"    '{algs_name}' (norm: {norm}) → 候補なし")

    # 5. Supabase更新
    print("\n[5/5] Supabase tournament_results更新中...")
    updated = 0
    skipped_no_team = 0
    skipped_no_result = 0

    for sb_t_name, teams_data in event_stats.items():
        tournament_id = sb_tournaments[sb_t_name]
        print(f"\n  {sb_t_name} (id={tournament_id})")

        # このトーナメントの既存結果を取得
        results = get_tournament_results(tournament_id)
        if not results:
            print(f"    結果レコードなし、スキップ")
            continue

        # team_id→resultのマッピング
        result_by_team = {r["team_id"]: r for r in results}

        for norm_name, data in teams_data.items():
            if norm_name not in sb_teams:
                skipped_no_team += 1
                continue

            sb_team_id = sb_teams[norm_name]["id"]

            if sb_team_id not in result_by_team:
                skipped_no_result += 1
                continue

            result = result_by_team[sb_team_id]
            result_id = result["id"]
            kills = data["kills"]
            games = data["games"]

            try:
                update_tournament_result(result_id, kills, games)
                updated += 1
                print(f"    ✓ {data['algs_name']}: kills={kills}, games={games}")
            except Exception as e:
                print(f"    ✗ {data['algs_name']}: エラー {e}")

    print("\n" + "=" * 60)
    print(f"完了！")
    print(f"  更新: {updated}")
    print(f"  チーム未マッチ: {skipped_no_team}")
    print(f"  結果レコードなし: {skipped_no_result}")
    print("=" * 60)


if __name__ == "__main__":
    main()
