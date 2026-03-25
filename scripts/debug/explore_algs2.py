import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright
import os
import json

DEBUG_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/debug"
os.makedirs(DEBUG_DIR, exist_ok=True)

api_calls = []

def capture_response(response):
    url = response.url
    if "prod-api.algstools.com" in url:
        try:
            content_type = response.headers.get("content-type", "")
            body = ""
            try:
                body = response.text()
            except:
                body = "(could not read)"
            api_calls.append({
                "url": url,
                "status": response.status,
                "body": body[:2000]
            })
        except:
            api_calls.append({"url": url, "status": response.status})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.on("response", capture_response)

    # === 1. マッチページからテーブルデータを完全抽出 ===
    print("=== 1. Extracting table data from match page ===")
    match_url = "https://algs.ea.com/en/year-6/split-1-pro-league-apac-north/match/01KH745JDA97FY0G26HXJD2FN2"
    page.goto(match_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    # テーブルヘッダーとデータ抽出
    table_data = page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        const results = [];
        tables.forEach((table, i) => {
            const headers = [];
            table.querySelectorAll('thead th').forEach(th => headers.push(th.textContent.trim()));
            const rows = [];
            table.querySelectorAll('tbody tr').forEach(tr => {
                const cells = [];
                tr.querySelectorAll('td').forEach(td => {
                    const img = td.querySelector('img');
                    const text = td.textContent.trim();
                    cells.push({
                        text: text.substring(0, 100),
                        imgSrc: img ? img.src : null,
                        cls: td.className || '',
                        html: td.innerHTML.substring(0, 200)
                    });
                });
                rows.push(cells);
            });
            results.push({tableIndex: i, headers, rowCount: rows.length, rows: rows.slice(0, 3)});
        });
        return results;
    }""")

    print("Found " + str(len(table_data)) + " tables")
    for t in table_data:
        print("\n  Table " + str(t["tableIndex"]) + ": " + str(t["rowCount"]) + " rows")
        print("  Headers: " + str(t["headers"]))
        if t["rows"]:
            for ri, row in enumerate(t["rows"][:2]):
                print("  Row " + str(ri) + ":")
                for ci, cell in enumerate(row[:6]):
                    print("    Cell " + str(ci) + ": text=" + repr(cell["text"][:50]) + " cls=" + repr(cell["cls"][:30]) + " img=" + ("yes" if cell["imgSrc"] else "no"))

    # チーム名とプレイヤー名のCSSセレクタを特定
    print("\n=== 2. Looking for team/player specific elements ===")
    team_elements = page.evaluate("""() => {
        const teamCells = [];
        document.querySelectorAll('table tbody tr').forEach(tr => {
            const tds = tr.querySelectorAll('td');
            if (tds.length > 1) {
                const teamTd = tds[1];
                teamCells.push({
                    text: teamTd.textContent.trim().substring(0, 100),
                    html: teamTd.innerHTML.substring(0, 300),
                    classes: teamTd.className
                });
            }
        });
        return teamCells.slice(0, 10);
    }""")

    print("Team cells (first 10):")
    for tc in team_elements:
        print("  text: " + repr(tc["text"][:60]) + " class: " + repr(tc["classes"][:30]))
        print("  html: " + tc["html"][:200])

    page.screenshot(path=DEBUG_DIR + "/05_match_page.png", full_page=True)

    # === 3. standings ページの詳細調査 ===
    print("\n=== 3. Standings page deep dive ===")
    standings_url = "https://algs.ea.com/en/year-6/split-1-pro-league-americas/standings"
    page.goto(standings_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    body_text = page.evaluate("() => document.body.innerText.substring(0, 3000)")
    print("Body text (first 3000 chars):")
    print(body_text[:3000])

    page.screenshot(path=DEBUG_DIR + "/06_standings_americas.png", full_page=True)

    # === 4. 直接APIを叩く ===
    print("\n=== 4. Direct API exploration ===")
    api_page = browser.new_page()

    endpoints = [
        "/v1/regions",
        "/v1/seasons",
        "/v1/events",
        "/v1/teams",
        "/v1/players",
        "/v1/events/01KH74518P0RXFSHRZJDD7Y0SA/structure",
        "/v1/series/01KH74519X6P7G56R7DCV0JPN6/matches",
    ]

    for ep in endpoints:
        url = "https://prod-api.algstools.com" + ep
        print("\n--- " + ep + " ---")
        try:
            resp = api_page.goto(url, timeout=10000)
            body = api_page.evaluate("() => document.body.innerText")
            try:
                data = json.loads(body)
                formatted = json.dumps(data, indent=2)
                print(formatted[:2000])
            except:
                print(body[:2000])
        except Exception as e:
            print("Error: " + str(e))

    # === 5. キャプチャしたAPI呼び出しの全リスト ===
    print("\n=== 5. All prod-api.algstools.com calls (" + str(len(api_calls)) + ") ===")
    for call in api_calls:
        print("\n  [" + str(call.get("status")) + "] " + call["url"])
        if call.get("body") and len(call.get("body", "")) > 5:
            print("  Body: " + call["body"][:300])

    api_page.close()
    browser.close()

print("\n=== Done ===")
