"""
Battlefy ALGS Year 6 トーナメントID発見スクリプト v3
組織ID 696be0f0604fabcc432430ac を使って全トーナメントを探索
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"

ORG_ID = "696be0f0604fabcc432430ac"
ORG_SLUG = "apex-legends-global-series-year-6"

# 全API応答を記録
captured_api = []
tournaments = {}
teams_data = {}


def on_response(response):
    """全APIレスポンスを傍受"""
    url = response.url
    # 静的リソース除外
    if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.ico', '.gif', '.webp']):
        return
    if any(x in url for x in ['google', 'facebook', 'analytics', 'sentry', 'segment',
                                'hotjar', 'cookielaw', 'onetrust', 'ads.', 'doubleclick']):
        return

    try:
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        body = response.text()
        if not body or len(body) < 5:
            return

        data = json.loads(body)
        captured_api.append({
            "url": url,
            "status": response.status,
            "size": len(body),
        })
        print(f"  [API] {response.status} {url[:120]} ({len(body)} bytes)")

        # データ構造をDump
        if isinstance(data, list) and len(data) > 0:
            sample = data[0] if isinstance(data[0], dict) else data[0]
            if isinstance(sample, dict):
                keys = list(sample.keys())[:15]
                print(f"    Array[{len(data)}], sample keys: {keys}")
                # トーナメントか？
                if "_id" in sample and any(k in sample for k in ["startTime", "stages", "teamCount", "bracketType"]):
                    for item in data:
                        tid = item.get("_id", "")
                        name = item.get("name", "")
                        tournaments[tid] = {
                            "name": name,
                            "startTime": item.get("startTime", ""),
                            "teamCount": item.get("teamCount", 0),
                            "slug": item.get("slug", ""),
                            "status": item.get("status", ""),
                            "source_url": url,
                        }
                        print(f"    TOURNAMENT: {name} | {tid} | teams={item.get('teamCount', 0)}")
                # チームか？
                elif "_id" in sample and "players" in sample:
                    tournament_id = sample.get("tournamentID", url.split("/")[-2] if "/teams" in url else "")
                    teams_data[tournament_id] = data
                    print(f"    TEAMS: {len(data)} teams for tournament {tournament_id}")
        elif isinstance(data, dict):
            keys = list(data.keys())[:15]
            print(f"    Object, keys: {keys}")

    except Exception:
        pass


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 トーナメント発見 v3")
    print(f"Organization ID: {ORG_ID}")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("response", on_response)

        # === Step 1: Org ページを開いてAPIコールを傍受 ===
        print("\n--- Step 1: Load org page and capture API calls ---")
        page.goto(f"https://battlefy.com/{ORG_SLUG}", wait_until="networkidle", timeout=45000)
        time.sleep(3)

        # Cookie拒否
        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # __NEXT_DATA__ を詳細解析
        print("\n--- Step 2: Deep parse __NEXT_DATA__ ---")
        next_data = page.evaluate("() => { try { return window.__NEXT_DATA__ } catch(e) { return null } }")
        if next_data:
            # 全体をJSON文字列化して保存
            nd_str = json.dumps(next_data, default=str)
            with open(CACHE_DIR / "next_data_full.json", "w", encoding="utf-8") as f:
                f.write(nd_str)
            print(f"  __NEXT_DATA__ saved ({len(nd_str)} bytes)")

            # 再帰的に全オブジェクトを探索
            def walk(obj, path=""):
                if isinstance(obj, dict):
                    if "_id" in obj and len(str(obj["_id"])) == 24:
                        name = obj.get("name", obj.get("title", ""))
                        if any(k in obj for k in ["startTime", "stages", "bracketType", "teamCount", "matchCount"]):
                            tid = obj["_id"]
                            tournaments[tid] = {
                                "name": name,
                                "startTime": obj.get("startTime", ""),
                                "teamCount": obj.get("teamCount", 0),
                                "slug": obj.get("slug", ""),
                                "status": obj.get("status", ""),
                                "source_url": f"__NEXT_DATA__{path}",
                            }
                            print(f"  FOUND TOURNAMENT at {path}: {name} | {tid}")
                    for k, v in obj.items():
                        walk(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        walk(item, f"{path}[{i}]")

            walk(next_data)
        else:
            print("  No __NEXT_DATA__ found")

        # === Step 3: ページ内のリンクを直接クリックしてサブページを探索 ===
        print("\n--- Step 3: Click navigation links ---")

        # ページ内の全クリック可能要素を調べる
        clickable = page.evaluate("""() => {
            const elements = document.querySelectorAll('a, button, [role="button"], [role="link"], [class*="card"], [class*="tournament"], [class*="league"]');
            return Array.from(elements).map(el => ({
                tag: el.tagName,
                href: el.href || '',
                text: el.textContent.trim().substring(0, 100),
                className: el.className.toString().substring(0, 100),
                id: el.id || '',
            }));
        }""")
        print(f"  Found {len(clickable)} clickable elements")
        for el in clickable:
            text = el.get("text", "").strip()
            href = el.get("href", "")
            cls = el.get("className", "")
            if text and any(kw in text.lower() for kw in ["split", "pro", "challenger", "league", "qualifier", "playoff", "championship", "algs"]):
                print(f"    {el['tag']} | text='{text[:60]}' | href={href[:80]} | class={cls[:60]}")

        # splitやpro leagueのリンクをクリック
        split_links = [el for el in clickable if any(kw in el.get("text", "").lower() for kw in ["split", "pro league", "challenger"])]
        for link in split_links[:6]:
            href = link.get("href", "")
            text = link.get("text", "")
            if href and "battlefy.com" in href:
                print(f"\n  Clicking link: '{text[:60]}' -> {href[:100]}")
                try:
                    page.goto(href, wait_until="networkidle", timeout=30000)
                    time.sleep(2)

                    # このページの__NEXT_DATA__も確認
                    sub_next = page.evaluate("() => { try { return window.__NEXT_DATA__ } catch(e) { return null } }")
                    if sub_next:
                        walk(sub_next, f"_sub_{text[:20]}")

                    # URLからトーナメントIDを探す
                    current_url = page.url
                    ids_in_url = re.findall(r'/([0-9a-f]{24})', current_url)
                    for tid in ids_in_url:
                        if tid not in tournaments:
                            tournaments[tid] = {"name": text, "source_url": current_url}
                            print(f"    ID from URL: {tid}")

                except Exception as e:
                    print(f"    Error: {e}")

        # === Step 4: 直接API呼び出し（ブラウザコンテキスト内） ===
        print("\n--- Step 4: Direct API calls from browser context ---")

        # Battlefy search APIのパターンを試す
        api_patterns = [
            f"https://search.battlefy.com/tournament/organization/{ORG_ID}/past?page=1&size=100",
            f"https://search.battlefy.com/tournament/organization/{ORG_ID}/upcoming?page=1&size=100",
            f"https://search.battlefy.com/tournament/organization/{ORG_ID}?page=1&size=100",
            f"https://api.battlefy.com/organizations/{ORG_ID}/tournaments?page=1&per_page=100",
            f"https://dtmwra1jsgyb0.cloudfront.net/organizations/{ORG_ID}/tournaments?page=1&per_page=100",
            # slug-based
            f"https://search.battlefy.com/tournament/organization/{ORG_SLUG}/past?page=1&size=100",
            f"https://search.battlefy.com/tournament/organization/{ORG_SLUG}/upcoming?page=1&size=100",
            # Battlefy V2 API
            f"https://api.battlefy.com/v2/organizations/{ORG_ID}/tournaments",
        ]

        for api_url in api_patterns:
            try:
                resp = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{api_url}");
                            const text = await r.text();
                            return {{ status: r.status, body: text.substring(0, 10000), length: text.length }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                status = resp.get("status", "error")
                print(f"  {api_url}")
                print(f"    Status: {status}, Length: {resp.get('length', 0)}")
                if status == 200 and resp.get("body"):
                    try:
                        data = json.loads(resp["body"])
                        if isinstance(data, list) and len(data) > 0:
                            print(f"    Array of {len(data)} items")
                            for item in data[:50]:
                                if isinstance(item, dict) and "_id" in item:
                                    tid = item["_id"]
                                    name = item.get("name", "")
                                    tournaments[tid] = {
                                        "name": name,
                                        "startTime": item.get("startTime", ""),
                                        "teamCount": item.get("teamCount", 0),
                                        "slug": item.get("slug", ""),
                                        "status": item.get("status", ""),
                                        "source_url": api_url,
                                    }
                                    print(f"      {tid} | {name} | teams={item.get('teamCount', 0)} | {item.get('startTime', '')}")
                        elif isinstance(data, dict):
                            print(f"    Object keys: {list(data.keys())[:15]}")
                            # ネストされたtournamentsを探す
                            for k, v in data.items():
                                if isinstance(v, list) and len(v) > 0:
                                    print(f"      {k}: array of {len(v)}")
                                    for item in v[:50]:
                                        if isinstance(item, dict) and "_id" in item:
                                            tid = item["_id"]
                                            name = item.get("name", "")
                                            tournaments[tid] = {
                                                "name": name,
                                                "startTime": item.get("startTime", ""),
                                                "teamCount": item.get("teamCount", 0),
                                                "source_url": api_url,
                                            }
                                            print(f"        {tid} | {name}")
                    except json.JSONDecodeError:
                        print(f"    Not JSON: {resp['body'][:100]}")
            except Exception as e:
                print(f"    Error: {e}")

        # === Step 5: 発見済みIDでチームデータ取得 ===
        print(f"\n--- Step 5: Fetch team data for {len(tournaments)} tournaments ---")

        for i, (tid, info) in enumerate(list(tournaments.items())):
            name = info.get("name", "Unknown")
            if tid in teams_data:
                continue

            # ブラウザfetchでチームデータ取得
            teams_url = f"https://dtmwra1jsgyb0.cloudfront.net/tournaments/{tid}/teams"
            try:
                resp = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{teams_url}");
                            if (!r.ok) return {{ status: r.status }};
                            const data = await r.json();
                            return {{ status: r.status, count: data.length, data: data }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                if resp and resp.get("count", 0) > 0:
                    print(f"  [{i+1}] {tid} | {name} | {resp['count']} teams")
                    teams_data[tid] = resp.get("data", [])
                    for t in resp.get("data", [])[:3]:
                        if isinstance(t, dict):
                            pnames = [pl.get("inGameName", pl.get("username", "?")) for pl in t.get("players", [])[:5]]
                            print(f"      {t.get('name', '?')}: {', '.join(pnames)}")
                else:
                    status = resp.get("status", "?") if resp else "?"
                    # api.battlefyも試す
                    alt_url = f"https://api.battlefy.com/tournaments/{tid}/teams"
                    resp2 = page.evaluate(f"""
                        async () => {{
                            try {{
                                const r = await fetch("{alt_url}");
                                if (!r.ok) return {{ status: r.status }};
                                const data = await r.json();
                                return {{ status: r.status, count: data.length, data: data }};
                            }} catch(e) {{
                                return {{ error: e.message }};
                            }}
                        }}
                    """)
                    if resp2 and resp2.get("count", 0) > 0:
                        print(f"  [{i+1}] {tid} | {name} | {resp2['count']} teams (via api.battlefy)")
                        teams_data[tid] = resp2.get("data", [])
                    elif (i + 1) % 10 == 0:
                        print(f"  [{i+1}] checked... (no teams)")

            except Exception as e:
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}] error: {e}")

        browser.close()

    # === 結果まとめ ===
    print("\n" + "=" * 70)
    print(f"発見トーナメント: {len(tournaments)}")
    print(f"チームデータあり: {len(teams_data)}")
    print("=" * 70)

    results = {}
    for tid, info in sorted(tournaments.items(), key=lambda x: x[1].get("startTime", ""), reverse=True):
        name = info.get("name", "不明")
        teams = info.get("teamCount", 0)
        start = info.get("startTime", "?")
        has_teams = tid in teams_data and len(teams_data.get(tid, [])) > 0
        team_count = len(teams_data.get(tid, []))

        print(f"\n  {tid} | {name}")
        print(f"    Start: {start} | Registered: {teams} | Teams with data: {team_count}")

        # チームデータをシリアライズ可能な形に
        team_list = []
        if has_teams:
            for t in teams_data[tid]:
                if isinstance(t, dict):
                    team_entry = {
                        "name": t.get("name", ""),
                        "players": [
                            {
                                "inGameName": pl.get("inGameName", ""),
                                "username": pl.get("username", ""),
                            }
                            for pl in t.get("players", [])
                            if isinstance(pl, dict)
                        ],
                    }
                    team_list.append(team_entry)
            for t in team_list[:3]:
                pstr = ", ".join(p["inGameName"] or p["username"] for p in t["players"][:5])
                print(f"      Team: {t['name']} | {pstr}")

        results[tid] = {
            **info,
            "has_team_data": has_teams,
            "team_data_count": team_count,
            "teams": team_list,
        }

    # 保存
    output = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "organization_id": ORG_ID,
        "organization_slug": ORG_SLUG,
        "total_tournaments": len(results),
        "tournaments_with_teams": sum(1 for r in results.values() if r.get("has_team_data")),
        "tournaments": results,
        "captured_api_calls": [a["url"] for a in captured_api],
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n結果保存: {OUTPUT_FILE}")
    print(f"合計: {len(results)} tournaments, {sum(1 for r in results.values() if r.get('has_team_data'))} with team data")


if __name__ == "__main__":
    main()
