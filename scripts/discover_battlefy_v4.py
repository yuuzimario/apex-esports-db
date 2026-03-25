"""
Battlefy ALGS Year 6 トーナメントID発見スクリプト v4
majestic.battlefy.com API と d3q4fnxloga6gz.cloudfront.net API を探索
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"

MAJESTIC_BASE = "https://majestic.battlefy.com"
CF_BASE = "https://d3q4fnxloga6gz.cloudfront.net"

# 全傍受APIレスポンス
all_api_calls = []
all_api_data = {}


def on_response(response):
    """全APIレスポンスを傍受し保存"""
    url = response.url
    if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.ico']):
        return
    if any(x in url for x in ['google', 'facebook', 'analytics', 'sentry', 'segment', 'hotjar', 'cookielaw', 'onetrust', 'intercom']):
        return

    try:
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        body = response.text()
        if not body or len(body) < 5:
            return
        data = json.loads(body)
        all_api_calls.append(url)
        all_api_data[url] = data
        print(f"  [API] {url[:150]} ({len(body)} bytes)")
    except Exception:
        pass


def fetch_json(page, url):
    """ブラウザコンテキスト内でfetch"""
    try:
        result = page.evaluate(f"""
            async () => {{
                try {{
                    const r = await fetch("{url}");
                    const text = await r.text();
                    return {{ status: r.status, body: text, length: text.length }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)
        if result and result.get("status") == 200 and result.get("body"):
            return json.loads(result["body"])
        else:
            print(f"    Status: {result.get('status', 'error')}")
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 API Explorer v4")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.on("response", on_response)

        # まずページを開いてCookieを取得
        print("\n--- Loading page to establish session ---")
        page.goto("https://battlefy.com/apex-legends-global-series-year-6", wait_until="networkidle", timeout=45000)
        time.sleep(3)
        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # === Step 1: Majestic API — seasons 全データ取得 ===
        print("\n--- Step 1: Majestic API - Seasons data ---")
        seasons_url = f"{MAJESTIC_BASE}/algs/apex-legends-global-series-year-6/seasons"
        print(f"  Fetching: {seasons_url}")
        seasons_data = fetch_json(page, seasons_url)

        if not seasons_data:
            print("  Failed to fetch seasons data!")
            browser.close()
            return

        # seasonsデータを保存
        with open(CACHE_DIR / "majestic_seasons.json", "w", encoding="utf-8") as f:
            json.dump(seasons_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"  Saved majestic_seasons.json")

        # seasonsデータの構造を解析
        print(f"\n  Top-level keys: {list(seasons_data.keys())}")
        print(f"  Name: {seasons_data.get('name', '')}")
        print(f"  Slug: {seasons_data.get('slug', '')}")
        print(f"  portalSlug: {seasons_data.get('portalSlug', '')}")
        print(f"  isActive: {seasons_data.get('isActive', '')}")

        # eventTypes
        event_types = seasons_data.get("eventTypes", [])
        print(f"\n  Event Types: {len(event_types)}")
        for et in event_types:
            print(f"    - {et.get('name', '')} (id={et.get('_id', '')}, slug={et.get('slug', '')})")
            events = et.get("events", [])
            for ev in events:
                print(f"      Event: {ev.get('name', '')} (id={ev.get('_id', '')}, slug={ev.get('slug', '')})")

        # divisions
        divisions = seasons_data.get("divisions", [])
        print(f"\n  Divisions: {len(divisions)}")
        for div in divisions:
            print(f"    - {div.get('name', '')} (id={div.get('_id', '')}, slug={div.get('slug', '')})")
            regions = div.get("regions", [])
            for reg in regions:
                print(f"      Region: {reg.get('name', '')} (id={reg.get('_id', '')}, slug={reg.get('slug', '')})")

        # leaderboardOnlyEventTypes
        lb_types = seasons_data.get("leaderboardOnlyEventTypes", [])
        print(f"\n  Leaderboard-only Event Types: {len(lb_types)}")
        for lbt in lb_types:
            print(f"    - {lbt.get('name', '')} (id={lbt.get('_id', '')})")
            events = lbt.get("events", [])
            for ev in events:
                print(f"      Event: {ev.get('name', '')} (id={ev.get('_id', '')})")

        # === Step 2: 各リージョンのリーダーボード取得 ===
        print("\n--- Step 2: Leaderboards per region ---")
        season_slug = "algs-season-6"

        # イベントIDの収集
        all_events = []
        for et in event_types:
            for ev in et.get("events", []):
                all_events.append({
                    "event_type": et.get("name", ""),
                    "event_type_slug": et.get("slug", ""),
                    "event_name": ev.get("name", ""),
                    "event_id": ev.get("_id", ""),
                    "event_slug": ev.get("slug", ""),
                })
        for lbt in lb_types:
            for ev in lbt.get("events", []):
                all_events.append({
                    "event_type": lbt.get("name", ""),
                    "event_name": ev.get("name", ""),
                    "event_id": ev.get("_id", ""),
                    "event_slug": ev.get("slug", ""),
                    "leaderboard_only": True,
                })

        print(f"  Total events found: {len(all_events)}")

        # リージョンスラグ
        region_slugs = []
        for div in divisions:
            for reg in div.get("regions", []):
                region_slugs.append(reg.get("slug", ""))

        # 各イベント×リージョンでリーダーボード取得
        leaderboard_results = {}
        qualified_results = {}

        for event in all_events:
            eid = event["event_id"]
            ename = event["event_name"]
            print(f"\n  Event: {ename} (ID: {eid})")

            for region in region_slugs:
                # リーダーボード
                lb_url = f"{CF_BASE}/algs/{season_slug}/team-leaderboards/{eid}?region={region}&offset=0&limit=100"
                print(f"    Leaderboard {region}: ", end="")
                lb_data = fetch_json(page, lb_url)
                if lb_data and lb_data.get("total", 0) > 0:
                    total = lb_data.get("total", 0)
                    teams = lb_data.get("data", [])
                    print(f"{total} teams")
                    key = f"{ename}|{region}"
                    leaderboard_results[key] = {
                        "event": ename,
                        "event_id": eid,
                        "region": region,
                        "total_teams": total,
                        "teams": teams,
                    }
                    for t in teams[:5]:
                        team_name = t.get("teamName", t.get("name", "?"))
                        score = t.get("score", t.get("points", "?"))
                        print(f"      {t.get('rank', '?')}. {team_name} ({score} pts)")
                else:
                    print("no data")

            # qualified-teams（リージョンなし）
            qt_url = f"{CF_BASE}/algs/{season_slug}/qualified-teams/{eid}"
            print(f"    Qualified teams: ", end="")
            qt_data = fetch_json(page, qt_url)
            if qt_data and isinstance(qt_data, list) and len(qt_data) > 0:
                print(f"{len(qt_data)} teams")
                qualified_results[ename] = {
                    "event": ename,
                    "event_id": eid,
                    "teams": qt_data,
                }
                for t in qt_data[:5]:
                    print(f"      {t.get('name', '?')} | placement: {t.get('placement', '?')}")
            else:
                print("no data")

        # === Step 3: トーナメントIDを探すために追加のAPIパターンを試す ===
        print("\n--- Step 3: Find tournament IDs via Majestic API ---")

        # イベント詳細API
        for event in all_events:
            eid = event["event_id"]
            ename = event["event_name"]

            detail_urls = [
                f"{MAJESTIC_BASE}/algs/{season_slug}/events/{eid}",
                f"{CF_BASE}/algs/{season_slug}/events/{eid}",
                f"{CF_BASE}/algs/{season_slug}/event-details/{eid}",
            ]
            for durl in detail_urls:
                print(f"  {durl}")
                ddata = fetch_json(page, durl)
                if ddata:
                    with open(CACHE_DIR / f"event_{eid}.json", "w", encoding="utf-8") as f:
                        json.dump(ddata, f, ensure_ascii=False, indent=2, default=str)
                    print(f"    Saved event_{eid}.json")

                    # トーナメントIDを探す
                    def find_tournament_ids(obj, path=""):
                        found = []
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if "tournament" in k.lower() and isinstance(v, str) and len(v) == 24:
                                    found.append((f"{path}.{k}", v))
                                found.extend(find_tournament_ids(v, f"{path}.{k}"))
                        elif isinstance(obj, list):
                            for i, item in enumerate(obj):
                                found.extend(find_tournament_ids(item, f"{path}[{i}]"))
                        return found

                    tid_refs = find_tournament_ids(ddata)
                    for path, tid in tid_refs:
                        print(f"    Tournament ref at {path}: {tid}")
                    break

        # === Step 4: マッチデータ、チーム詳細等のAPIパターン ===
        print("\n--- Step 4: Additional API patterns ---")
        additional_patterns = [
            f"{CF_BASE}/algs/{season_slug}/teams",
            f"{CF_BASE}/algs/{season_slug}/matches",
            f"{CF_BASE}/algs/{season_slug}/rosters",
            f"{CF_BASE}/algs/{season_slug}/standings",
            f"{MAJESTIC_BASE}/algs/{season_slug}/teams",
            f"{MAJESTIC_BASE}/algs/{season_slug}/rosters",
        ]

        for url in additional_patterns:
            print(f"  {url}: ", end="")
            data = fetch_json(page, url)
            if data:
                if isinstance(data, list):
                    print(f"Array[{len(data)}]")
                    if len(data) > 0 and isinstance(data[0], dict):
                        print(f"    Sample keys: {list(data[0].keys())[:15]}")
                        # 保存
                        fname = url.split("/")[-1].split("?")[0]
                        with open(CACHE_DIR / f"algs_{fname}.json", "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                elif isinstance(data, dict):
                    print(f"Object keys: {list(data.keys())[:15]}")
                    fname = url.split("/")[-1].split("?")[0]
                    with open(CACHE_DIR / f"algs_{fname}.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            else:
                print("no data")

        # === Step 5: 各リージョン × イベント のリーダーボード全チーム取得 ===
        print("\n--- Step 5: Full leaderboard data ---")
        all_team_rosters = {}

        for key, lb in leaderboard_results.items():
            total = lb["total_teams"]
            eid = lb["event_id"]
            region = lb["region"]
            ename = lb["event"]

            if total <= len(lb["teams"]):
                # 既に全チーム取得済み
                all_team_rosters[key] = lb["teams"]
                continue

            # ページネーションで全チーム取得
            all_teams = list(lb["teams"])
            offset = len(all_teams)
            while offset < total:
                url = f"{CF_BASE}/algs/{season_slug}/team-leaderboards/{eid}?region={region}&offset={offset}&limit=100"
                data = fetch_json(page, url)
                if data and data.get("data"):
                    all_teams.extend(data["data"])
                    offset += len(data["data"])
                else:
                    break
            all_team_rosters[key] = all_teams
            print(f"  {key}: {len(all_teams)} teams (total={total})")

        # === Step 6: チーム詳細（ロスター）取得 ===
        print("\n--- Step 6: Team roster details ---")
        team_rosters = {}

        # リーダーボードからチームIDを収集
        team_ids = set()
        for key, teams in all_team_rosters.items():
            for t in teams:
                tid = t.get("teamID", t.get("id", t.get("_id", "")))
                if tid:
                    team_ids.add(tid)

        print(f"  Unique team IDs: {len(team_ids)}")

        # チーム詳細APIを探す
        sample_teams = list(team_ids)[:3]
        for tid in sample_teams:
            patterns = [
                f"{CF_BASE}/algs/{season_slug}/teams/{tid}",
                f"{CF_BASE}/algs/{season_slug}/team-details/{tid}",
                f"{MAJESTIC_BASE}/algs/{season_slug}/teams/{tid}",
                f"{CF_BASE}/algs/{season_slug}/rosters/{tid}",
                f"{CF_BASE}/algs/{season_slug}/lineups/{tid}",
            ]
            for url in patterns:
                print(f"  {url}: ", end="")
                data = fetch_json(page, url)
                if data:
                    if isinstance(data, list):
                        print(f"Array[{len(data)}]")
                    elif isinstance(data, dict):
                        print(f"keys: {list(data.keys())[:15]}")
                    with open(CACHE_DIR / f"team_sample_{tid[:8]}.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                    break
                else:
                    print("no data")

        # リーダーボードのチームデータ内にロスター情報があるか確認
        print("\n  Checking leaderboard team data structure...")
        for key, teams in list(all_team_rosters.items())[:1]:
            if teams:
                sample = teams[0]
                print(f"  Sample team keys: {list(sample.keys())}")
                # メンバー情報を探す
                for k, v in sample.items():
                    if isinstance(v, list) and len(v) > 0:
                        print(f"    {k}: list[{len(v)}]")
                        if isinstance(v[0], dict):
                            print(f"      sample: {list(v[0].keys())[:10]}")
                    elif isinstance(v, dict):
                        print(f"    {k}: {list(v.keys())[:10]}")

        # === Step 7: マッチ/スケジュールAPI ===
        print("\n--- Step 7: Matches/Schedule API ---")
        for event in all_events[:3]:
            eid = event["event_id"]
            ename = event["event_name"]
            for region in region_slugs:
                match_urls = [
                    f"{CF_BASE}/algs/{season_slug}/matches/{eid}?region={region}",
                    f"{CF_BASE}/algs/{season_slug}/schedule/{eid}?region={region}",
                    f"{CF_BASE}/algs/{season_slug}/results/{eid}?region={region}",
                ]
                for murl in match_urls:
                    data = fetch_json(page, murl)
                    if data:
                        if isinstance(data, list) and len(data) > 0:
                            print(f"  {murl.split('/')[-1].split('?')[0]} {ename}|{region}: {len(data)} items")
                            fname = f"matches_{eid}_{region}.json"
                            with open(CACHE_DIR / fname, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                        elif isinstance(data, dict) and data:
                            print(f"  {murl.split('/')[-1].split('?')[0]} {ename}|{region}: {list(data.keys())[:10]}")
                        break

        # === Step 8: ナビゲーションリンクをクリックしてAPIコール傍受 ===
        print("\n--- Step 8: Navigate to sub-pages ---")
        sub_pages = [
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league",
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-challenger-circuit",
        ]
        # divisionsとevent_typesからURLを構築
        for et in event_types:
            slug = et.get("slug", "")
            if slug:
                sub_pages.append(f"https://battlefy.com/apex-legends-global-series-year-6/{slug}")

        for sub_url in sub_pages:
            print(f"\n  Visiting: {sub_url}")
            try:
                page.goto(sub_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # ページ内テキスト
                body_text = page.inner_text("body")
                relevant_lines = [l.strip() for l in body_text.split("\n")
                                  if l.strip() and any(kw in l.lower() for kw in
                                                       ["tournament", "qualifier", "week", "day", "match", "round", "americas", "emea", "apac"])]
                for line in relevant_lines[:10]:
                    print(f"    {line[:100]}")
            except Exception as e:
                print(f"    Error: {e}")

        browser.close()

    # === 最終結果 ===
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    print(f"\nAPI Calls intercepted: {len(all_api_calls)}")
    for url in all_api_calls:
        print(f"  {url[:150]}")

    print(f"\nLeaderboard data: {len(leaderboard_results)} region/event combos")
    for key, lb in leaderboard_results.items():
        print(f"  {key}: {lb['total_teams']} teams")

    print(f"\nQualified teams: {len(qualified_results)} events")
    for key, qt in qualified_results.items():
        print(f"  {key}: {len(qt['teams'])} teams")

    # 保存
    output = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "api_base": {
            "majestic": MAJESTIC_BASE,
            "cloudfront": CF_BASE,
            "season_slug": "algs-season-6",
        },
        "organization": {
            "name": seasons_data.get("name", ""),
            "slug": seasons_data.get("slug", ""),
            "portalSlug": seasons_data.get("portalSlug", ""),
        },
        "event_types": [
            {
                "name": et.get("name", ""),
                "slug": et.get("slug", ""),
                "id": et.get("_id", ""),
                "events": [
                    {"name": ev.get("name", ""), "id": ev.get("_id", ""), "slug": ev.get("slug", "")}
                    for ev in et.get("events", [])
                ],
            }
            for et in event_types
        ],
        "leaderboard_only_event_types": [
            {
                "name": lbt.get("name", ""),
                "id": lbt.get("_id", ""),
                "events": [
                    {"name": ev.get("name", ""), "id": ev.get("_id", "")}
                    for ev in lbt.get("events", [])
                ],
            }
            for lbt in lb_types
        ],
        "divisions": [
            {
                "name": div.get("name", ""),
                "id": div.get("_id", ""),
                "slug": div.get("slug", ""),
                "regions": [
                    {"name": reg.get("name", ""), "id": reg.get("_id", ""), "slug": reg.get("slug", "")}
                    for reg in div.get("regions", [])
                ],
            }
            for div in divisions
        ],
        "leaderboards": {
            key: {
                "event": lb["event"],
                "event_id": lb["event_id"],
                "region": lb["region"],
                "total_teams": lb["total_teams"],
                "teams": all_team_rosters.get(key, lb["teams"]),
            }
            for key, lb in leaderboard_results.items()
        },
        "qualified_teams": {
            key: {
                "event": qt["event"],
                "event_id": qt["event_id"],
                "teams": qt["teams"],
            }
            for key, qt in qualified_results.items()
        },
        "all_api_calls": all_api_calls,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nSaved to: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
