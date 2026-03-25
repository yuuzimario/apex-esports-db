"""
Liquipediaから選手のデバイス情報をバルク取得→Supabase投入
Hardware tableテンプレートから mouse/keyboard/monitor/headset/mousepad/controller を抽出
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
from datetime import datetime

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {"User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)"}

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)

# デバイスカテゴリとLiquipediaフィールドのマッピング
DEVICE_MAP = {
    "mouse": {"brand": "mouse-brand", "model": "mouse-model"},
    "keyboard": {"brand": "keyboard-brand", "model": "keyboard-model"},
    "monitor": {"brand": "monitor-brand", "model": "monitor-model"},
    "headset": {"brand": "headset-brand", "model": "headset-model"},
    "mousepad": {"brand": "pad-brand", "model": "pad-model"},
    "controller": {"brand": "controller-brand", "model": "controller-model"},
}

# 人気デバイスのAmazonアフィリンク（後で拡充）
AMAZON_LINKS_JA = {
    # マウス
    ("Logitech", "G PRO X SUPERLIGHT"): "https://www.amazon.co.jp/dp/B09MVD4TBN?tag=apexdb-22",
    ("Logitech", "G PRO X SUPERLIGHT 2"): "https://www.amazon.co.jp/dp/B0CKJ4HYYG?tag=apexdb-22",
    ("Razer", "Viper V3 Pro"): "https://www.amazon.co.jp/dp/B0D1X4J51X?tag=apexdb-22",
    ("Razer", "DeathAdder V3 Pro"): "https://www.amazon.co.jp/dp/B0B5YGR1KG?tag=apexdb-22",
    # キーボード
    ("Wooting", "60HE"): "https://www.amazon.co.jp/dp/B0D8THRQXJ?tag=apexdb-22",
    # モニター
    ("ZOWIE", "XL2546K"): "https://www.amazon.co.jp/dp/B08LCMJNV7?tag=apexdb-22",
    # ヘッドセット
    ("Logitech", "G PRO X"): "https://www.amazon.co.jp/dp/B0856GLJ8V?tag=apexdb-22",
    # マウスパッド
    ("Artisan", "Hien"): "https://www.amazon.co.jp/dp/B00800GKR2?tag=apexdb-22",
    ("Logitech", "G640"): "https://www.amazon.co.jp/dp/B01E4MA1VU?tag=apexdb-22",
}


def normalize_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def extract_hardware(wikitext):
    """Hardware tableからデバイス情報を抽出"""
    hw_match = re.search(r"\{\{Hardware table(.*?)\}\}", wikitext, re.DOTALL | re.IGNORECASE)
    if not hw_match:
        return []

    hw_text = hw_match.group(1)
    devices = []

    for category, fields in DEVICE_MAP.items():
        brand_match = re.search(rf"\|\s*{fields['brand']}\s*=\s*([^\n|]+)", hw_text, re.IGNORECASE)
        model_match = re.search(rf"\|\s*{fields['model']}\s*=\s*([^\n|]+)", hw_text, re.IGNORECASE)

        brand = brand_match.group(1).strip() if brand_match else ""
        model = model_match.group(1).strip() if model_match else ""

        # desc（追加説明）があればモデルに追加
        desc_field = fields['model'].replace('-model', '-desc')
        desc_match = re.search(rf"\|\s*{desc_field}\s*=\s*([^\n|]+)", hw_text, re.IGNORECASE)
        if desc_match and desc_match.group(1).strip():
            model = f"{model} {desc_match.group(1).strip()}".strip()

        if brand or model:
            # ブランド名の正規化
            brand = brand.replace("Logitech G", "Logitech").replace("SONY", "Sony")
            if brand and model:
                devices.append({
                    "category": category,
                    "brand": brand,
                    "model": model,
                })

    return devices


def find_amazon_link(brand, model):
    """デバイスに合うAmazonアフィリンクを検索"""
    # 完全一致
    key = (brand, model)
    if key in AMAZON_LINKS_JA:
        return AMAZON_LINKS_JA[key]

    # 部分一致（ブランド+モデル前半）
    norm_brand = brand.lower()
    norm_model = model.lower()
    for (ab, am), url in AMAZON_LINKS_JA.items():
        if ab.lower() == norm_brand and am.lower() in norm_model:
            return url

    return None


def main():
    print("=" * 60)
    print("デバイス情報取得 & Supabase投入")
    print("=" * 60)

    # Step 3で取得済みのLiquipedia SNSデータを使う（wikitextを再取得する必要がある）
    with open(os.path.join(CACHE_DIR, "liquipedia_sns.json"), "r", encoding="utf-8") as f:
        sns_data = json.load(f)

    # DB上の選手IDマッピング
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/players",
        params={"select": "id,ign,slug", "is_active": "eq.true"},
        headers=HEADERS,
    )
    db_players = resp.json()
    players_by_norm = {normalize_name(p["ign"]): p for p in db_players}

    # 既存デバイスデータをチェック
    resp2 = client.get(
        f"{SUPABASE_URL}/rest/v1/devices",
        params={"select": "player_id,category"},
        headers=HEADERS,
    )
    existing_devices = set()
    for d in resp2.json():
        existing_devices.add((d["player_id"], d["category"]))

    # Liquipediaでページがある選手のリスト
    lp_players = []
    for norm_key, pdata in sns_data.get("players", {}).items():
        lp_title = pdata.get("liquipedia_title")
        if lp_title:
            db_player = players_by_norm.get(norm_key)
            if db_player:
                lp_players.append({
                    "db_id": db_player["id"],
                    "ign": db_player["ign"],
                    "lp_title": lp_title,
                })

    print(f"Liquipediaページあり: {len(lp_players)}選手")

    # バルクでwikitextを取得してデバイス情報を抽出
    batch_size = 50
    total_devices = 0
    players_with_devices = 0
    all_devices = []

    for i in range(0, len(lp_players), batch_size):
        batch = lp_players[i:i + batch_size]
        titles = [p["lp_title"] for p in batch]
        titles_str = "|".join(titles)

        params = {
            "action": "query",
            "titles": titles_str,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
        }

        resp = client.get(LP_API, params=params, headers=LP_HEADERS)
        time.sleep(2)

        if resp.status_code != 200:
            print(f"  APIエラー: {resp.status_code}")
            continue

        pages = resp.json().get("query", {}).get("pages", {})

        # タイトル→DB情報のマッピング
        title_to_player = {p["lp_title"]: p for p in batch}

        for pid, page in pages.items():
            if int(pid) < 0:
                continue
            title = page.get("title", "")
            revs = page.get("revisions", [])
            if not revs:
                continue

            content = revs[0].get("slots", {}).get("main", {}).get("*", "")
            if not content:
                content = revs[0].get("*", "")

            devices = extract_hardware(content)
            if not devices:
                continue

            player_info = title_to_player.get(title)
            if not player_info:
                continue

            players_with_devices += 1
            for device in devices:
                # 既にDBにあるかチェック
                if (player_info["db_id"], device["category"]) in existing_devices:
                    continue

                amazon_url = find_amazon_link(device["brand"], device["model"])

                all_devices.append({
                    "player_id": player_info["db_id"],
                    "category": device["category"],
                    "brand": device["brand"],
                    "model": device["model"],
                    "amazon_url_ja": amazon_url,
                })
                total_devices += 1

        batch_num = i // batch_size + 1
        total_batches = (len(lp_players) + batch_size - 1) // batch_size
        print(f"  バッチ {batch_num}/{total_batches} 完了 (累計: {players_with_devices}選手, {total_devices}デバイス)")

    # Supabaseに投入（50件ずつ）
    print(f"\n--- Supabase投入 ---")
    inserted = 0
    for i in range(0, len(all_devices), 50):
        batch = all_devices[i:i + 50]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/devices",
            json=batch,
            headers={**HEADERS, "Prefer": "return=representation"},
        )
        if resp.status_code in (200, 201):
            inserted += len(resp.json())
        else:
            print(f"  INSERT エラー: {resp.status_code}: {resp.text[:200]}")

    # デバイス統計
    device_stats = {}
    for d in all_devices:
        cat = d["category"]
        device_stats[cat] = device_stats.get(cat, 0) + 1

    affiliate_count = sum(1 for d in all_devices if d.get("amazon_url_ja"))

    # キャッシュ保存
    cache_path = os.path.join(CACHE_DIR, "devices_data.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "total_players_with_devices": players_with_devices,
            "total_devices": total_devices,
            "devices": all_devices,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"結果:")
    print(f"  デバイス情報あり: {players_with_devices}選手")
    print(f"  デバイス総数: {total_devices}")
    print(f"  DB投入: {inserted}件")
    print(f"  アフィリンク付き: {affiliate_count}件")
    print(f"\nカテゴリ別:")
    for cat, count in sorted(device_stats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"\nキャッシュ: {cache_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
