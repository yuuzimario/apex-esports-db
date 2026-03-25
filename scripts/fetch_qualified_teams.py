"""
Battlefy — Qualified teamsを取得（数値ID=177を使用）
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"
CF_BASE = "https://d3q4fnxloga6gz.cloudfront.net"
SEASON_SLUG = "algs-season-6"

with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
    discovery = json.load(f)


def main():
    print("=" * 70)
    print("Qualified teams 取得")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = context.new_page()

        # ページ読み込み
        print("Loading battlefy...")
        try:
            page.goto("https://battlefy.com/apex-legends-global-series-year-6",
                       wait_until="load", timeout=60000)
            time.sleep(8)
        except Exception:
            pass

        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # 数値ID=177でqualified teams取得（ページ読み込み時にキャプチャされたパターン）
        qt_url = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/177"
        print(f"\nFetching: {qt_url}")
        result = page.evaluate("""
            async (url) => {
                try {
                    const r = await fetch(url);
                    const text = await r.text();
                    return { status: r.status, body: text };
                } catch(e) {
                    return { error: e.message };
                }
            }
        """, qt_url)

        if result and result.get("status") == 200:
            data = json.loads(result["body"])
            if isinstance(data, list):
                print(f"Qualified teams: {len(data)}")
                discovery["qualified_teams"]["Online Opens (lb177)"] = data
                for t in data:
                    name = t.get("name", "?")
                    placement = t.get("placement", "?")
                    event_name = t.get("event", {}).get("name", "") if isinstance(t.get("event"), dict) else t.get("event", "")
                    meta = t.get("meta", {})
                    print(f"  {placement}. {name} | event={event_name} | meta={json.dumps(meta, default=str)[:100]}")
            else:
                print(f"Unexpected type: {type(data)}")
        else:
            print(f"Failed: {result}")

        # リーダーボード全データのチーム詳細（breakdown=プレイヤー名）の完全性確認
        print("\n--- リーダーボード サンプルデータ確認 ---")
        for key, lb in discovery["leaderboards"].items():
            teams = lb.get("teams", [])
            if teams:
                t = teams[0]
                print(f"\n{key} サンプル:")
                print(f"  Keys: {list(t.keys())}")
                print(f"  Name: {t.get('name')}")
                print(f"  TeamID: {t.get('teamID')}")
                print(f"  Score: {t.get('score')}")
                print(f"  Rank: {t.get('rank')}")
                print(f"  Region: {t.get('region')}")
                breakdown = t.get("breakdown", [])
                print(f"  Breakdown ({len(breakdown)} players):")
                for b in breakdown:
                    print(f"    {b.get('name')} (subID: {b.get('subID')})")
                meta = t.get("meta", {})
                print(f"  Meta: {meta}")

        browser.close()

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(discovery, f, ensure_ascii=False, indent=2, default=str)

    file_size = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n保存完了: {OUTPUT_FILE} ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
