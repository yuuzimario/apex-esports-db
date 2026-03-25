"""
デバイスにAmazonアフィリエイトリンクを一括設定
Amazon商品検索ページのURLを使ってリンクを生成
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import re
import urllib.parse

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

TAG = "yuuzimario14-22"

client = httpx.Client(timeout=30)

# 手動ASIN マッピング（人気デバイスを優先的に設定）
# Amazon.co.jpのASINコード
ASIN_MAP = {
    # === マウス ===
    ("Logitech", "G PRO X SUPERLIGHT"): "B09MVD4TBN",
    ("Logitech", "G PRO X SUPERLIGHT 2"): "B0CKJ4HYYG",
    ("Logitech", "G PRO X SUPERLIGHT 2C"): "B0CKJ4HYYG",
    ("Logitech", "G PRO Wireless"): "B07T5YKVNR",
    ("Razer", "DeathAdder V3 Pro"): "B0B5YGR1KG",
    ("Razer", "Viper V3 Pro"): "B0D1X4J51X",
    ("Razer", "Viper V2 Pro"): "B09XFJCH1Q",
    ("Razer", "Viper Mini"): "B084WBZ5NR",
    ("Finalmouse", "Starlight Pro TenZ Edition"): "B09WQPDWKB",
    ("Xtrfy", "M42 Wireless"): "B0BWJQV2MH",
    ("Logitech", "G502 X LIGHTSPEED"): "B0B2LTF5G1",
    ("Logitech", "G502 HERO"): "B07GBZ4Q68",
    ("Pulsar", "X2 Mini"): "B0CKFKCR5W",
    ("Pulsar", "X2V2 Mini"): "B0DDZ9GGMQ",
    ("Zowie", "EC2-CW"): "B0C8T9DMMG",
    ("Endgame Gear", "XM2we"): "B0BP7P1XFX",
    ("SteelSeries", "Prime Mini Wireless"): "B097BGRFNS",
    # === キーボード ===
    ("Wooting", "60HE"): "B0D8THRQXJ",
    ("WOOTING", "60HE"): "B0D8THRQXJ",
    ("Ducky", "One 2 Mini"): "B08BXDFBWX",
    ("SteelSeries", "Apex Pro Mini"): "B0B7D4PVHM",
    ("SteelSeries", "Apex Pro Mini Wireless"): "B0B7D4PVHM",
    ("Corsair", "K70 RGB"): "B09HQFRZYR",
    ("Razer", "Huntsman Mini"): "B08BFD9NWQ",
    ("Razer", "Huntsman V2 TKL"): "B09M97Y2LN",
    ("DrunkDeer", "A75"): "B0C9LHJ8JP",
    ("HyperX", "Alloy Origins 60"): "B08G94VN2L",
    ("Logicool", "G PRO Keyboard"): "B08GZKT4G9",
    # === モニター ===
    ("ZOWIE", "XL2546K"): "B08LCMJNV7",
    ("ZOWIE", "XL2566K"): "B0B5CNQHRL",
    ("ZOWIE", "XL2540K"): "B08LCNXS4C",
    ("ZOWIE", "XL2540"): "B073JLYQVJ",
    ("Sony", "INZONE M10S"): "B0DJGFKD53",
    ("Sony", "M10S"): "B0DJGFKD53",
    ("SONY", "INZONE M10S"): "B0DJGFKD53",
    ("INZONE", "M10S"): "B0DJGFKD53",
    ("Alienware", "AW2523HF"): "B09XKVF5F5",
    ("Alienware", "AW2524HF"): "B0CTD3YBWK",
    ("ASUS", "VG279QM"): "B0845NXCVS",
    # === ヘッドセット ===
    ("Apple", "EarPods"): "B0C5B8ZY2P",
    ("Apple", "Earbuds"): "B0C5B8ZY2P",
    ("HyperX", "Cloud II"): "B00SAYCXWG",
    ("HyperX", "Cloud Alpha"): "B074NBSF9N",
    ("Logitech", "G PRO X"): "B0856GLJ8V",
    ("Logitech", "PRO X"): "B0856GLJ8V",
    ("Astro", "A50"): "B07RNKJ4HN",
    ("Astro", "A40"): "B07KSKSNFL",
    ("ASTRO", "A40"): "B07KSKSNFL",
    ("Sony", "INZONE Buds"): "B0D6MKX9QP",
    ("Sony", "INZONE H9"): "B0B7FMPYMS",
    ("SONY", "INZONE H9"): "B0B7FMPYMS",
    ("SteelSeries", "Arctis Nova Pro"): "B09ZYCFYKQ",
    # === マウスパッド ===
    ("Logitech", "G640"): "B01E4MA1VU",
    ("ZOWIE", "G-SR-SE"): "B095RBLH22",
    ("Skypad", "3.0"): "B0BQM99Y5S",
    ("Artisan", "Hien"): "B00800GKR2",
    ("Artisan", "Hayate Otsu"): "B00800GNBO",
    ("Artisan", "FX Zero"): "B00800GKH2",
    ("SteelSeries", "QcK Heavy"): "B000V7ARAU",
    ("SteelSeries", "QcK"): "B000UVRU6G",
    ("Razer", "Gigantus V2"): "B0842PPMF3",
    # === コントローラー ===
    ("Sony", "DualSense Edge"): "B0BSLFKFHQ",
    ("Sony", "DualShock 4"): "B01LWVX2RG",
    ("Battle Beaver", "DualSense"): "B0BSLFKFHQ",  # ベースはDualSense Edge
}


def make_affiliate_url(asin):
    """ASINからアフィリエイトURLを生成"""
    return f"https://www.amazon.co.jp/dp/{asin}?tag={TAG}"


def make_search_url(brand, model):
    """Amazon検索URLを生成（ASINが不明なデバイス用）"""
    query = f"{brand} {model}"
    encoded = urllib.parse.quote(query)
    return f"https://www.amazon.co.jp/s?k={encoded}&tag={TAG}"


def find_asin(brand, model):
    """ブランド+モデルからASINを検索"""
    # 完全一致
    key = (brand, model)
    if key in ASIN_MAP:
        return ASIN_MAP[key]

    # ブランド+モデル前半一致
    norm_brand = brand.lower().strip()
    norm_model = model.lower().strip()

    for (ab, am), asin in ASIN_MAP.items():
        if ab.lower() == norm_brand:
            # モデル名が含まれるか
            am_lower = am.lower()
            if am_lower in norm_model or norm_model in am_lower:
                return asin
            # 先頭部分一致
            if len(am_lower) >= 4 and norm_model.startswith(am_lower[:min(len(am_lower), 10)]):
                return asin

    return None


def main():
    print("=" * 60)
    print(f"Amazonアフィリエイトリンク一括設定 (tag: {TAG})")
    print("=" * 60)

    # 全デバイスを取得
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/devices",
        params={"select": "id,brand,model,category,amazon_url_ja"},
        headers=HEADERS,
    )
    devices = resp.json()
    print(f"総デバイス: {len(devices)}")

    updated = 0
    search_url_count = 0
    skipped = 0
    no_match = []

    for d in devices:
        brand = d["brand"]
        model = d["model"]

        # ASINを検索
        asin = find_asin(brand, model)

        if asin:
            url = make_affiliate_url(asin)
        else:
            # ASINが不明→Amazon検索URLを使う
            url = make_search_url(brand, model)
            search_url_count += 1

        # 既存のURLと同じならスキップ
        if d.get("amazon_url_ja") == url:
            skipped += 1
            continue

        # DB更新
        resp2 = client.patch(
            f"{SUPABASE_URL}/rest/v1/devices?id=eq.{d['id']}",
            json={"amazon_url_ja": url},
            headers={**HEADERS, "Prefer": "return=representation"},
        )
        if resp2.status_code in (200, 204):
            updated += 1
        else:
            print(f"  エラー: {d['brand']} {d['model']}: {resp2.status_code}")

    print(f"\n{'=' * 60}")
    print(f"結果:")
    print(f"  更新: {updated}件")
    print(f"  スキップ（変更なし）: {skipped}件")
    print(f"  商品ページ直リンク: {updated - search_url_count + skipped}件")
    print(f"  検索URL（ASIN不明）: {search_url_count}件")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
