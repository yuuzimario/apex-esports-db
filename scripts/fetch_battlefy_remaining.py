"""
Battlefy — NA/APAC_N リーダーボード取得（Playwright経由）
httpxでタイムアウトしたリージョンをブラウザコンテキスト内fetchで取得
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

REGIONS_NEEDED = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
}

# 既存データ読み込み
with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
    discovery = json.load(f)
leaderboards = discovery.get("leaderboards", {})
qualified = discovery.get("qualified_teams", {})


def main():
    print("=" * 70)
    print("Battlefy — Playwright経由で残りのリーダーボード取得")
    print("=" * 70)

    captured_data = {}

    def on_response(response):
        url = response.url
        try:
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            if "team-leaderboards" in url or "qualified-teams" in url:
                body = response.text()
                data = json.loads(body)
                captured_data[url] = data
                if isinstance(data, dict) and "total" in data:
                    print(f"  [CAPTURED] {url[:120]} — {data['total']} teams")
                elif isinstance(data, list):
                    print(f"  [CAPTURED] {url[:120]} — Array[{len(data)}]")
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.on("response", on_response)

        # ページ読み込み
        print("\nLoading battlefy...")
        try:
            page.goto("https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers",
                       wait_until="load", timeout=60000)
            time.sleep(8)
        except Exception as e:
            print(f"  Load error: {e}")

        # Cookie拒否
        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # 各リージョンのページを訪問してAPIキャプチャ
        for region, rs in REGIONS_NEEDED.items():
            print(f"\n--- {rs} ({region}) ---")
            region_url = f"https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/{region}"
            print(f"  Visiting: {region_url}")
            try:
                page.goto(region_url, wait_until="load", timeout=60000)
                time.sleep(8)
                # スクロールで追加データ読み込み
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 500)")
                    time.sleep(1)
            except Exception as e:
                print(f"  Error: {e}")

        # ブラウザコンテキスト内でfetch
        print("\n--- ブラウザfetchで直接取得 ---")
        for region, rs in REGIONS_NEEDED.items():
            key = f"Online Opens|{rs}"
            if key in leaderboards and leaderboards[key].get("total", 0) > 0:
                print(f"  {rs}: 既に取得済み — スキップ")
                continue

            lb_url = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/177?region={region}&offset=0&limit=200"
            print(f"  {rs} leaderboard fetch: ", end="")
            try:
                result = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{lb_url}");
                            const text = await r.text();
                            return {{ status: r.status, body: text, length: text.length }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                if result and result.get("status") == 200 and result.get("body"):
                    data = json.loads(result["body"])
                    total = data.get("total", 0)
                    teams = data.get("data", [])
                    print(f"{total} teams!")

                    # ページネーション
                    while len(teams) < total:
                        offset = len(teams)
                        url2 = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/177?region={region}&offset={offset}&limit=200"
                        result2 = page.evaluate(f"""
                            async () => {{
                                try {{
                                    const r = await fetch("{url2}");
                                    const text = await r.text();
                                    return {{ status: r.status, body: text }};
                                }} catch(e) {{
                                    return {{ error: e.message }};
                                }}
                            }}
                        """)
                        if result2 and result2.get("status") == 200:
                            data2 = json.loads(result2["body"])
                            teams.extend(data2.get("data", []))
                        else:
                            break

                    leaderboards[key] = {
                        "total": total,
                        "teams": teams,
                        "lb_id": 177,
                        "region": region,
                    }
                    for t in teams[:5]:
                        name = t.get("name", "?")
                        score = t.get("score", "?")
                        rank = t.get("rank", "?")
                        players = [b.get("name", "?") for b in t.get("breakdown", [])]
                        print(f"    {rank}. {name} ({score} pts) — {', '.join(players)}")
                else:
                    print(f"failed: {result.get('status', result.get('error', '?'))}")
            except Exception as e:
                print(f"error: {e}")

        # Qualified teams もブラウザfetchで取得
        print("\n--- Qualified teams (ブラウザfetch) ---")
        events = discovery.get("events", [])
        for ev in events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            if ename in qualified and len(qualified[ename]) > 0:
                print(f"  {ename}: 既に取得済み — スキップ")
                continue

            qt_url = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{eid}"
            try:
                result = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{qt_url}");
                            const text = await r.text();
                            return {{ status: r.status, body: text }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                if result and result.get("status") == 200 and result.get("body"):
                    data = json.loads(result["body"])
                    if isinstance(data, list) and len(data) > 0:
                        qualified[ename] = data
                        print(f"  {ename}: {len(data)} teams")
                        for t in data[:3]:
                            print(f"    {t.get('name', '?')} | placement: {t.get('placement', '?')}")
                    else:
                        print(f"  {ename}: empty")
                else:
                    print(f"  {ename}: {result.get('status', result.get('error', '?'))}")
            except Exception as e:
                print(f"  {ename}: error {e}")

        # キャプチャされたデータも追加
        print(f"\n--- キャプチャされたAPI: {len(captured_data)} ---")
        for url, data in captured_data.items():
            if "team-leaderboards" in url:
                for region, rs in {**REGIONS_NEEDED, "asia-pacific-south": "APAC_S", "europe-middle-east-and-africa": "EMEA"}.items():
                    if region in url:
                        key = f"Online Opens|{rs}"
                        if key not in leaderboards or leaderboards[key].get("total", 0) == 0:
                            if isinstance(data, dict) and data.get("total", 0) > 0:
                                leaderboards[key] = {
                                    "total": data["total"],
                                    "teams": data.get("data", []),
                                    "lb_id": 177,
                                    "region": region,
                                }
                                print(f"  Added captured {key}: {data['total']} teams")
                        break
            elif "qualified-teams" in url:
                if isinstance(data, list) and len(data) > 0:
                    eid = url.split("/")[-1]
                    # イベントIDからイベント名を逆引き
                    for ev in events:
                        if ev["event_id"] == eid:
                            ename = ev["event_name"]
                            if ename not in qualified or len(qualified[ename]) == 0:
                                qualified[ename] = data
                                print(f"  Added captured qualified {ename}: {len(data)} teams")
                            break

        browser.close()

    # 保存
    discovery["leaderboards"] = leaderboards
    discovery["qualified_teams"] = qualified

    # サマリー
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_teams = 0
    total_players = set()

    print(f"\nリーダーボード: {len(leaderboards)} datasets")
    for key, lb in sorted(leaderboards.items()):
        total = lb.get("total", 0)
        teams = lb.get("teams", [])
        total_teams += len(teams)
        for t in teams:
            for b in t.get("breakdown", []):
                total_players.add(b.get("subID", ""))
        print(f"  {key}: {total} teams ({len(teams)} fetched)")

    print(f"\nQualified teams: {len(qualified)} events")
    for key, qt in sorted(qualified.items()):
        print(f"  {key}: {len(qt)} teams")

    print(f"\n合計: {total_teams} チームエントリ, {len(total_players)} ユニークプレイヤー")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(discovery, f, ensure_ascii=False, indent=2, default=str)

    file_size = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n保存完了: {OUTPUT_FILE} ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
