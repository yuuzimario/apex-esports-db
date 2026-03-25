"""
Battlefy ALGS Year 6 トーナメントID発見スクリプト
Playwrightでネットワークリクエストを傍受し、トーナメントIDを収集する
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import re
import time
import httpx
from pathlib import Path
from playwright.sync_api import sync_playwright

# 結果保存先
CACHE_DIR = Path("C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CACHE_DIR / "battlefy_discovery.json"

# CloudFront API ベースURL
CLOUDFRONT_BASE = "https://dtmwra1jsgyb0.cloudfront.net"

# MongoDB ObjectId パターン（24文字の16進数）
OBJECTID_PATTERN = re.compile(r'[0-9a-f]{24}')

# 探索するURL一覧
URLS_TO_VISIT = [
    "https://battlefy.com/apex-legends-global-series-year-6",
    "https://battlefy.com/leagues/algs/",
    "https://battlefy.com/apex-legends-global-series-year-6/tournaments",
]

# 発見したトーナメントID → メタデータ
discovered_ids = {}
# 傍受したAPIレスポンス
intercepted_responses = []


def extract_tournament_ids_from_text(text: str) -> set:
    """テキストからトーナメントIDっぽい24文字hex文字列を抽出"""
    return set(OBJECTID_PATTERN.findall(text))


def check_cloudfront_teams(tournament_id: str) -> dict | None:
    """CloudFront APIでチームデータが取得できるか確認"""
    url = f"{CLOUDFRONT_BASE}/tournaments/{tournament_id}/teams"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://battlefy.com",
        "Referer": "https://battlefy.com/",
    }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return {
                        "team_count": len(data),
                        "sample_teams": [
                            {
                                "name": t.get("name", "?"),
                                "players": [
                                    p.get("inGameName", p.get("username", "?"))
                                    for p in t.get("players", [])
                                ],
                            }
                            for t in data[:3]
                        ],
                    }
                return {"team_count": 0, "sample_teams": []}
            return None
    except Exception as e:
        print(f"  CloudFront error for {tournament_id}: {e}")
        return None


def check_cloudfront_tournament_info(tournament_id: str) -> dict | None:
    """CloudFront APIでトーナメント情報を取得"""
    url = f"{CLOUDFRONT_BASE}/tournaments/{tournament_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://battlefy.com",
        "Referer": "https://battlefy.com/",
    }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                return {
                    "name": data.get("name", "?"),
                    "game": data.get("game", {}).get("name", data.get("gameName", "?")),
                    "startTime": data.get("startTime", "?"),
                    "status": data.get("status", "?"),
                    "teamCount": data.get("teamCount", 0),
                    "region": data.get("region", "?"),
                }
            return None
    except Exception as e:
        print(f"  CloudFront info error for {tournament_id}: {e}")
        return None


def on_response(response):
    """Playwrightのレスポンスハンドラ — APIレスポンスを傍受"""
    url = response.url
    # API呼び出しっぽいURLのみ処理
    if any(keyword in url for keyword in [
        "cloudfront.net", "api.battlefy.com", "battlefy.com/api",
        "/tournaments", "/organizations", "/leagues",
        "dtmwra1jsgyb0", "graphql",
    ]):
        try:
            body = response.text()
            ids = extract_tournament_ids_from_text(body)
            if ids:
                intercepted_responses.append({
                    "url": url,
                    "status": response.status,
                    "id_count": len(ids),
                    "ids": list(ids),
                })
                for tid in ids:
                    if tid not in discovered_ids:
                        discovered_ids[tid] = {"source_urls": []}
                    if url not in discovered_ids[tid]["source_urls"]:
                        discovered_ids[tid]["source_urls"].append(url)
        except Exception:
            pass


def search_battlefy_api_directly():
    """Battlefy APIを直接叩いてALGSトーナメントを検索"""
    print("\n=== Battlefy API 直接検索 ===")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    # 組織IDを探す
    org_urls = [
        f"{CLOUDFRONT_BASE}/organizations?name=apex-legends-global-series-year-6",
        f"{CLOUDFRONT_BASE}/organizations?name=ALGS",
        "https://api.battlefy.com/organizations?name=apex-legends-global-series-year-6",
    ]

    # 既知のBattlefy APIパターン
    search_urls = [
        # 組織のトーナメント一覧（組織slugから）
        f"{CLOUDFRONT_BASE}/organizations/apex-legends-global-series-year-6/tournaments",
        # 検索API
        f"{CLOUDFRONT_BASE}/tournaments?search=ALGS&game=Apex+Legends",
        f"{CLOUDFRONT_BASE}/tournaments?search=ALGS+Year+6",
        # ゲームIDでの検索（Apex LegendsのゲームID）
        f"{CLOUDFRONT_BASE}/tournaments?game=5c44ae21c3285e6b03efa6d6&search=ALGS",
    ]

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        for url in org_urls + search_urls:
            try:
                print(f"  Trying: {url}")
                resp = client.get(url, headers=headers)
                print(f"    Status: {resp.status_code}")
                if resp.status_code == 200:
                    body = resp.text()
                    ids = extract_tournament_ids_from_text(body)
                    if ids:
                        print(f"    Found {len(ids)} IDs")
                        for tid in ids:
                            if tid not in discovered_ids:
                                discovered_ids[tid] = {"source_urls": []}
                            discovered_ids[tid]["source_urls"].append(url)
                    # JSONを解析してトーナメント名も取得
                    try:
                        data = resp.json()
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    tid = item.get("_id", "")
                                    name = item.get("name", "")
                                    if tid and name:
                                        print(f"    Tournament: {name} (ID: {tid})")
                        elif isinstance(data, dict):
                            tid = data.get("_id", "")
                            name = data.get("name", "")
                            if tid:
                                print(f"    Org/Tournament: {name} (ID: {tid})")
                    except Exception:
                        pass
            except Exception as e:
                print(f"    Error: {e}")


def discover_from_org_page(org_id: str):
    """組織IDからトーナメント一覧を取得"""
    print(f"\n=== 組織 {org_id} のトーナメント一覧取得 ===")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    # ページネーション付きで取得
    page = 1
    while True:
        url = f"{CLOUDFRONT_BASE}/organizations/{org_id}/tournaments?page={page}&per_page=50"
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    print(f"  Page {page}: status {resp.status_code}")
                    break
                data = resp.json()
                if not isinstance(data, list) or len(data) == 0:
                    break
                for t in data:
                    tid = t.get("_id", "")
                    name = t.get("name", "")
                    start = t.get("startTime", "")
                    if tid:
                        discovered_ids[tid] = {
                            "source_urls": [url],
                            "name": name,
                            "startTime": start,
                        }
                        print(f"  Found: {name} | {start} | {tid}")
                print(f"  Page {page}: {len(data)} tournaments")
                if len(data) < 50:
                    break
                page += 1
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break


def main():
    print("=" * 70)
    print("Battlefy ALGS Year 6 トーナメントID発見スクリプト")
    print("=" * 70)

    # Phase 1: Playwrightでページをブラウズし、ネットワークリクエストを傍受
    print("\n=== Phase 1: Playwright でページブラウズ ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.on("response", on_response)

        for url in URLS_TO_VISIT:
            print(f"\nVisiting: {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # ページ内のリンクからトーナメントIDを抽出
                content = page.content()
                # URLパターンからID抽出
                url_ids = re.findall(r'/tournaments?/([0-9a-f]{24})', content)
                for tid in url_ids:
                    if tid not in discovered_ids:
                        discovered_ids[tid] = {"source_urls": []}
                    discovered_ids[tid]["source_urls"].append(f"page_content:{url}")
                    print(f"  Found in page HTML: {tid}")

                # hrefからもトーナメントリンクを探す
                links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                for link in links:
                    ids_in_link = re.findall(r'/([0-9a-f]{24})', link)
                    for tid in ids_in_link:
                        if tid not in discovered_ids:
                            discovered_ids[tid] = {"source_urls": []}
                        if f"link:{link}" not in discovered_ids[tid]["source_urls"]:
                            discovered_ids[tid]["source_urls"].append(f"link:{link}")

                # スクロールしてさらにコンテンツを読み込む
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(0.5)

                # スクロール後のコンテンツも確認
                content_after = page.content()
                url_ids_after = re.findall(r'/tournaments?/([0-9a-f]{24})', content_after)
                for tid in url_ids_after:
                    if tid not in discovered_ids:
                        discovered_ids[tid] = {"source_urls": []}
                        discovered_ids[tid]["source_urls"].append(f"page_content_scroll:{url}")
                        print(f"  Found after scroll: {tid}")

            except Exception as e:
                print(f"  Error visiting {url}: {e}")

        # 「もっと見る」ボタンなどをクリック
        try:
            page.goto(URLS_TO_VISIT[0], wait_until="networkidle", timeout=30000)
            time.sleep(2)
            # 「View More」や「Show All」ボタンを探してクリック
            buttons = page.query_selector_all("button, a.btn, [class*='more'], [class*='load'], [class*='show']")
            for btn in buttons:
                try:
                    text = btn.text_content() or ""
                    if any(word in text.lower() for word in ["more", "all", "view", "show", "load"]):
                        print(f"  Clicking button: {text.strip()}")
                        btn.click()
                        time.sleep(2)
                except Exception:
                    pass
        except Exception as e:
            print(f"  Error clicking buttons: {e}")

        # Battlefyの内部APIパターンを試す（ページコンテキスト内で）
        try:
            # window.__NEXT_DATA__ からデータを抽出（Next.jsベースの場合）
            next_data = page.evaluate("() => { try { return JSON.stringify(window.__NEXT_DATA__) } catch(e) { return null } }")
            if next_data:
                print("\n  Found __NEXT_DATA__!")
                ids = extract_tournament_ids_from_text(next_data)
                for tid in ids:
                    if tid not in discovered_ids:
                        discovered_ids[tid] = {"source_urls": ["__NEXT_DATA__"]}
                        print(f"  Found in __NEXT_DATA__: {tid}")
        except Exception:
            pass

        # Battlefy検索ページも試す
        search_queries = ["ALGS Year 6", "ALGS 2026", "Apex Legends Global Series Year 6", "ALGS Split"]
        for query in search_queries:
            try:
                search_url = f"https://battlefy.com/search?query={query.replace(' ', '+')}"
                print(f"\nSearching: {search_url}")
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                time.sleep(3)
                content = page.content()
                ids = re.findall(r'/tournaments?/([0-9a-f]{24})', content)
                for tid in ids:
                    if tid not in discovered_ids:
                        discovered_ids[tid] = {"source_urls": []}
                    discovered_ids[tid]["source_urls"].append(f"search:{query}")
                    print(f"  Found via search '{query}': {tid}")
            except Exception as e:
                print(f"  Search error: {e}")

        browser.close()

    print(f"\n=== Phase 1 結果: {len(discovered_ids)} IDs found from Playwright ===")

    # Phase 2: 直接API検索
    search_battlefy_api_directly()

    # 組織IDが見つかった場合、そこからトーナメント一覧を取得
    org_ids = set()
    for tid, meta in discovered_ids.items():
        for src in meta.get("source_urls", []):
            if "organizations" in src:
                # URLから組織IDを抽出
                org_match = re.search(r'organizations/([0-9a-f]{24})', src)
                if org_match:
                    org_ids.add(org_match.group(1))

    for oid in org_ids:
        discover_from_org_page(oid)

    print(f"\n=== Phase 2 結果: 合計 {len(discovered_ids)} IDs ===")

    # Phase 3: 各IDのCloudFront APIでデータ確認
    print("\n=== Phase 3: CloudFront API でデータ確認 ===")
    results = {}
    for i, (tid, meta) in enumerate(discovered_ids.items()):
        print(f"\n[{i+1}/{len(discovered_ids)}] ID: {tid}")

        # トーナメント情報取得
        info = check_cloudfront_tournament_info(tid)
        if info:
            print(f"  Name: {info.get('name', '?')}")
            print(f"  Game: {info.get('game', '?')}")
            print(f"  Start: {info.get('startTime', '?')}")
            print(f"  Status: {info.get('status', '?')}")
            print(f"  Teams: {info.get('teamCount', 0)}")
            meta["tournament_info"] = info
        else:
            # メタから名前がある場合はそのまま使う
            if "name" not in meta:
                print("  (トーナメント情報取得失敗)")

        # チームデータ取得
        teams = check_cloudfront_teams(tid)
        if teams:
            print(f"  Team data: {teams['team_count']} teams")
            if teams["sample_teams"]:
                for st in teams["sample_teams"]:
                    print(f"    - {st['name']}: {', '.join(st['players'][:3])}")
            meta["teams_available"] = True
            meta["team_count"] = teams["team_count"]
            meta["sample_teams"] = teams["sample_teams"]
        else:
            meta["teams_available"] = False
            print("  Team data: not available")

        results[tid] = meta

    # Phase 4: Apex Legends関連のみフィルタリング
    apex_results = {}
    other_results = {}
    for tid, meta in results.items():
        info = meta.get("tournament_info", {})
        name = info.get("name", meta.get("name", "")).lower()
        game = info.get("game", "").lower()

        is_apex = (
            "apex" in name or "algs" in name or
            "apex" in game or
            any("apex" in src.lower() or "algs" in src.lower() for src in meta.get("source_urls", []))
        )

        if is_apex:
            apex_results[tid] = meta
        else:
            other_results[tid] = meta

    # 結果出力
    print("\n" + "=" * 70)
    print(f"APEX LEGENDS 関連トーナメント: {len(apex_results)}")
    print("=" * 70)
    for tid, meta in apex_results.items():
        info = meta.get("tournament_info", {})
        name = info.get("name", meta.get("name", "不明"))
        teams = meta.get("team_count", 0)
        has_teams = meta.get("teams_available", False)
        print(f"  {tid} | {name} | Teams: {teams} | Data: {'YES' if has_teams else 'NO'}")

    if other_results:
        print(f"\nその他のトーナメント: {len(other_results)}")
        for tid, meta in list(other_results.items())[:10]:
            info = meta.get("tournament_info", {})
            name = info.get("name", meta.get("name", "不明"))
            print(f"  {tid} | {name}")

    # 保存
    output = {
        "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_ids": len(results),
        "apex_tournament_count": len(apex_results),
        "apex_tournaments": apex_results,
        "other_tournaments": {k: v for k, v in list(other_results.items())[:20]},
        "intercepted_api_calls": intercepted_responses[:50],
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n結果を保存: {OUTPUT_FILE}")
    print(f"合計: {len(results)} IDs, うちApex関連: {len(apex_results)}")


if __name__ == "__main__":
    main()
