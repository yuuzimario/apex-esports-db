"""
Battlefy ALGS Year 6 — 最終版v2
2段階: Playwright で majestic API からデータ取得 → httpx で CloudFront APIを叩く
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"

MAJESTIC_BASE = "https://majestic.battlefy.com"
CF_BASE = "https://d3q4fnxloga6gz.cloudfront.net"
CF_OLD = "https://dtmwra1jsgyb0.cloudfront.net"
SEASON_SLUG = "algs-season-6"

REGIONS = ["americas", "asia-pacific-north", "asia-pacific-south", "europe-middle-east-and-africa"]
REGION_SHORT = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Origin": "https://battlefy.com",
    "Referer": "https://battlefy.com/",
    "Accept": "application/json, text/plain, */*",
}


def httpx_get(client, url):
    """httpxでGETリクエスト"""
    try:
        resp = client.get(url, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"    [{resp.status_code}] {url[:100]}")
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 — Final Discovery v2")
    print("=" * 70)

    # === Phase 1: Playwright でMajestic APIからシーズンデータ取得 ===
    print("\n=== Phase 1: Playwright — Majestic API ===")
    seasons = None
    captured_leaderboards = {}
    captured_qualified = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        # APIレスポンス傍受
        def on_response(response):
            url = response.url
            try:
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                if "team-leaderboards" in url:
                    body = response.text()
                    data = json.loads(body)
                    captured_leaderboards[url] = data
                    print(f"  [CAPTURED] leaderboard: {url[:100]} ({len(body)} bytes)")
                elif "qualified-teams" in url:
                    body = response.text()
                    data = json.loads(body)
                    captured_qualified[url] = data
                    print(f"  [CAPTURED] qualified: {url[:100]} ({len(body)} bytes)")
            except Exception:
                pass

        page = context.new_page()
        page.on("response", on_response)

        # ページ読み込み（最大3回リトライ）
        print("  Loading battlefy.com...")
        for attempt in range(3):
            try:
                page.goto("https://battlefy.com/apex-legends-global-series-year-6",
                          wait_until="networkidle", timeout=60000)
                print(f"  Page loaded (attempt {attempt + 1})")
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} timeout, retrying...")
                if attempt == 2:
                    try:
                        page.goto("https://battlefy.com/apex-legends-global-series-year-6",
                                  wait_until="load", timeout=60000)
                        time.sleep(10)
                        print("  Page loaded via 'load' event + wait")
                    except Exception:
                        print("  WARNING: Page failed to load properly")
        time.sleep(3)

        # Cookie拒否
        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # Majestic API fetch (ブラウザコンテキスト内)
        print("\n  Fetching seasons data from Majestic API...")
        seasons_url = f"{MAJESTIC_BASE}/algs/apex-legends-global-series-year-6/seasons"
        try:
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
            """, seasons_url)
            if result and result.get("status") == 200:
                seasons = json.loads(result["body"])
                print(f"  Seasons data: {len(result['body'])} bytes")
            else:
                print(f"  Seasons fetch failed: {result}")
        except Exception as e:
            print(f"  Error: {e}")

        # イベント詳細もMajestic APIから取得
        event_details = {}
        if seasons:
            for et in seasons.get("eventTypes", []):
                for ev in et.get("events", []):
                    eid = ev.get("_id", "")
                    ename = ev.get("name", "")
                    detail_url = f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{eid}"
                    try:
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
                        """, detail_url)
                        if result and result.get("status") == 200:
                            event_details[eid] = json.loads(result["body"])
                            print(f"  Event detail: {ename}")
                    except Exception:
                        pass

        # リージョンページも訪問してリーダーボード等のAPIキャプチャ
        region_pages = [
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/americas",
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/asia-pacific-north",
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/asia-pacific-south",
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/europe-middle-east-and-africa",
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league/americas",
        ]

        for rpage_url in region_pages:
            print(f"\n  Visiting: {rpage_url}")
            try:
                page.goto(rpage_url, wait_until="networkidle", timeout=45000)
                time.sleep(3)
                # スクロールしてデータ読み込み
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 500)")
                    time.sleep(0.5)
            except Exception as e:
                print(f"    Timeout (trying load event)...")
                try:
                    page.goto(rpage_url, wait_until="load", timeout=30000)
                    time.sleep(5)
                except Exception:
                    pass

        browser.close()

    if not seasons:
        print("FATAL: シーズンデータが取得できませんでした")
        # キャッシュから読み込み
        cached = CACHE_DIR / "majestic_seasons.json"
        if cached.exists():
            print("  キャッシュから読み込み...")
            with open(cached, "r", encoding="utf-8") as f:
                seasons = json.load(f)
        else:
            return

    # === Phase 2: データ解析 ===
    print("\n=== Phase 2: データ解析 ===")
    event_types = seasons.get("eventTypes", [])
    lb_types = seasons.get("leaderboardOnlyEventTypes", [])

    all_events = []
    structure_ids = {}

    for et in event_types:
        et_name = et.get("name", "")
        lb_season_id = et.get("leaderboardSeasonID", "")
        for ev in et.get("events", []):
            ev_info = {
                "event_type": et_name,
                "event_name": ev.get("name", ""),
                "event_id": ev.get("_id", ""),
                "event_slug": ev.get("slug", ""),
                "leaderboard_season_id": lb_season_id,
                "regional_events": {},
            }
            regional = ev.get("regionalEvents", {})
            for region, rdata in regional.items():
                sid = rdata.get("structureID", "")
                ev_info["regional_events"][region] = {
                    "structureID": sid,
                    "tournamentSlug": rdata.get("tournamentSlug", ""),
                    "startTime": rdata.get("tournamentStartTime", ""),
                    "completedAt": rdata.get("completedAt", ""),
                }
                if sid:
                    structure_ids[sid] = {
                        "event": ev.get("name", ""),
                        "region": region,
                        "region_short": REGION_SHORT.get(region, region),
                    }
            all_events.append(ev_info)

    print(f"  イベント数: {len(all_events)}")
    print(f"  StructureID数: {len(structure_ids)}")
    for ev in all_events:
        print(f"    {ev['event_type']} > {ev['event_name']} (LB ID: {ev['leaderboard_season_id'] or 'N/A'})")
        for region, rdata in ev["regional_events"].items():
            sid = rdata["structureID"]
            status = "completed" if rdata.get("completedAt") else "upcoming"
            print(f"      {REGION_SHORT.get(region, region)}: {sid or 'N/A'} [{status}]")

    # === Phase 3: httpx で CloudFront API を叩く ===
    print("\n=== Phase 3: httpx — CloudFront API ===")

    leaderboard_data = {}
    qualified_data = {}
    team_rosters = {}

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        # リーダーボード取得
        print("\n--- リーダーボード ---")
        for et in event_types:
            lb_id = et.get("leaderboardSeasonID", "")
            if not lb_id:
                continue
            et_name = et.get("name", "")
            for region in REGIONS:
                rs = REGION_SHORT[region]
                url = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_id}?region={region}&offset=0&limit=200"
                print(f"  {et_name}|{rs}: ", end="")
                data = httpx_get(client, url)
                if data and data.get("total", 0) > 0:
                    total = data["total"]
                    teams = data.get("data", [])
                    key = f"{et_name}|{rs}"
                    leaderboard_data[key] = {"total": total, "teams": teams, "lb_id": lb_id, "region": region}
                    print(f"{total} teams")
                    for t in teams[:3]:
                        name = t.get("teamName", t.get("name", "?"))
                        score = t.get("score", "?")
                        print(f"    {t.get('rank', '?')}. {name} ({score} pts)")
                    # ページネーション
                    while len(teams) < total:
                        offset = len(teams)
                        url2 = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_id}?region={region}&offset={offset}&limit=200"
                        data2 = httpx_get(client, url2)
                        if data2 and data2.get("data"):
                            teams.extend(data2["data"])
                        else:
                            break
                    leaderboard_data[key]["teams"] = teams
                else:
                    print("no data")

        # Qualified teams取得
        print("\n--- Qualified teams ---")
        for ev in all_events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            url = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{eid}"
            data = httpx_get(client, url)
            if data and isinstance(data, list) and len(data) > 0:
                qualified_data[ename] = data
                print(f"  {ename}: {len(data)} teams")
                for t in data[:3]:
                    print(f"    {t.get('name', '?')} | placement: {t.get('placement', '?')}")

        # StructureID からチームデータ取得
        print("\n--- StructureID → チームデータ ---")
        for sid, info in structure_ids.items():
            event = info["event"]
            rs = info["region_short"]
            key = f"{event}|{rs}"

            url = f"{CF_OLD}/tournaments/{sid}/teams"
            print(f"  {key}: ", end="")
            data = httpx_get(client, url)
            if data and isinstance(data, list) and len(data) > 0:
                print(f"{len(data)} teams!")
                teams_list = []
                for t in data:
                    if isinstance(t, dict):
                        players = []
                        for pl in t.get("players", []):
                            if isinstance(pl, dict):
                                players.append({
                                    "inGameName": pl.get("inGameName", ""),
                                    "username": pl.get("username", ""),
                                    "persistentPlayerID": pl.get("persistentPlayerID", ""),
                                    "ownerID": pl.get("ownerID", ""),
                                })
                        teams_list.append({
                            "name": t.get("name", ""),
                            "teamID": t.get("_id", ""),
                            "persistentTeamID": t.get("persistentTeamID", ""),
                            "players": players,
                            "customFields": t.get("customFields", []),
                        })
                team_rosters[key] = {
                    "structureID": sid,
                    "event": event,
                    "region": info["region"],
                    "region_short": rs,
                    "team_count": len(teams_list),
                    "teams": teams_list,
                }
                for t in teams_list[:3]:
                    pnames = [p["inGameName"] or p["username"] for p in t["players"][:5]]
                    print(f"    {t['name']}: {', '.join(pnames)}")
            else:
                print("no team data")

        # Lineups API パターン試行
        print("\n--- Lineups/Roster API パターン ---")
        sample_event = all_events[0] if all_events else None
        if sample_event:
            eid = sample_event["event_id"]
            for region in REGIONS[:1]:
                api_patterns = [
                    f"{CF_BASE}/algs/{SEASON_SLUG}/lineups/{eid}?region={region}",
                    f"{CF_BASE}/algs/{SEASON_SLUG}/event-lineups/{eid}?region={region}",
                    f"{CF_BASE}/algs/{SEASON_SLUG}/event-teams/{eid}?region={region}",
                    f"{CF_BASE}/algs/{SEASON_SLUG}/rosters/{eid}?region={region}",
                    f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/lineups/{eid}?region={region}",
                    f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{eid}/lineups?region={region}",
                    f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{eid}/teams?region={region}",
                ]
                for url in api_patterns:
                    data = httpx_get(client, url)
                    if data:
                        if isinstance(data, list) and len(data) > 0:
                            print(f"  HIT: {url.split(SEASON_SLUG)[1]} → {len(data)} items")
                            sample = data[0]
                            if isinstance(sample, dict):
                                print(f"    Keys: {list(sample.keys())[:15]}")
                            with open(CACHE_DIR / f"lineups_sample.json", "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                        elif isinstance(data, dict):
                            print(f"  HIT: {url.split(SEASON_SLUG)[1]} → keys={list(data.keys())[:10]}")

    # キャプチャされたデータも追加
    print("\n--- Playwright キャプチャデータ ---")
    for url, data in captured_leaderboards.items():
        if isinstance(data, dict) and data.get("total", 0) > 0:
            # URLからリージョンを推定
            for r in REGIONS:
                if r in url:
                    rs = REGION_SHORT[r]
                    key = f"captured|{rs}"
                    if key not in leaderboard_data:
                        leaderboard_data[key] = {"total": data["total"], "teams": data.get("data", []), "region": r}
                        print(f"  Captured leaderboard {rs}: {data['total']} teams")
                    break

    for url, data in captured_qualified.items():
        if isinstance(data, list) and len(data) > 0:
            key = f"captured_{url.split('/')[-1]}"
            if key not in qualified_data:
                qualified_data[key] = data
                print(f"  Captured qualified: {len(data)} teams")

    # === 最終結果 ===
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"\nイベント: {len(all_events)}")
    for ev in all_events:
        print(f"  {ev['event_type']} > {ev['event_name']}")

    print(f"\nStructureIDs: {len(structure_ids)}")
    for sid, info in structure_ids.items():
        print(f"  {sid} | {info['event']} | {info['region_short']}")

    print(f"\nリーダーボード: {len(leaderboard_data)} datasets")
    for key, lb in leaderboard_data.items():
        print(f"  {key}: {lb['total']} teams")

    print(f"\nQualified teams: {len(qualified_data)} events")
    for key, qt in qualified_data.items():
        print(f"  {key}: {len(qt)} teams")

    print(f"\nチームロスター (structureIDs): {len(team_rosters)} combos")
    total_teams = 0
    for key, data in team_rosters.items():
        count = data["team_count"]
        total_teams += count
        print(f"  {key}: {count} teams")
    print(f"  合計: {total_teams} teams with roster data")

    # JSON保存
    output = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "api_endpoints": {
            "majestic_seasons": f"{MAJESTIC_BASE}/algs/apex-legends-global-series-year-6/seasons",
            "cloudfront_leaderboard": f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{{leaderboardSeasonID}}?region={{region}}&offset=0&limit=200",
            "cloudfront_qualified": f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{{eventID}}",
            "cloudfront_old_teams": f"{CF_OLD}/tournaments/{{structureID}}/teams",
            "majestic_event_detail": f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{{eventID}}",
        },
        "season": {
            "name": seasons.get("name", ""),
            "slug": seasons.get("slug", ""),
            "id": seasons.get("_id", ""),
        },
        "regions": REGIONS,
        "events": all_events,
        "structure_ids": structure_ids,
        "event_details": {eid: d for eid, d in event_details.items()},
        "leaderboards": leaderboard_data,
        "qualified_teams": qualified_data,
        "team_rosters_from_structures": team_rosters,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    # seasonsデータも保存
    with open(CACHE_DIR / "majestic_seasons.json", "w", encoding="utf-8") as f:
        json.dump(seasons, f, ensure_ascii=False, indent=2, default=str)

    file_size = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n保存完了: {OUTPUT_FILE} ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
