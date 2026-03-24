"""
Liquipediaからチームロゴをダウンロードしてpublic/logos/に保存 + DB更新
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import time
import os

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "logos")
client = httpx.Client(timeout=30)


def main():
    # ロゴURLがあるチームを取得
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/teams?select=id,slug,logo_url&logo_url=not.is.null",
        headers=HEADERS,
    )
    teams = resp.json()
    print(f"ロゴダウンロード対象: {len(teams)} チーム")

    for team in teams:
        slug = team["slug"]
        logo_url = team["logo_url"]
        ext = logo_url.split(".")[-1].split("?")[0].lower()
        if ext not in ("png", "jpg", "jpeg", "svg", "webp"):
            ext = "png"

        filename = f"{slug}.{ext}"
        filepath = os.path.join(LOGO_DIR, filename)

        if os.path.exists(filepath):
            print(f"  スキップ（既存）: {slug}")
            continue

        print(f"  ダウンロード中: {slug}...")
        try:
            img_resp = client.get(logo_url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
            if img_resp.status_code == 200 and len(img_resp.content) > 100:
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)
                print(f"    保存完了: {filename} ({len(img_resp.content)} bytes)")

                # DBのlogo_urlをローカルパスに更新
                new_url = f"/logos/{filename}"
                update_resp = client.patch(
                    f"{SUPABASE_URL}/rest/v1/teams?id=eq.{team['id']}",
                    json={"logo_url": new_url},
                    headers={**HEADERS, "Prefer": "return=representation"},
                )
                if update_resp.status_code in (200, 204):
                    print(f"    DB更新完了: {new_url}")
                else:
                    print(f"    DB更新エラー: {update_resp.status_code}")
            else:
                print(f"    ダウンロード失敗: {img_resp.status_code}")
        except Exception as e:
            print(f"    エラー: {e}")

        time.sleep(1)

    print(f"\n完了！ロゴは {LOGO_DIR} に保存されました")


if __name__ == "__main__":
    main()
