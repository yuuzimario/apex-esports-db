"""
Battlefy ALGS Year 6 トーナメントID発見スクリプト v2
Playwrightでネットワークレスポンスを完全傍受し、Battlefyの実際のAPIデータを収集
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# 結果保存先
CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"

# 全傍受レスポンスを保存
all_api_responses = []
# トーナメントデータ
tournaments = {}
# チームデータ
teams_data = {}


def on_response(response):
    """全てのAPIレスポンスを傍受"""
    url = response.url
    status = response.status

    # API呼び出しのみキャプチャ（静的アセット除外）
    skip_exts = ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ico', '.gif', '.webp']
    if any(url.endswith(ext) for ext in skip_exts):
        return
    if any(x in url for x in ['google', 'facebook', 'analytics', 'sentry', 'segment', 'hotjar',
                                'cookielaw', 'onetrust', 'cdn.', 'fonts.', 'ads.', 'doubleclick']):
        return

    try:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and "text" not in content_type:
            return

        body = response.text()
        if not body or len(body) < 10:
            return

        # JSON解析を試みる
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return

        entry = {
            "url": url,
            "status": status,
            "data_type": type(data).__name__,
            "data_length": len(data) if isinstance(data, (list, dict)) else 0,
        }

        # トーナメントデータを検出
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "_id" in item:
                    _id = item["_id"]
                    name = item.get("name", "")
                    # トーナメントっぽいか？
                    if any(k in item for k in ["startTime", "teamCount", "stages", "bracketType", "gameName"]):
                        tournaments[_id] = {
                            "name": name,
                            "startTime": item.get("startTime", ""),
                            "endTime": item.get("endTime", ""),
                            "status": item.get("status", ""),
                            "teamCount": item.get("teamCount", 0),
                            "checkInRequired": item.get("checkInRequired", False),
                            "gameName": item.get("gameName", item.get("game", {}).get("name", "") if isinstance(item.get("game"), dict) else ""),
                            "region": item.get("region", ""),
                            "slug": item.get("slug", ""),
                            "organizationID": item.get("organizationID", ""),
                            "source_url": url,
                            "customFields": [f.get("name", "") for f in item.get("customFields", []) if isinstance(f, dict)],
                        }
                        print(f"  [TOURNAMENT] {name} | {_id} | teams={item.get('teamCount', 0)} | {item.get('startTime', '')}")

                    # チームデータっぽいか？
                    if "players" in item and isinstance(item.get("players"), list):
                        team_name = item.get("name", item.get("teamName", ""))
                        tournament_id = item.get("tournamentID", "")
                        players = []
                        for p in item.get("players", []):
                            if isinstance(p, dict):
                                players.append({
                                    "inGameName": p.get("inGameName", ""),
                                    "username": p.get("username", ""),
                                })
                        if tournament_id not in teams_data:
                            teams_data[tournament_id] = []
                        teams_data[tournament_id].append({
                            "name": team_name,
                            "players": players,
                            "_id": _id,
                        })

        elif isinstance(data, dict):
            if "_id" in data and any(k in data for k in ["startTime", "teamCount", "stages"]):
                _id = data["_id"]
                tournaments[_id] = {
                    "name": data.get("name", ""),
                    "startTime": data.get("startTime", ""),
                    "status": data.get("status", ""),
                    "teamCount": data.get("teamCount", 0),
                    "gameName": data.get("gameName", ""),
                    "source_url": url,
                }
                print(f"  [TOURNAMENT] {data.get('name', '')} | {_id}")

            # 組織データ
            if "_id" in data and "slug" in data and "name" in data:
                entry["org_name"] = data.get("name", "")
                entry["org_id"] = data["_id"]
                entry["org_slug"] = data.get("slug", "")
                print(f"  [ORG] {data.get('name', '')} | {data['_id']} | slug={data.get('slug', '')}")

        all_api_responses.append(entry)

    except Exception as e:
        pass


def extract_ids_and_links(page) -> dict:
    """ページ内のリンクからトーナメントIDとURLを抽出"""
    results = {}
    try:
        links = page.eval_on_selector_all(
            "a[href*='tournament'], a[href*='/'], a[href*='battlefy']",
            """els => els.map(e => ({
                href: e.href,
                text: e.textContent.trim().substring(0, 200)
            }))"""
        )
        for link in links:
            href = link.get("href", "")
            text = link.get("text", "")
            # トーナメントIDパターン
            ids = re.findall(r'/([0-9a-f]{24})(?:/|$)', href)
            for tid in ids:
                if tid not in results:
                    results[tid] = {"href": href, "text": text}
    except Exception:
        pass
    return results


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 トーナメントID発見スクリプト v2")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("response", on_response)

        # === ステップ1: 組織ページ ===
        print("\n--- Step 1: Organization page ---")
        org_url = "https://battlefy.com/apex-legends-global-series-year-6"
        print(f"Visiting: {org_url}")
        try:
            page.goto(org_url, wait_until="networkidle", timeout=45000)
            time.sleep(3)

            # Cookie同意を処理
            try:
                reject_btn = page.locator("button:has-text('Reject All')")
                if reject_btn.count() > 0:
                    reject_btn.first.click()
                    time.sleep(1)
            except Exception:
                pass

            # ページ内容をスクリーンショットで確認
            page.screenshot(path=str(CACHE_DIR / "battlefy_org_page.png"))
            print("  Screenshot saved")

            # ページ内のテキストを確認
            page_text = page.inner_text("body")
            print(f"  Page text length: {len(page_text)}")
            # ALGSに関連するテキストを探す
            for line in page_text.split("\n"):
                line = line.strip()
                if line and any(kw in line.lower() for kw in ["algs", "split", "qualifier", "championship", "playoff", "regional"]):
                    print(f"    Text: {line[:120]}")

            # リンク抽出
            page_links = extract_ids_and_links(page)
            print(f"  Links with IDs: {len(page_links)}")
            for tid, info in page_links.items():
                print(f"    {tid}: {info['text'][:80]} | {info['href'][:100]}")

            # スクロール&「もっと見る」
            for i in range(10):
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.5)

            # Show moreボタン
            try:
                show_more = page.locator("button:has-text('Show more'), button:has-text('Load more'), button:has-text('もっと見る')")
                while show_more.count() > 0 and show_more.first.is_visible():
                    print("  Clicking 'Show more'...")
                    show_more.first.click()
                    time.sleep(2)
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(1)
            except Exception as e:
                print(f"  Show more error: {e}")

            # スクロール後に再度リンク抽出
            page_links_after = extract_ids_and_links(page)
            new_links = {k: v for k, v in page_links_after.items() if k not in page_links}
            if new_links:
                print(f"  New links after scroll: {len(new_links)}")
                for tid, info in new_links.items():
                    print(f"    {tid}: {info['text'][:80]}")

        except Exception as e:
            print(f"  Error: {e}")

        # === ステップ2: 個別トーナメントページを訪問（チームデータ取得） ===
        print("\n--- Step 2: Visit individual tournament pages ---")

        # 発見済みトーナメントIDリストを作成
        discovered_tournament_ids = list(tournaments.keys())
        # ページリンクからも追加
        for tid in list(page_links.get(tid, {}) for tid in page_links):
            pass
        all_ids = list(set(list(tournaments.keys()) + list(page_links.keys()) + list(page_links_after.keys() if 'page_links_after' in dir() else [])))

        print(f"  Total discovered IDs to check: {len(all_ids)}")

        # 各トーナメントのteamsページを訪問（最大30個）
        for i, tid in enumerate(all_ids[:30]):
            # トーナメント名があればスラグを使う
            t_info = tournaments.get(tid, {})
            slug = t_info.get("slug", "")
            org_slug = "apex-legends-global-series-year-6"

            # まずCloudFront API をブラウザコンテキストで試す（cookies付き）
            teams_url = f"https://dtmwra1jsgyb0.cloudfront.net/tournaments/{tid}/teams"
            try:
                resp = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{teams_url}");
                            if (r.ok) {{
                                const data = await r.json();
                                return {{ status: r.status, count: data.length, data: data.slice(0, 5) }};
                            }}
                            return {{ status: r.status, count: 0, data: [] }};
                        }} catch(e) {{
                            return {{ status: 0, error: e.message }};
                        }}
                    }}
                """)
                if resp and resp.get("count", 0) > 0:
                    team_count = resp["count"]
                    name = t_info.get("name", "Unknown")
                    print(f"  [{i+1}] {tid} | {name} | {team_count} teams via browser fetch!")
                    teams_data[tid] = []
                    for t in resp.get("data", []):
                        if isinstance(t, dict):
                            teams_data[tid].append({
                                "name": t.get("name", ""),
                                "players": [
                                    {"inGameName": pl.get("inGameName", ""), "username": pl.get("username", "")}
                                    for pl in t.get("players", [])
                                ] if isinstance(t.get("players"), list) else [],
                                "_id": t.get("_id", ""),
                            })
                    # 残りも取得
                    if team_count > 5:
                        resp_full = page.evaluate(f"""
                            async () => {{
                                try {{
                                    const r = await fetch("{teams_url}");
                                    if (r.ok) {{ const data = await r.json(); return data; }}
                                    return [];
                                }} catch(e) {{ return []; }}
                            }}
                        """)
                        if isinstance(resp_full, list):
                            teams_data[tid] = []
                            for t in resp_full:
                                if isinstance(t, dict):
                                    teams_data[tid].append({
                                        "name": t.get("name", ""),
                                        "players": [
                                            {"inGameName": pl.get("inGameName", ""), "username": pl.get("username", "")}
                                            for pl in t.get("players", [])
                                        ] if isinstance(t.get("players"), list) else [],
                                        "_id": t.get("_id", ""),
                                    })
                            print(f"    Full team data: {len(teams_data[tid])} teams")
                    continue
                elif resp and resp.get("status") == 403:
                    pass  # 403 — CloudFront blocked
            except Exception as e:
                pass

            # CloudFrontがダメならBattlefy APIを直接ブラウザfetchで試す
            api_urls = [
                f"https://api.battlefy.com/tournaments/{tid}/teams",
                f"https://search.battlefy.com/tournament/organization/{tid}/past",
            ]
            for api_url in api_urls:
                try:
                    resp2 = page.evaluate(f"""
                        async () => {{
                            try {{
                                const r = await fetch("{api_url}");
                                if (r.ok) {{
                                    const data = await r.json();
                                    return {{ status: r.status, count: Array.isArray(data) ? data.length : 0, sample: JSON.stringify(data).substring(0, 500) }};
                                }}
                                return {{ status: r.status }};
                            }} catch(e) {{
                                return {{ error: e.message }};
                            }}
                        }}
                    """)
                    if resp2 and resp2.get("count", 0) > 0:
                        print(f"  [{i+1}] {tid} | API hit: {api_url} | count={resp2['count']}")
                        break
                except Exception:
                    pass

            if (i + 1) % 10 == 0:
                print(f"  ... checked {i+1}/{min(len(all_ids), 30)}")

        # === ステップ3: トーナメントページに直接アクセスして組織の全トーナメントを取得 ===
        print("\n--- Step 3: Fetch tournament listings via search API ---")

        # Battlefyの検索APIを使う
        search_apis = [
            "https://search.battlefy.com/tournament/organization/apex-legends-global-series-year-6?page=1&size=50",
            "https://search.battlefy.com/tournament/organization/apex-legends-global-series-year-6/past?page=1&size=50",
            "https://search.battlefy.com/tournament/organization/apex-legends-global-series-year-6/upcoming?page=1&size=50",
        ]

        for search_url in search_apis:
            try:
                resp3 = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{search_url}");
                            const text = await r.text();
                            return {{ status: r.status, body: text.substring(0, 5000) }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                print(f"  {search_url}")
                print(f"    Status: {resp3.get('status', 'error')}")
                if resp3.get("body"):
                    try:
                        data = json.loads(resp3["body"])
                        if isinstance(data, list):
                            print(f"    Found {len(data)} items")
                            for item in data:
                                if isinstance(item, dict) and "_id" in item:
                                    tid = item["_id"]
                                    name = item.get("name", "")
                                    tournaments[tid] = {
                                        "name": name,
                                        "startTime": item.get("startTime", ""),
                                        "teamCount": item.get("teamCount", 0),
                                        "status": item.get("status", ""),
                                        "source_url": search_url,
                                    }
                                    print(f"      {tid} | {name}")
                        elif isinstance(data, dict) and "tournaments" in data:
                            for item in data["tournaments"]:
                                tid = item.get("_id", "")
                                name = item.get("name", "")
                                if tid:
                                    tournaments[tid] = {
                                        "name": name,
                                        "startTime": item.get("startTime", ""),
                                        "teamCount": item.get("teamCount", 0),
                                        "source_url": search_url,
                                    }
                                    print(f"      {tid} | {name}")
                    except json.JSONDecodeError:
                        print(f"    Body (not JSON): {resp3['body'][:200]}")
            except Exception as e:
                print(f"    Error: {e}")

        # === ステップ4: GraphQL APIがあるか確認 ===
        print("\n--- Step 4: Check for GraphQL API ---")
        graphql_urls = [
            "https://api.battlefy.com/graphql",
            "https://battlefy.com/graphql",
        ]
        for gql_url in graphql_urls:
            try:
                query = '{"query":"{ organization(slug:\\"apex-legends-global-series-year-6\\") { _id name tournaments { _id name startTime teamCount } } }"}'
                resp4 = page.evaluate(f"""
                    async () => {{
                        try {{
                            const r = await fetch("{gql_url}", {{
                                method: "POST",
                                headers: {{ "Content-Type": "application/json" }},
                                body: '{query}'
                            }});
                            const text = await r.text();
                            return {{ status: r.status, body: text.substring(0, 2000) }};
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                print(f"  {gql_url}: status={resp4.get('status', 'error')}")
                if resp4.get("body"):
                    print(f"    Body: {resp4['body'][:300]}")
            except Exception as e:
                print(f"  Error: {e}")

        # === ステップ5: __NEXT_DATA__ と初期State取得 ===
        print("\n--- Step 5: Extract __NEXT_DATA__ / Initial State ---")
        try:
            page.goto(org_url, wait_until="networkidle", timeout=45000)
            time.sleep(2)

            # __NEXT_DATA__
            next_data = page.evaluate("() => { try { return window.__NEXT_DATA__ } catch(e) { return null } }")
            if next_data:
                print("  Found __NEXT_DATA__!")
                next_data_str = json.dumps(next_data, default=str)
                # トーナメントIDを抽出
                ids = re.findall(r'[0-9a-f]{24}', next_data_str)
                print(f"  IDs in __NEXT_DATA__: {len(set(ids))}")

                # pagePropsからデータを取り出す
                page_props = next_data.get("props", {}).get("pageProps", {})
                if page_props:
                    print(f"  pageProps keys: {list(page_props.keys())[:20]}")
                    # トーナメントリストを探す
                    for key in page_props:
                        val = page_props[key]
                        if isinstance(val, list) and len(val) > 0:
                            print(f"    {key}: list of {len(val)} items")
                            if isinstance(val[0], dict) and "_id" in val[0]:
                                for item in val:
                                    tid = item.get("_id", "")
                                    name = item.get("name", "")
                                    if tid:
                                        tournaments[tid] = {
                                            "name": name,
                                            "startTime": item.get("startTime", ""),
                                            "teamCount": item.get("teamCount", 0),
                                            "source_url": "__NEXT_DATA__",
                                        }
                                        print(f"      {tid} | {name}")
                        elif isinstance(val, dict):
                            if "_id" in val:
                                print(f"    {key}: object with _id={val['_id']}, name={val.get('name', '')}")

                # dehydratedState（React Queryキャッシュ）も確認
                dehydrated = next_data.get("props", {}).get("pageProps", {}).get("dehydratedState", {})
                if dehydrated:
                    queries = dehydrated.get("queries", [])
                    print(f"  dehydratedState queries: {len(queries)}")
                    for q in queries:
                        qkey = q.get("queryKey", "")
                        qdata = q.get("state", {}).get("data", q.get("data", None))
                        print(f"    queryKey: {qkey}")
                        if isinstance(qdata, list) and len(qdata) > 0:
                            print(f"    data: list of {len(qdata)}")
                            for item in qdata[:3]:
                                if isinstance(item, dict):
                                    print(f"      sample: {json.dumps(item, default=str)[:200]}")
                        elif isinstance(qdata, dict):
                            print(f"    data keys: {list(qdata.keys())[:10]}")

                # 全JSON保存
                with open(CACHE_DIR / "battlefy_next_data.json", "w", encoding="utf-8") as f:
                    json.dump(next_data, f, ensure_ascii=False, indent=2, default=str)
                print("  Saved __NEXT_DATA__ to battlefy_next_data.json")

            # __INITIAL_STATE__（Redux等）
            initial_state = page.evaluate("() => { try { return window.__INITIAL_STATE__ || window.__APOLLO_STATE__ || window.__RELAY_STORE__ } catch(e) { return null } }")
            if initial_state:
                print("  Found __INITIAL_STATE__!")
                with open(CACHE_DIR / "battlefy_initial_state.json", "w", encoding="utf-8") as f:
                    json.dump(initial_state, f, ensure_ascii=False, indent=2, default=str)

        except Exception as e:
            print(f"  Error: {e}")

        browser.close()

    # === 結果まとめ ===
    print("\n" + "=" * 70)
    print(f"発見したトーナメント: {len(tournaments)}")
    print("=" * 70)

    # 名前でソート
    sorted_tournaments = sorted(tournaments.items(), key=lambda x: x[1].get("startTime", ""), reverse=True)

    algs_tournaments = {}
    for tid, info in sorted_tournaments:
        name = info.get("name", "不明")
        teams = info.get("teamCount", 0)
        start = info.get("startTime", "?")
        has_team_data = tid in teams_data and len(teams_data[tid]) > 0
        team_data_count = len(teams_data.get(tid, []))

        print(f"  {tid} | {name}")
        print(f"    Start: {start} | Registered Teams: {teams} | Team Data: {team_data_count if has_team_data else 'NO'}")

        if has_team_data:
            for t in teams_data[tid][:3]:
                players_str = ", ".join(p.get("inGameName", p.get("username", "?")) for p in t.get("players", [])[:5])
                print(f"      Team: {t['name']} | Players: {players_str}")

        algs_tournaments[tid] = {
            **info,
            "has_team_data": has_team_data,
            "team_data_count": team_data_count,
            "teams": teams_data.get(tid, []),
        }

    # チームデータがある tournaments のサマリー
    with_teams = {k: v for k, v in algs_tournaments.items() if v.get("has_team_data")}
    print(f"\nチームデータあり: {len(with_teams)} / {len(algs_tournaments)} トーナメント")

    # 保存
    output = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_tournaments": len(algs_tournaments),
        "tournaments_with_teams": len(with_teams),
        "tournaments": algs_tournaments,
        "api_responses_captured": len(all_api_responses),
        "api_response_urls": [r["url"] for r in all_api_responses[:100]],
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n結果を保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
