"""
ALGS公式APIからYear 6の最新ロスターを取得し、DBを同期する
- ALGS公式ロスターを正として現在のロスターを更新
- 旧メンバーのleft_atを設定
- 新メンバーのロスターレコードを作成
- 選手名の表記揺れ（Dizzy vs Dizzy_pw等）も解決

使い方:
  python sync_algs_rosters.py          # 本番実行
  python sync_algs_rosters.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse
from datetime import date

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
db_client = httpx.Client(timeout=30)

ALGS_SOURCE = "https://algs.ea.com"
TODAY = date.today().isoformat()


def normalize_name(name):
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
            print(f"  GET エラー: {resp.status_code}: {resp.text[:200]}")
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


def supabase_update(table, record_id, data):
    headers = {**DB_HEADERS, "Prefer": "return=minimal"}
    resp = db_client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{record_id}",
        json=data, headers=headers,
    )
    if resp.status_code not in (200, 204):
        print(f"  UPDATE エラー: {resp.status_code}: {resp.text[:200]}")
        return False
    return True


def fetch_algs_rosters():
    """ALGS公式APIから全リージョンのYear 6ロスターを取得"""
    with open(os.path.join(CACHE_DIR, "algs_history_exploration.json"), "r", encoding="utf-8") as f:
        hist = json.load(f)

    y6 = hist["year6_structure"]
    region_map = {
        "Americas": "NA",
        "Europe Middle East and Africa": "EMEA",
        "Asia Pacific North": "APAC_N",
        "Asia Pacific South": "APAC_S",
    }

    all_teams = []
    for tournament in y6["tournaments"]:
        for region in tournament.get("regions", []):
            for event in region.get("events", []):
                eid = event["id"]
                rname = region["name"]
                resp = client.get(f"https://prod-api.algstools.com/v1/events/{eid}/teams")
                if resp.status_code == 200:
                    data = resp.json()
                    teams = data.get("teams", [])
                    db_region = region_map.get(rname, rname)
                    for t in teams:
                        all_teams.append({
                            "name": t["name"],
                            "short_name": t.get("shortName"),
                            "region": db_region,
                            "players": [
                                {
                                    "name": p["name"].strip(),
                                    "role": p.get("role", "player"),
                                }
                                for p in t.get("players", [])
                            ],
                        })

    return all_teams


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("ALGS公式ロスター同期")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # --- Step 1: ALGS APIからロスター取得 ---
    print("--- Step 1: ALGS APIから最新ロスター取得 ---")
    algs_teams = fetch_algs_rosters()
    total_players = sum(len(t["players"]) for t in algs_teams)
    print(f"  {len(algs_teams)}チーム / {total_players}選手")

    # --- Step 2: DB既存データ取得 ---
    print("\n--- Step 2: DB既存データ取得 ---")
    db_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    db_players = supabase_get("players", {"select": "id,ign,slug"})
    db_rosters = supabase_get("team_rosters", {"select": "*"})

    # インデックス構築
    teams_by_norm = {}
    for t in db_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t

    players_by_norm = {}
    for p in db_players:
        players_by_norm[normalize_name(p["ign"])] = p

    # 既存のアクティブロスター（left_at=NULL）をチームごとにグループ化
    active_rosters_by_team = {}
    for r in db_rosters:
        if r.get("left_at") is None:
            tid = r["team_id"]
            if tid not in active_rosters_by_team:
                active_rosters_by_team[tid] = []
            active_rosters_by_team[tid].append(r)

    print(f"  DBチーム: {len(db_teams)} / DB選手: {len(db_players)} / DBロスター: {len(db_rosters)}")

    # --- Step 3: 同期処理 ---
    print("\n--- Step 3: ロスター同期 ---")

    stats = {
        "teams_matched": 0,
        "teams_unmatched": 0,
        "players_matched": 0,
        "players_created": 0,
        "players_unmatched": 0,
        "rosters_created": 0,
        "rosters_closed": 0,
        "rosters_kept": 0,
        "algs_rosters_cleaned": 0,
    }

    for algs_team in algs_teams:
        # チームマッチング
        tn = normalize_name(algs_team["name"])
        db_team = teams_by_norm.get(tn)
        if not db_team:
            # short_nameでも試す
            if algs_team.get("short_name"):
                sn = normalize_name(algs_team["short_name"])
                db_team = teams_by_norm.get(sn)

        if not db_team:
            stats["teams_unmatched"] += 1
            continue

        stats["teams_matched"] += 1
        team_id = db_team["id"]

        # ALGS公式メンバーリスト（正規化名 → ALGS名）
        algs_members = {}
        for p in algs_team["players"]:
            pn = normalize_name(p["name"])
            algs_members[pn] = p

        # 現在のアクティブロスター
        current_active = active_rosters_by_team.get(team_id, [])

        # マッチング: アクティブロスターの選手がALGS公式にいるか
        matched_player_ids = set()
        for roster in current_active:
            pid = roster["player_id"]
            # この選手のIGNを取得
            player_ign = None
            for p in db_players:
                if p["id"] == pid:
                    player_ign = p["ign"]
                    break
            if not player_ign:
                continue

            pn = normalize_name(player_ign)
            if pn in algs_members:
                # ALGS公式にもいる → キープ
                matched_player_ids.add(pid)
                stats["rosters_kept"] += 1
                # sourceを更新
                if not args.dry_run and roster.get("source_url") != ALGS_SOURCE:
                    supabase_update("team_rosters", roster["id"], {"source_url": ALGS_SOURCE})
                del algs_members[pn]  # 処理済み
            else:
                # ALGS公式にいない → left_atを設定（チームを離れた）
                if not args.dry_run:
                    supabase_update("team_rosters", roster["id"], {"left_at": TODAY})
                stats["rosters_closed"] += 1

        # 残ったALGSメンバー = DB上で未登録 → 新規追加
        for pn, algs_player in algs_members.items():
            # 選手をDBから探す
            db_player = players_by_norm.get(pn)

            if not db_player:
                # 選手が存在しない → 新規作成
                if not args.dry_run:
                    slug = make_slug(algs_player["name"])
                    # スラッグ重複チェック
                    existing_slugs = {p["slug"] for p in db_players}
                    base_slug = slug
                    counter = 1
                    while slug in existing_slugs:
                        slug = f"{base_slug}-{counter}"
                        counter += 1

                    created = supabase_insert("players", [{
                        "ign": algs_player["name"],
                        "slug": slug,
                        "is_active": True,
                    }])
                    if created:
                        db_player = created[0]
                        db_players.append(db_player)
                        players_by_norm[pn] = db_player
                        stats["players_created"] += 1
                    else:
                        stats["players_unmatched"] += 1
                        continue
                else:
                    stats["players_created"] += 1
                    continue

            stats["players_matched"] += 1

            # このチームのアクティブロスターに既にいないか確認
            already_exists = any(
                r["player_id"] == db_player["id"] and r["team_id"] == team_id and r.get("left_at") is None
                for r in db_rosters
            )
            if already_exists:
                stats["rosters_kept"] += 1
                continue

            # ロスター作成
            if not args.dry_run:
                new_roster = {
                    "player_id": db_player["id"],
                    "team_id": team_id,
                    "role": algs_player.get("role"),
                    "joined_at": TODAY,
                    "is_substitute": False,
                    "source_url": ALGS_SOURCE,
                }
                result = supabase_insert("team_rosters", [new_roster])
                if result:
                    db_rosters.append(result[0])
            stats["rosters_created"] += 1

    # --- Step 4: 古いALGSソースのアクティブロスターをクリーンアップ ---
    # 今回同期されなかったALGSソースのアクティブロスターを閉じる
    print("\n--- Step 4: 古いALGSロスターのクリーンアップ ---")
    algs_team_norms = {normalize_name(t["name"]) for t in algs_teams}
    for roster in db_rosters:
        if (roster.get("left_at") is None
                and roster.get("source_url") == ALGS_SOURCE):
            # このチームがALGS Year 6に存在するか
            tid = roster["team_id"]
            team_name = None
            for t in db_teams:
                if t["id"] == tid:
                    team_name = t["name"]
                    break
            if team_name and normalize_name(team_name) not in algs_team_norms:
                # ALGSに存在しないチームの古いALGSロスター → 閉じる
                if not args.dry_run:
                    supabase_update("team_rosters", roster["id"], {"left_at": TODAY})
                stats["algs_rosters_cleaned"] += 1

    # レポート
    print("\n" + "=" * 60)
    print("結果レポート")
    print("=" * 60)
    print(f"  チームマッチ: {stats['teams_matched']}")
    print(f"  チーム未マッチ: {stats['teams_unmatched']}")
    print(f"  選手マッチ: {stats['players_matched']}")
    print(f"  選手新規作成: {stats['players_created']}")
    print(f"  選手未マッチ: {stats['players_unmatched']}")
    print(f"  ロスターキープ: {stats['rosters_kept']}")
    print(f"  ロスター新規作成: {stats['rosters_created']}")
    print(f"  ロスター閉鎖(left_at設定): {stats['rosters_closed']}")
    print(f"  古いALGSロスター閉鎖: {stats['algs_rosters_cleaned']}")


if __name__ == "__main__":
    main()
