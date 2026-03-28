"""
Liquipediaの選手画像をローカルにダウンロード
→ public/players/ に保存、profile_image_url をローカルパスに更新

Liquipediaはホットリンクを403でブロックするため、ローカル保存が必要

使い方:
  python download_player_images.py --dry-run
  python download_player_images.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import os
import time
import argparse

PLAYERS_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/public/players"
os.makedirs(PLAYERS_DIR, exist_ok=True)

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
# リファラーなしでリクエスト（Liquipediaホットリンク防止回避）
dl_client = httpx.Client(timeout=30, headers={
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
}, follow_redirects=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("選手画像ダウンロード")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN\n")

    # Liquipedia URLが入ってる選手を取得
    all_players = []
    offset = 0
    while True:
        resp = client.get(f"{SUPABASE_URL}/rest/v1/players", params={
            "select": "id,ign,slug,profile_image_url",
            "profile_image_url": "not.is.null",
            "limit": "1000", "offset": str(offset),
        }, headers=DB_HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        all_players.extend(data)
        if len(data) < 1000:
            break
        offset += 1000

    # liquipedia URLのものだけ（既にローカルパスに変更済みは除外）
    targets = [p for p in all_players if p["profile_image_url"].startswith("http")]
    already_local = [p for p in all_players if p["profile_image_url"].startswith("/players/")]

    print(f"対象: {len(targets)}人 (既にローカル: {len(already_local)}人)")

    stats = {"downloaded": 0, "failed": 0, "skipped": 0}

    for i, player in enumerate(targets):
        slug = player["slug"]
        url = player["profile_image_url"]

        # 拡張子
        ext = url.split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        local_filename = f"{slug}.{ext}"
        local_path = os.path.join(PLAYERS_DIR, local_filename)
        db_path = f"/players/{local_filename}"

        # 既にダウンロード済み
        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            stats["skipped"] += 1
            # DB更新だけ
            if not args.dry_run:
                client.patch(
                    f"{SUPABASE_URL}/rest/v1/players",
                    params={"id": f"eq.{player['id']}"},
                    json={"profile_image_url": db_path},
                    headers={**DB_HEADERS, "Prefer": "return=minimal"},
                )
            continue

        if args.dry_run:
            if i < 5:
                print(f"  {player['ign']} → {db_path}")
            continue

        # ダウンロード
        try:
            resp = dl_client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(local_path, "wb") as f:
                    f.write(resp.content)

                # DB更新
                client.patch(
                    f"{SUPABASE_URL}/rest/v1/players",
                    params={"id": f"eq.{player['id']}"},
                    json={"profile_image_url": db_path},
                    headers={**DB_HEADERS, "Prefer": "return=minimal"},
                )
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1
                if i < 20:
                    print(f"  FAIL: {player['ign']} ({resp.status_code}, {len(resp.content)}bytes)")
        except Exception as e:
            stats["failed"] += 1
            print(f"  ERROR: {player['ign']}: {e}")

        # 100件ごとに進捗表示
        if (i + 1) % 100 == 0:
            print(f"  進捗: {i+1}/{len(targets)} (DL:{stats['downloaded']}, fail:{stats['failed']})")

        # レート制限（画像ダウンロードは軽めに）
        if (i + 1) % 10 == 0:
            time.sleep(1)

    print(f"\n{'='*60}")
    print("結果")
    print(f"{'='*60}")
    print(f"  ダウンロード: {stats['downloaded']}")
    print(f"  スキップ（済み）: {stats['skipped']}")
    print(f"  失敗: {stats['failed']}")


if __name__ == "__main__":
    main()
