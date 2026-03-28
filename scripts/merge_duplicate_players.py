"""
重複選手を統合: ロースター・結果を1人に集約し、重複を削除

使い方:
  python merge_duplicate_players.py --dry-run
  python merge_duplicate_players.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import argparse

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)

# 統合定義: keep_id（残す）, merge_ids（統合して削除）
# 基準: ロースター数が多い+LP/TW/IMG等データが充実してる方をkeep
MERGES = [
    {
        "name": "Axis",
        "keep_id": "ef52aced",  # rosters=4, LP, TW
        "merge_ids": ["d339320a", "8dd61d30"],  # RC Axis(1), Axis(0)
    },
    {
        "name": "Euriece",
        "keep_id": "28e56ab6",  # rosters=2, LP, TW, name
        "merge_ids": ["4cf45101", "1b3f803b"],  # RC Euriece(1), Euriece(0)
    },
    {
        "name": "Fredstxr",
        "keep_id": "8c305530",  # rosters=1 (Twitch Fredstxr)
        "merge_ids": ["7b6cee15", "cef4f7df"],  # Fredstxr(0), Fredstxr(1)
    },
    {
        "name": "Gild",
        "keep_id": "5b2dabdf",  # rosters=3, LP, TW, name
        "merge_ids": ["c0775a4b", "783b48d2"],  # FLCN Gild(1), Gild(0)
    },
    {
        "name": "ImperialHal",
        "keep_id": "53b40c39",  # rosters=1, LP, TW, IMG, name
        "merge_ids": ["04598fe9", "1ba77279"],  # FLCN ImperialHal(1), ImperialHal(1)
    },
    {
        "name": "Unlucky",
        "keep_id": "4f44e8d6",  # rosters=3, LP, TW, IMG, name
        "merge_ids": ["863e571e", "c56e117a"],  # Alliance Unlucky(1), Unlucky(1)
    },
]


# 全選手をキャッシュ（起動時に1回だけ取得）
ALL_PLAYERS = []

def load_all_players():
    global ALL_PLAYERS
    if ALL_PLAYERS:
        return
    offset = 0
    while True:
        resp = client.get(f"{SUPABASE_URL}/rest/v1/players", params={
            "select": "id,ign", "limit": "1000", "offset": str(offset)
        }, headers=DB_HEADERS)
        data = resp.json()
        ALL_PLAYERS.extend(data)
        if len(data) < 1000:
            break
        offset += 1000

def get_full_id(short_id):
    """短縮IDから完全なUUIDを取得"""
    load_all_players()
    for p in ALL_PLAYERS:
        if p["id"].startswith(short_id):
            return p["id"], p["ign"]
    return None, None


def get_rosters(player_id):
    """選手のロースター一覧を取得"""
    resp = client.get(f"{SUPABASE_URL}/rest/v1/team_rosters", params={
        "select": "id,team_id,joined_at,left_at",
        "player_id": f"eq.{player_id}",
    }, headers=DB_HEADERS)
    return resp.json() if resp.status_code == 200 else []


def move_rosters(from_id, to_id, dry_run=False):
    """ロースターを移動（重複チェック付き）"""
    from_rosters = get_rosters(from_id)
    to_rosters = get_rosters(to_id)

    # 既存のteam_id+joined_atの組み合わせ
    existing = {(r["team_id"], r.get("joined_at")) for r in to_rosters}

    moved = 0
    for r in from_rosters:
        key = (r["team_id"], r.get("joined_at"))
        if key in existing:
            # 重複 → 削除
            if not dry_run:
                client.delete(f"{SUPABASE_URL}/rest/v1/team_rosters", params={
                    "id": f"eq.{r['id']}"
                }, headers=DB_HEADERS)
            continue

        # 移動
        if not dry_run:
            client.patch(f"{SUPABASE_URL}/rest/v1/team_rosters", params={
                "id": f"eq.{r['id']}"
            }, json={"player_id": to_id}, headers={**DB_HEADERS, "Prefer": "return=minimal"})
        moved += 1

    return moved, len(from_rosters) - moved


def merge_player_data(keep_id, merge_id, dry_run=False):
    """merge_idのデータでkeep_idの空フィールドを補完"""
    resp = client.get(f"{SUPABASE_URL}/rest/v1/players", params={
        "select": "*", "id": f"eq.{merge_id}"
    }, headers=DB_HEADERS)
    merge_data = resp.json()[0] if resp.json() else None

    resp = client.get(f"{SUPABASE_URL}/rest/v1/players", params={
        "select": "*", "id": f"eq.{keep_id}"
    }, headers=DB_HEADERS)
    keep_data = resp.json()[0] if resp.json() else None

    if not merge_data or not keep_data:
        return {}

    # 空フィールドを補完
    update = {}
    fields = ["real_name", "real_name_ja", "nationality", "region",
              "twitter_url", "twitch_url", "youtube_url",
              "liquipedia_url", "profile_image_url", "bio_ja", "bio_en"]

    for f in fields:
        if not keep_data.get(f) and merge_data.get(f):
            update[f] = merge_data[f]

    if update and not dry_run:
        client.patch(f"{SUPABASE_URL}/rest/v1/players", params={
            "id": f"eq.{keep_id}"
        }, json=update, headers={**DB_HEADERS, "Prefer": "return=minimal"})

    return update


def delete_player(player_id, dry_run=False):
    """選手を削除（is_active=falseにする。RLS DELETEポリシーがないため）"""
    if not dry_run:
        client.patch(f"{SUPABASE_URL}/rest/v1/players", params={
            "id": f"eq.{player_id}"
        }, json={"is_active": False, "bio_ja": "MERGED_DUPLICATE"}, headers={**DB_HEADERS, "Prefer": "return=minimal"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("重複選手統合")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN\n")

    total_merged = 0

    for merge_def in MERGES:
        print(f"\n--- {merge_def['name']} ---")

        keep_id, keep_ign = get_full_id(merge_def["keep_id"])
        if not keep_id:
            print(f"  keep ID not found: {merge_def['keep_id']}")
            continue
        print(f"  残す: {keep_ign} ({keep_id[:8]}..)")

        for short_id in merge_def["merge_ids"]:
            merge_id, merge_ign = get_full_id(short_id)
            if not merge_id:
                print(f"  merge ID not found: {short_id}")
                continue

            print(f"  統合: {merge_ign} ({merge_id[:8]}..)")

            # データ補完
            update = merge_player_data(keep_id, merge_id, dry_run=args.dry_run)
            if update:
                print(f"    データ補完: {list(update.keys())}")

            # ロースター移動
            moved, duped = move_rosters(merge_id, keep_id, dry_run=args.dry_run)
            print(f"    ロースター: {moved}件移動, {duped}件重複削除")

            # 削除（非アクティブ化）
            delete_player(merge_id, dry_run=args.dry_run)
            print(f"    → 非アクティブ化")
            total_merged += 1

    print(f"\n{'='*60}")
    print(f"統合完了: {total_merged}人を非アクティブ化")


if __name__ == "__main__":
    main()
