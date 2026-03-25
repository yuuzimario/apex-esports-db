"""
同一選手×同一チームの連続ロースターレコードを統合する
- 同じplayer_id + team_idが連続 → 1レコードに統合
- joined_at: 最も早い日付を採用
- left_at: 最も遅い日付を採用（Noneがあればアクティブ=None）
- 統合後、余分なレコードを削除

使い方:
  python merge_duplicate_rosters.py          # 本番実行
  python merge_duplicate_rosters.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import argparse
import time
from collections import defaultdict

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)


def supabase_get_all(table, select="*", order="player_id,joined_at"):
    """全レコード取得（ページネーション）"""
    all_data = []
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params={"select": select, "order": order, "limit": "1000", "offset": str(offset)},
            headers=DB_HEADERS,
        )
        if resp.status_code != 200:
            print(f"  GET エラー: {resp.status_code}: {resp.text[:200]}")
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return all_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("重複ロースター統合")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # 全ロースター取得
    print("ロースター取得中...")
    rosters = supabase_get_all("team_rosters")
    print(f"  全ロースター: {len(rosters)}件")

    # 選手名・チーム名取得（表示用）
    players = {}
    for p in supabase_get_all("players", select="id,ign", order="id"):
        players[p["id"]] = p["ign"]
    teams = {}
    for t in supabase_get_all("teams", select="id,name", order="id"):
        teams[t["id"]] = t["name"]

    # 選手ごとにグループ化
    by_player = defaultdict(list)
    for r in rosters:
        by_player[r["player_id"]].append(r)

    # 統合対象を検出
    to_update = []  # (keep_id, new_joined_at, new_left_at)
    to_delete = []  # [id, ...]

    for pid, player_rosters in by_player.items():
        # joined_atでソート（Noneは末尾）
        player_rosters.sort(key=lambda x: x["joined_at"] or "9999-99-99")

        # 連続する同一チームをグループ化
        groups = []
        current_group = [player_rosters[0]]

        for i in range(1, len(player_rosters)):
            prev = player_rosters[i - 1]
            curr = player_rosters[i]

            if curr["team_id"] == prev["team_id"]:
                # 同じチーム → グループに追加
                current_group.append(curr)
            else:
                groups.append(current_group)
                current_group = [curr]
        groups.append(current_group)

        # 2件以上のグループを統合
        for group in groups:
            if len(group) < 2:
                continue

            # 最も早いjoined_at
            joined_dates = [r["joined_at"] for r in group if r["joined_at"]]
            best_joined = min(joined_dates) if joined_dates else None

            # left_at: Noneがあれば現在アクティブ、なければ最も遅い日付
            left_dates = [r["left_at"] for r in group if r["left_at"]]
            has_none = any(r["left_at"] is None for r in group)

            if has_none:
                best_left = None  # まだ在籍中
            elif left_dates:
                best_left = max(left_dates)
            else:
                best_left = None

            # joined_at > left_at の異常を修正
            if best_joined and best_left and best_joined > best_left:
                # 全日付から最小と最大を取る
                all_dates = joined_dates + left_dates
                best_joined = min(all_dates)
                best_left = max(all_dates)

            # 最初のレコードを残し、残りを削除
            keep = group[0]
            delete_ids = [r["id"] for r in group[1:]]

            to_update.append({
                "id": keep["id"],
                "joined_at": best_joined,
                "left_at": best_left,
                "player_name": players.get(pid, f"ID:{pid}"),
                "team_name": teams.get(keep["team_id"], f"TID:{keep['team_id']}"),
                "merged_count": len(group),
            })
            to_delete.extend(delete_ids)

    print(f"\n統合対象: {len(to_update)}グループ（{len(to_delete)}件削除予定）")

    # サンプル表示
    print(f"\n--- 統合例（上位20件）---")
    for u in to_update[:20]:
        left_str = u["left_at"] or "現在"
        print(f"  {u['player_name']} @ {u['team_name']}: {u['joined_at']} ~ {left_str} ({u['merged_count']}件→1件)")

    if args.dry_run:
        print(f"\nDRY-RUN: {len(to_delete)}件の削除をスキップ")
        return

    # --- 実行 ---
    print(f"\n--- 統合実行 ---")

    # 1. 残すレコードを更新
    updated = 0
    for u in to_update:
        headers = {**DB_HEADERS, "Prefer": "return=minimal"}
        resp = client.patch(
            f"{SUPABASE_URL}/rest/v1/team_rosters?id=eq.{u['id']}",
            json={"joined_at": u["joined_at"], "left_at": u["left_at"]},
            headers=headers,
        )
        if resp.status_code in (200, 204):
            updated += 1
        else:
            print(f"  UPDATE エラー ({u['id']}): {resp.status_code}: {resp.text[:200]}")
        if updated % 50 == 0 and updated > 0:
            print(f"    更新: {updated}/{len(to_update)}")
        time.sleep(0.1)
    print(f"  更新完了: {updated}件")

    # 2. 余分なレコードを削除（バッチ）
    deleted = 0
    batch_size = 20
    for i in range(0, len(to_delete), batch_size):
        batch = to_delete[i:i + batch_size]
        # OR条件で一括削除
        id_filter = ",".join(batch)
        resp = client.delete(
            f"{SUPABASE_URL}/rest/v1/team_rosters?id=in.({id_filter})",
            headers={**DB_HEADERS, "Prefer": "return=minimal"},
        )
        if resp.status_code in (200, 204):
            deleted += len(batch)
        else:
            print(f"  DELETE エラー: {resp.status_code}: {resp.text[:200]}")
        if (i // batch_size) % 10 == 0 and i > 0:
            print(f"    削除: {deleted}/{len(to_delete)}")
        time.sleep(0.1)
    print(f"  削除完了: {deleted}件")

    print(f"\n完了！ {len(to_update)}グループ統合、{deleted}件削除")


if __name__ == "__main__":
    main()
