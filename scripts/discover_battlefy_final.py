"""
Battlefy ALGS Year 6 — 最終版トーナメントID発見＆チームデータ取得
majestic.battlefy.com / d3q4fnxloga6gz.cloudfront.net APIを使用
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
CF_OLD = "https://dtmwra1jsgyb0.cloudfront.net"
SEASON_SLUG = "algs-season-6"

# 4リージョン
REGIONS = ["americas", "asia-pacific-north", "asia-pacific-south", "europe-middle-east-and-africa"]
REGION_SHORT = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}


def fetch_json(page, url):
    """ブラウザコンテキスト内でfetch"""
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
        """, url)
        if result and result.get("status") == 200 and result.get("body"):
            return json.loads(result["body"])
        elif result:
            print(f"    [{result.get('status', '?')}] {url[:100]}")
        return None
    except Exception as e:
        print(f"    Error fetching {url[:80]}: {e}")
        return None


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 — 最終版発見スクリプト")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # セッション確立
        print("\n--- セッション確立 ---")
        try:
            page.goto("https://battlefy.com/apex-legends-global-series-year-6", wait_until="networkidle", timeout=60000)
        except Exception:
            print("  networkidle timeout, retrying with domcontentloaded...")
            page.goto("https://battlefy.com/apex-legends-global-series-year-6", wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
        time.sleep(2)
        try:
            page.locator("button:has-text('Reject All')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        # === Step 1: Seasons構造データ取得 ===
        print("\n--- Step 1: Seasons構造データ取得 ---")
        seasons_url = f"{MAJESTIC_BASE}/algs/apex-legends-global-series-year-6/seasons"
        seasons = fetch_json(page, seasons_url)
        if not seasons:
            print("FATAL: seasonsデータ取得失敗")
            browser.close()
            return

        # イベントタイプ解析
        event_types = seasons.get("eventTypes", [])
        lb_types = seasons.get("leaderboardOnlyEventTypes", [])

        # 全イベント＋structureID収集
        all_events = []
        structure_ids = {}  # structureID -> event info

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
            print(f"    {ev['event_type']} > {ev['event_name']} (LB: {ev['leaderboard_season_id']})")
            for region, rdata in ev["regional_events"].items():
                sid = rdata["structureID"]
                status = "completed" if rdata.get("completedAt") else "upcoming"
                print(f"      {REGION_SHORT.get(region, region)}: {sid or 'N/A'} [{status}]")

        # === Step 2: リーダーボード取得（leaderboardSeasonID=177） ===
        print("\n--- Step 2: リーダーボード取得 ---")
        leaderboard_data = {}
        lb_season_id = 177  # Online Opens用

        for region in REGIONS:
            region_short = REGION_SHORT[region]
            url = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_season_id}?region={region}&offset=0&limit=200"
            print(f"  {region_short} リーダーボード: ", end="")
            data = fetch_json(page, url)
            if data and data.get("total", 0) > 0:
                total = data["total"]
                teams = data.get("data", [])
                print(f"{total} teams")
                leaderboard_data[region] = {
                    "total": total,
                    "teams": teams,
                }
                for t in teams[:5]:
                    team_name = t.get("teamName", t.get("name", "?"))
                    score = t.get("score", "?")
                    rank = t.get("rank", "?")
                    print(f"    {rank}. {team_name} ({score} pts)")

                # ページネーション
                if total > len(teams):
                    offset = len(teams)
                    while offset < total:
                        url2 = f"{CF_BASE}/algs/{SEASON_SLUG}/team-leaderboards/{lb_season_id}?region={region}&offset={offset}&limit=200"
                        data2 = fetch_json(page, url2)
                        if data2 and data2.get("data"):
                            teams.extend(data2["data"])
                            offset += len(data2["data"])
                        else:
                            break
                    leaderboard_data[region]["teams"] = teams
                    print(f"    Total fetched: {len(teams)}")
            else:
                print("no data")

        # === Step 3: Qualified teams取得 ===
        print("\n--- Step 3: Qualified teams ---")
        qualified_data = {}
        for ev in all_events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            url = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{eid}"
            data = fetch_json(page, url)
            if data and isinstance(data, list) and len(data) > 0:
                print(f"  {ename}: {len(data)} teams")
                qualified_data[ename] = data
                for t in data[:3]:
                    print(f"    {t.get('name', '?')} | placement: {t.get('placement', '?')}")
            # 数値IDでも試す
            lb_id = ev.get("leaderboard_season_id", "")
            if lb_id and str(lb_id) != str(eid):
                url2 = f"{CF_BASE}/algs/{SEASON_SLUG}/qualified-teams/{lb_id}"
                data2 = fetch_json(page, url2)
                if data2 and isinstance(data2, list) and len(data2) > 0:
                    print(f"  {ename} (lb={lb_id}): {len(data2)} teams")
                    qualified_data[f"{ename}_lb{lb_id}"] = data2

        # === Step 4: StructureID（実際のBattlefy tournament ID）からチームデータ取得 ===
        print("\n--- Step 4: StructureID からチームデータ取得 ---")
        team_rosters = {}

        for sid, info in structure_ids.items():
            event = info["event"]
            region = info["region_short"]
            key = f"{event}|{region}"

            # CloudFront (old) API
            teams_url = f"{CF_OLD}/tournaments/{sid}/teams"
            print(f"  {key}: ", end="")
            data = fetch_json(page, teams_url)
            if data and isinstance(data, list) and len(data) > 0:
                print(f"{len(data)} teams!")
                team_rosters[key] = {
                    "structureID": sid,
                    "event": event,
                    "region": info["region"],
                    "region_short": region,
                    "team_count": len(data),
                    "teams": [],
                }
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
                        team_entry = {
                            "name": t.get("name", ""),
                            "teamID": t.get("_id", ""),
                            "persistentTeamID": t.get("persistentTeamID", ""),
                            "captain": t.get("captain", ""),
                            "players": players,
                            "customFields": t.get("customFields", []),
                        }
                        team_rosters[key]["teams"].append(team_entry)

                # サンプル表示
                for t in team_rosters[key]["teams"][:3]:
                    pnames = [p["inGameName"] or p["username"] for p in t["players"][:5]]
                    print(f"    {t['name']}: {', '.join(pnames)}")
            else:
                print("no team data")

                # 別のAPIパターンも試す
                alt_urls = [
                    f"{CF_OLD}/tournaments/{sid}",
                    f"{CF_OLD}/tournaments/{sid}/participants",
                ]
                for alt in alt_urls:
                    alt_data = fetch_json(page, alt)
                    if alt_data:
                        if isinstance(alt_data, list) and len(alt_data) > 0:
                            print(f"    Alt API hit: {alt.split('/')[-1]} → {len(alt_data)} items")
                            sample = alt_data[0] if isinstance(alt_data[0], dict) else {}
                            print(f"    Sample keys: {list(sample.keys())[:15]}")
                            # 保存
                            fname = f"structure_{sid[:12]}_{alt.split('/')[-1]}.json"
                            with open(CACHE_DIR / fname, "w", encoding="utf-8") as f:
                                json.dump(alt_data, f, ensure_ascii=False, indent=2, default=str)
                        elif isinstance(alt_data, dict):
                            name = alt_data.get("name", "")
                            if name:
                                print(f"    Tournament info: {name}")

        # === Step 5: Pro League ページのAPIを傍受 ===
        print("\n--- Step 5: Pro League ページ探索 ---")
        api_captured = {}

        def capture_api(response):
            url = response.url
            if "cloudfront.net" in url or "majestic.battlefy" in url:
                if url not in api_captured:
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            body = response.text()
                            if body and len(body) > 10:
                                api_captured[url] = json.loads(body)
                                print(f"    [CAPTURED] {url[:120]} ({len(body)} bytes)")
                    except Exception:
                        pass

        page.on("response", capture_api)

        # Pro Leagueの各リージョンページをブラウズ
        pro_league_urls = [
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league/americas",
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league/asia-pacific-north",
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league/asia-pacific-south",
            "https://battlefy.com/apex-legends-global-series-year-6/split-1-pro-league/europe-middle-east-and-africa",
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/americas",
            "https://battlefy.com/apex-legends-global-series-year-6/preseason-qualifiers/asia-pacific-north",
        ]

        for purl in pro_league_urls:
            print(f"\n  Visiting: {purl}")
            try:
                page.goto(purl, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                # スクロールしてデータ読み込み
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 500)")
                    time.sleep(0.5)
            except Exception as e:
                print(f"    Error: {e}")

        # キャプチャしたAPI保存
        print(f"\n  Total captured APIs: {len(api_captured)}")
        for url, data in api_captured.items():
            if isinstance(data, dict):
                print(f"    {url[:120]}: keys={list(data.keys())[:10]}")
            elif isinstance(data, list):
                print(f"    {url[:120]}: Array[{len(data)}]")

        # リーダーボードで捕捉されたデータも保存
        for url, data in api_captured.items():
            if "team-leaderboards" in url or "lineups" in url or "rosters" in url:
                fname = url.split("/")[-1].split("?")[0] + "_captured.json"
                with open(CACHE_DIR / fname, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        # === Step 6: Majestic API でイベント詳細取得（lineup/roster情報含む） ===
        print("\n--- Step 6: Event Details via Majestic API ---")
        event_details = {}
        for ev in all_events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            url = f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{eid}"
            data = fetch_json(page, url)
            if data:
                event_details[eid] = data

                # lineupやroster関連フィールドを探す
                def find_keys(obj, target_keys, path=""):
                    results = []
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if any(tk in k.lower() for tk in target_keys):
                                results.append((f"{path}.{k}", v))
                            results.extend(find_keys(v, target_keys, f"{path}.{k}"))
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            results.extend(find_keys(item, target_keys, f"{path}[{i}]"))
                    return results

                lineup_refs = find_keys(data, ["lineup", "roster", "team", "participant"])
                relevant = [(p, v) for p, v in lineup_refs if isinstance(v, (str, int, list)) and v]
                if relevant:
                    print(f"  {ename}: {len(relevant)} relevant fields")
                    for path, val in relevant[:5]:
                        val_str = str(val)[:80]
                        print(f"    {path}: {val_str}")

        # === Step 7: Lineups API ===
        print("\n--- Step 7: Lineups API ---")
        for ev in all_events:
            eid = ev["event_id"]
            ename = ev["event_name"]
            for region in REGIONS:
                urls_to_try = [
                    f"{CF_BASE}/algs/{SEASON_SLUG}/lineups/{eid}?region={region}",
                    f"{CF_BASE}/algs/{SEASON_SLUG}/event-lineups/{eid}?region={region}",
                    f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/lineups/{eid}?region={region}",
                    f"{MAJESTIC_BASE}/algs/{SEASON_SLUG}/events/{eid}/lineups?region={region}",
                    f"{CF_BASE}/algs/{SEASON_SLUG}/event-teams/{eid}?region={region}",
                ]
                for url in urls_to_try:
                    data = fetch_json(page, url)
                    if data:
                        if isinstance(data, list) and len(data) > 0:
                            rs = REGION_SHORT[region]
                            print(f"  {ename}|{rs}: {len(data)} lineups via {url.split('/')[-1].split('?')[0]}")
                            fname = f"lineups_{eid}_{region}.json"
                            with open(CACHE_DIR / fname, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                            # サンプル表示
                            sample = data[0]
                            if isinstance(sample, dict):
                                print(f"    Keys: {list(sample.keys())[:15]}")
                                if "members" in sample:
                                    for m in sample["members"][:3]:
                                        print(f"      {m.get('inGameName', m.get('username', '?'))}")
                            break
                        elif isinstance(data, dict) and data:
                            print(f"  {ename}|{REGION_SHORT[region]}: object with keys {list(data.keys())[:10]}")
                            break
                # 最初のイベント+リージョンだけ試す（APIパターン確認のため）
                break
            break

        browser.close()

    # === 最終結果まとめ ===
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"\nイベント一覧 ({len(all_events)}):")
    for ev in all_events:
        print(f"  {ev['event_type']} > {ev['event_name']}")

    print(f"\nStructureID一覧 ({len(structure_ids)}):")
    for sid, info in structure_ids.items():
        print(f"  {sid} | {info['event']} | {info['region_short']}")

    print(f"\nリーダーボード ({len(leaderboard_data)} regions):")
    for region, lb in leaderboard_data.items():
        print(f"  {REGION_SHORT[region]}: {lb['total']} teams")

    print(f"\nQualified teams ({len(qualified_data)} events):")
    for key, teams in qualified_data.items():
        print(f"  {key}: {len(teams)} teams")

    print(f"\nチームロスター (from structureIDs): {len(team_rosters)} combos")
    total_teams = 0
    for key, data in team_rosters.items():
        count = data["team_count"]
        total_teams += count
        print(f"  {key}: {count} teams")
    print(f"  合計: {total_teams} teams")

    print(f"\n傍受API ({len(api_captured)}):")
    for url in api_captured:
        print(f"  {url[:150]}")

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
        "leaderboards": {
            region: {
                "total": lb["total"],
                "teams": lb["teams"],
            }
            for region, lb in leaderboard_data.items()
        },
        "qualified_teams": qualified_data,
        "team_rosters_from_structures": {
            key: {
                "structureID": data["structureID"],
                "event": data["event"],
                "region": data["region"],
                "team_count": data["team_count"],
                "teams": data["teams"],
            }
            for key, data in team_rosters.items()
        },
        "captured_api_urls": list(api_captured.keys()),
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    file_size = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n保存完了: {OUTPUT_FILE} ({file_size:.1f} KB)")


if __name__ == "__main__":
    main()
