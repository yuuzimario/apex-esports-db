"""
Liquipediaから選手プロフィール画像を取得
→ players.profile_image_url を更新

画像はLiquipedia commonsから直接参照（ホットリンク）
CC BY-SA 3.0ライセンス（フッターに帰属表示済み）

使い方:
  python fetch_player_images.py --dry-run    # DB更新なし
  python fetch_player_images.py              # 本番実行
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
lp_client = httpx.Client(timeout=30, headers=LP_HEADERS)

BATCH_SIZE = 50
BATCH_DELAY = 3


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


def supabase_update(player_id, data):
    headers = {**DB_HEADERS, "Prefer": "return=minimal"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/players",
        params={"id": f"eq.{player_id}"},
        json=data,
        headers=headers,
    )
    return resp.status_code in (200, 204)


def batch_query_lp(titles):
    """Liquipedia APIでバッチ取得"""
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }
    for attempt in range(3):
        try:
            resp = lp_client.get(LP_API, params=params)
        except Exception as e:
            print(f"    HTTPエラー: {e}")
            time.sleep(30)
            continue
        if resp.status_code == 429:
            wait = 60 * (attempt + 1)
            print(f"    レート制限。{wait}秒待機...")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            return {}
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        result = {}
        for pid, pdata in pages.items():
            if pid == "-1":
                continue
            title = pdata.get("title", "")
            revisions = pdata.get("revisions", [])
            if revisions:
                result[title] = revisions[0].get("*", "")
        return result
    return {}


def batch_get_image_urls(filenames):
    """複数の画像ファイル名からURLを一括取得"""
    if not filenames:
        return {}

    titles = [f"File:{f}" for f in filenames]
    results = {}

    # バッチ50件ずつ
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i+BATCH_SIZE]
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        }
        try:
            resp = lp_client.get(LP_API, params=params)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    imageinfo = pdata.get("imageinfo", [])
                    if imageinfo:
                        url = imageinfo[0].get("url", "")
                        # File:プレフィックスを除去してファイル名をキーにする
                        title = pdata.get("title", "")
                        fname = title.replace("File:", "") if title.startswith("File:") else title
                        results[fname] = url
        except Exception:
            pass
        if i + BATCH_SIZE < len(titles):
            time.sleep(BATCH_DELAY)

    return results


def extract_player_image(wikitext):
    """wikitextから選手画像ファイル名を抽出"""
    if "Infobox player" not in wikitext:
        return None

    # image フィールド（imagedarkではなく通常のimage）
    m = re.search(r"\|\s*image\s*=\s*(.+?)(?:\n|\|)", wikitext)
    if m:
        filename = m.group(1).strip()
        # バリデーション
        if not filename or filename.startswith("{{") or filename.startswith("<!--") or "=" in filename:
            return None
        if len(filename) < 3:
            return None
        return filename

    return None


def main():
    parser = argparse.ArgumentParser(description="選手プロフィール画像取得")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia 選手プロフィール画像取得")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # LP URLがある選手を取得（画像未設定のみ）
    players = supabase_get_all("players", {
        "select": "id,ign,liquipedia_url,profile_image_url",
    })

    # LP URLがあり、画像がまだない選手
    targets = [p for p in players if p.get("liquipedia_url") and not p.get("profile_image_url")]
    already = [p for p in players if p.get("profile_image_url")]

    print(f"全選手: {len(players)}")
    print(f"LP URLあり+画像なし: {len(targets)}")
    print(f"既に画像あり: {len(already)}")

    # LP URLからタイトル抽出
    title_to_player = {}
    titles = []
    for p in targets:
        url = p["liquipedia_url"]
        title = url.split("/apexlegends/")[-1].replace("_", " ") if "/apexlegends/" in url else None
        if title:
            title_to_player[title] = p
            titles.append(title)

    print(f"検索対象: {len(titles)}件\n")

    stats = {"found": 0, "updated": 0, "no_image": 0, "lp_requests": 0}

    # Phase 1: バッチ取得して画像ファイル名を収集
    image_files = {}  # player_id → filename
    player_map = {}   # filename → player

    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(titles) - 1) // BATCH_SIZE + 1
        print(f"  バッチ {batch_num}/{total_batches} ({len(batch)}件)")

        pages = batch_query_lp(batch)
        stats["lp_requests"] += 1

        for title, wikitext in pages.items():
            player = title_to_player.get(title)
            if not player:
                # 正規化マッチ
                norm = "".join(c.lower() for c in title if c.isalnum())
                for t, p in title_to_player.items():
                    if "".join(c.lower() for c in t if c.isalnum()) == norm:
                        player = p
                        break
            if not player:
                continue

            filename = extract_player_image(wikitext)
            if filename:
                image_files[player["id"]] = filename
                player_map[filename] = player
                stats["found"] += 1
            else:
                stats["no_image"] += 1

        time.sleep(BATCH_DELAY)

    print(f"\n画像あり: {stats['found']}人 / 画像なし: {stats['no_image']}人")

    if not image_files:
        print("画像が見つかりませんでした。")
        return

    # Phase 2: 画像URLを一括取得
    print(f"\n--- 画像URL取得 ({len(image_files)}件) ---")
    all_filenames = list(set(image_files.values()))
    url_map = batch_get_image_urls(all_filenames)
    stats["lp_requests"] += (len(all_filenames) - 1) // BATCH_SIZE + 1

    print(f"  URL取得成功: {len(url_map)}件")

    # Phase 3: DB更新
    print(f"\n--- DB更新 ---")
    for player_id, filename in image_files.items():
        url = url_map.get(filename)
        if not url:
            continue

        player = player_map.get(filename)
        ign = player["ign"] if player else "?"

        if args.dry_run:
            print(f"  {ign} → {url[:80]}...")
        else:
            if supabase_update(player_id, {"profile_image_url": url}):
                stats["updated"] += 1
            else:
                print(f"  更新失敗: {ign}")

    # レポート
    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  画像発見: {stats['found']}人")
    print(f"  画像なし: {stats['no_image']}人")
    print(f"  URL取得成功: {len(url_map)}件")
    print(f"  DB更新: {stats['updated']}件")
    print(f"  Liquipediaリクエスト: {stats['lp_requests']}回")


if __name__ == "__main__":
    main()
