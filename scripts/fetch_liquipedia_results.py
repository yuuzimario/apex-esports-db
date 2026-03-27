"""
Liquipedia APIからYear 1-5の不足大会結果を取得
リクエスト間隔15秒で安全に取得

使い方:
  python fetch_liquipedia_results.py          # 本番実行
  python fetch_liquipedia_results.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse
from bs4 import BeautifulSoup

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache/lp_results"
os.makedirs(CACHE_DIR, exist_ok=True)

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

REQUEST_INTERVAL = 15  # 秒

client = httpx.Client(timeout=60, follow_redirects=True)
db_client = httpx.Client(timeout=30)

# === 不足大会定義（Wayback Machine対応パス） ===
TOURNAMENTS = [
    # Year 1 Championship（正しいパス: Championship/Region/2021）
    {
        "lp_page": "Apex_Legends_Global_Series/Championship/North_America/2021",
        "db_name": "ALGS Year 1 Championship - NA",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "NA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Championship/EMEA/2021",
        "db_name": "ALGS Year 1 Championship - EMEA",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "EMEA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Championship/APAC_North/2021",
        "db_name": "ALGS Year 1 Championship - APAC North",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_N",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Championship/APAC_South/2021",
        "db_name": "ALGS Year 1 Championship - APAC South",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_S",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    # Year 2 Split 2 Playoffs
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Split_2/Playoffs",
        "db_name": "ALGS Year 2 Split 2 Playoffs",
        "series": "ALGS Year 2",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2022-04-29",
        "end_date": "2022-05-01",
        "is_lan": True,
        "location": "Stockholm, Sweden",
        "prize_pool_usd": 1000000,
    },
    # Year 4 Championship (DB登録済み・結果0件)
    {
        "lp_page": "Apex_Legends_Global_Series/Year_4/Championship",
        "db_name": "ALGS Year 4 Championship",
        "series": "ALGS Year 4",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2025-04-24",
        "end_date": "2025-04-27",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 2000000,
        "existing": True,
    },
    # Year 4 Split 1 Playoffs
    {
        "lp_page": "Apex_Legends_Global_Series/Year_4/Split_1/Playoffs",
        "db_name": "ALGS Year 4 Split 1 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-03-28",
        "end_date": "2024-03-31",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
    },
    # Year 4 Split 2 Playoffs
    {
        "lp_page": "Apex_Legends_Global_Series/Year_4/Split_2/Playoffs",
        "db_name": "ALGS Year 4 Split 2 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-09-12",
        "end_date": "2024-09-15",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
    },
    # Year 5 LCQ (DB登録済み・結果0件) — Waybackにスナップショットなし。Liquipedia直接のみ
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Last_Chance_Qualifier/Americas",
        "db_name": "ALGS Year 5 Last Chance Qualifier - Americas",
        "series": "ALGS Year 5",
        "event_type": "lcq",
        "region": "NA",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Last_Chance_Qualifier/APAC_North",
        "db_name": "ALGS Year 5 Last Chance Qualifier - Asia Pacific North",
        "series": "ALGS Year 5",
        "event_type": "lcq",
        "region": "APAC_N",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Last_Chance_Qualifier/APAC_South",
        "db_name": "ALGS Year 5 Last Chance Qualifier - Asia Pacific South",
        "series": "ALGS Year 5",
        "event_type": "lcq",
        "region": "APAC_S",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Last_Chance_Qualifier/EMEA",
        "db_name": "ALGS Year 5 Last Chance Qualifier - Europe Middle East and Africa",
        "series": "ALGS Year 5",
        "event_type": "lcq",
        "region": "EMEA",
        "existing": True,
        "liquipedia_only": True,
    },
    # Year 5 Pro League Qualifier (DB登録済み・結果0件)
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Pro_League_Qualifier/Americas",
        "db_name": "ALGS Year 5 Pro League Qualifier - Americas",
        "series": "ALGS Year 5",
        "event_type": "qualifier",
        "region": "NA",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Pro_League_Qualifier/APAC_North",
        "db_name": "ALGS Year 5 Pro League Qualifier - Asia Pacific North",
        "series": "ALGS Year 5",
        "event_type": "qualifier",
        "region": "APAC_N",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Pro_League_Qualifier/APAC_South",
        "db_name": "ALGS Year 5 Pro League Qualifier - Asia Pacific South",
        "series": "ALGS Year 5",
        "event_type": "qualifier",
        "region": "APAC_S",
        "existing": True,
        "liquipedia_only": True,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/Year_5/Pro_League_Qualifier/EMEA",
        "db_name": "ALGS Year 5 Pro League Qualifier - Europe Middle East and Africa",
        "series": "ALGS Year 5",
        "event_type": "qualifier",
        "region": "EMEA",
        "existing": True,
        "liquipedia_only": True,
    },
]


def normalize_name(name):
    if not name:
        return ""
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def supabase_get(table, params=None):
    all_data = []
    offset = 0
    while True:
        p = {**(params or {}), "limit": "1000", "offset": str(offset)}
        resp = db_client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return all_data


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = db_client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


WB_CDX = "https://web.archive.org/cdx/search/cdx"


def fetch_html(page_title, liquipedia_only=False):
    """HTMLを取得（Wayback Machine優先、フォールバックでLiquipedia API）"""
    cache_file = os.path.join(CACHE_DIR, f"{page_title.replace('/', '_')}.html")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    # liquipedia_onlyフラグがない場合はWayback Machineを試す
    if not liquipedia_only:
        html = _fetch_wayback(page_title)
        if html:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(html)
            return html

    # Waybackになければ Liquipedia API
    html = _fetch_liquipedia_api(page_title)
    if html:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(html)
    return html


def _fetch_wayback(page_title):
    """Wayback Machine経由でHTMLを取得"""
    lp_url = f"liquipedia.net/apexlegends/{page_title}"
    print(f"    Wayback検索: {page_title}")

    try:
        params = {
            "url": lp_url,
            "output": "json",
            "limit": "5",
            "fl": "timestamp,statuscode",
        }
        resp = client.get(WB_CDX, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"    CDXエラー: {resp.status_code}")
            return None

        data = resp.json()
        snapshots = [row for row in data[1:] if row[1] == "200"] if len(data) > 1 else []
        if not snapshots:
            print(f"    スナップショットなし")
            return None

        ts = snapshots[-1][0]
        wb_url = f"https://web.archive.org/web/{ts}id_/https://liquipedia.net/apexlegends/{page_title}"
        print(f"    Wayback: {ts}")

        time.sleep(3)
        resp2 = client.get(wb_url, timeout=120)
        if resp2.status_code != 200:
            print(f"    HTML取得エラー: {resp2.status_code}")
            return None

        return resp2.text

    except Exception as e:
        print(f"    Waybackエラー: {e}")
        return None


def _fetch_liquipedia_api(page_title):
    """Liquipedia APIからHTMLを取得"""
    print(f"    Liquipedia API: {page_title}")
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    }

    try:
        resp = client.get(LP_API, params=params, headers=LP_HEADERS)
        if resp.status_code == 429:
            print("    レート制限！60秒待機...")
            time.sleep(60)
            resp = client.get(LP_API, params=params, headers=LP_HEADERS)

        if resp.status_code != 200:
            print(f"    APIエラー: {resp.status_code}")
            return None

        data = resp.json()
        if "error" in data:
            print(f"    ページなし: {data['error'].get('info', '')}")
            return None

        html = data.get("parse", {}).get("text", {}).get("*", "")
        if not html:
            return None

        time.sleep(REQUEST_INTERVAL)
        return html

    except Exception as e:
        print(f"    エラー: {e}")
        return None


def parse_standings_bs(html):
    """BeautifulSoupでstandingsテーブルを解析"""
    soup = BeautifulSoup(html, "html.parser")

    # 戦略1: Finals セクション内の table-battleroyale-results
    finals = soup.find("span", id="Finals")
    if finals:
        tables = _get_section_tables(finals)
        for table in tables:
            cls = " ".join(table.get("class", []))
            if "table-battleroyale-results" in cls:
                results = _parse_table(table)
                if results and 10 <= len(results) <= 40:
                    return results
        best = _find_best_table(tables, 40)
        if best and 10 <= len(best) <= 40:
            return best

    # 戦略2: Overall Standings
    for sid in ["Overall_Standings", "Overall_standings"]:
        heading = soup.find("span", id=sid)
        if heading:
            tables = _get_section_tables(heading)
            best = _find_best_table(tables, 40)
            if best and len(best) >= 10:
                return best

    # 戦略3: League Standings テーブル
    for table in soup.find_all("table"):
        text = table.get_text()
        if "League Standings" not in text:
            continue
        teams = _count_teams(table)
        if 10 <= teams <= 40:
            results = _deduplicate(_parse_table(table))
            if results and 10 <= len(results) <= 40:
                return results

    # 戦略4: Results セクション
    results_heading = soup.find("span", id="Results")
    if results_heading:
        tables = _get_section_tables(results_heading)
        best = _find_best_table(tables, 40)
        if best and len(best) >= 10:
            return best

    # 戦略5: 最大テーブル
    best_result = None
    best_count = 0
    for table in soup.find_all("table"):
        teams = _count_teams(table)
        if not (10 <= teams <= 40) or teams <= best_count:
            continue
        if table.find("table", attrs={"data-highlightingclass": True}):
            continue
        results = _deduplicate(_parse_table(table))
        if results and 10 <= len(results) <= 40 and len(results) > best_count:
            best_result = results
            best_count = len(results)
    return best_result or []


def _get_section_tables(heading_span):
    tables = []
    parent = heading_span.parent
    if not parent:
        return tables
    for sibling in parent.next_siblings:
        if hasattr(sibling, "name") and sibling.name in ("h2", "h3", "h4"):
            break
        if hasattr(sibling, "find_all"):
            for table in sibling.find_all("table"):
                tables.append(table)
            if sibling.name == "table":
                tables.append(sibling)
    return tables


def _count_teams(table):
    return len(set(
        el["data-highlightingclass"]
        for el in table.find_all(attrs={"data-highlightingclass": True})
    ))


def _find_best_table(tables, max_teams=40):
    best = None
    best_score = 0
    for table in tables:
        teams = _count_teams(table)
        if not (5 <= teams <= max_teams):
            continue
        text = table.get_text()
        score = teams + (20 if "Standings" in text or "Total" in text else 0)
        if score > best_score:
            results = _parse_table(table)
            if results and len(results) <= max_teams:
                best = results
                best_score = score
    return best


def _parse_table(table):
    results = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        first = cells[0].get_text(strip=True).rstrip(".")
        if not first or not first.replace("-", "").isdigit():
            continue
        placement = int(first.split("-")[0])

        team_name = None
        for cell in cells[1:3]:
            hl = cell.find(attrs={"data-highlightingclass": True})
            if hl:
                team_name = hl["data-highlightingclass"]
                break
            link = cell.find("a", title=True)
            if link and not link["title"].startswith("File:"):
                team_name = link["title"]
                break
        if not team_name:
            continue

        total_points = None
        for cell in cells[2:4]:
            ct = cell.get_text(strip=True)
            if ct.isdigit() and int(ct) > 0:
                total_points = int(ct)
                break

        results.append({
            "placement": placement,
            "team_name": team_name,
            "total_points": total_points,
        })
    return results


def _deduplicate(results):
    if not results:
        return results
    seen = {}
    for r in results:
        name = r["team_name"]
        if name not in seen:
            seen[name] = r
        else:
            old_pts = seen[name].get("total_points") or 0
            new_pts = r.get("total_points") or 0
            if new_pts > old_pts:
                seen[name]["total_points"] = new_pts
    return sorted(seen.values(), key=lambda x: x["placement"])


def match_team(team_name, teams_by_norm):
    if not team_name:
        return None
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]
    clean = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
    cn = normalize_name(clean)
    if cn and cn in teams_by_norm:
        return teams_by_norm[cn]
    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + team_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]
    for suffix in [" esports", " gaming", " e-sports"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wayback-only", action="store_true", help="Liquipedia APIを使わず、Wayback Machineのみ")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia → 不足大会結果取得")
    print(f"リクエスト間隔: {REQUEST_INTERVAL}秒")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # DB既存データ
    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get("tournaments", {"select": "id,name,slug"})

    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        name = t["name"]
        if name.lower().startswith("team "):
            teams_by_norm[normalize_name(name[5:])] = t
        for sfx in [" Esports", " Gaming", " E-Sports"]:
            if name.endswith(sfx):
                teams_by_norm[normalize_name(name[:len(name) - len(sfx)])] = t

    tournament_by_slug = {t["slug"]: t for t in existing_tournaments}
    tournament_by_name = {t["name"]: t for t in existing_tournaments}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)}")

    stats = {"created": 0, "skipped": 0, "results": 0, "teams_created": 0, "no_data": 0}

    for tdef in TOURNAMENTS:
        name = tdef["db_name"]
        slug = make_slug(name)
        print(f"\n--- {name} ---")

        # 既存チェック
        existing = tournament_by_name.get(name) or tournament_by_slug.get(slug)
        if existing:
            # 結果があるかチェック
            existing_results = supabase_get("tournament_results", {
                "select": "id", "tournament_id": f"eq.{existing['id']}", "limit": "1"
            })
            if existing_results:
                print("  既に結果あり。スキップ")
                stats["skipped"] += 1
                continue
            print(f"  既存大会（結果なし）: {existing['id'][:15]}...")
            tournament_id = existing["id"]
        else:
            tournament_id = None

        # liquipedia_onlyの大会はWaybackモード時スキップ
        if args.wayback_only and tdef.get("liquipedia_only"):
            print("  Liquipedia専用→スキップ（--wayback-only）")
            stats["no_data"] += 1
            continue

        # HTML取得（Wayback優先）
        html = fetch_html(tdef["lp_page"], liquipedia_only=tdef.get("liquipedia_only", False))
        if not html:
            print("  HTML取得失敗")
            stats["no_data"] += 1
            continue

        results = parse_standings_bs(html)
        if not results:
            print("  結果パース失敗")
            stats["no_data"] += 1
            continue

        print(f"  結果: {len(results)}チーム")
        for r in results[:5]:
            team = match_team(r["team_name"], teams_by_norm)
            status = "OK" if team else "??"
            pts = r.get("total_points") or "-"
            print(f"    {r['placement']:3d}位 [{status}] {r['team_name']:30s} pts={pts}")
        if len(results) > 5:
            print(f"    ... 他 {len(results) - 5}チーム")

        if args.dry_run:
            continue

        # 大会作成（必要な場合）
        if not tournament_id:
            tourney_data = {
                "name": name,
                "slug": slug,
                "series": tdef["series"],
                "event_type": tdef["event_type"],
                "region": tdef["region"],
                "start_date": tdef.get("start_date"),
                "end_date": tdef.get("end_date"),
                "is_lan": tdef.get("is_lan", False),
                "location": tdef.get("location"),
                "prize_pool_usd": tdef.get("prize_pool_usd"),
                "status": "completed",
                "liquipedia_url": f"https://liquipedia.net/apexlegends/{tdef['lp_page']}",
            }
            created = supabase_insert("tournaments", [tourney_data])
            if not created:
                print("  大会作成失敗")
                continue
            tournament_id = created[0]["id"]
            stats["created"] += 1

        # 結果登録
        to_insert = []
        for r in results:
            team = match_team(r["team_name"], teams_by_norm)
            if not team:
                # 自動追加
                new_data = {
                    "name": r["team_name"],
                    "slug": make_slug(r["team_name"]),
                    "region": tdef["region"] if tdef["region"] != "GLOBAL" else None,
                    "is_active": False,
                }
                created = supabase_insert("teams", [new_data])
                if created:
                    team = created[0]
                    teams_by_norm[normalize_name(r["team_name"])] = team
                    stats["teams_created"] += 1
                else:
                    continue

            to_insert.append({
                "tournament_id": tournament_id,
                "team_id": team["id"],
                "placement": r["placement"],
                "total_points": r.get("total_points"),
            })

        if to_insert:
            inserted = supabase_insert("tournament_results", to_insert)
            count = len(inserted) if inserted else 0
            stats["results"] += count
            print(f"  結果登録: {count}件")

    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  大会新規作成: {stats['created']}")
    print(f"  スキップ: {stats['skipped']}")
    print(f"  データなし: {stats['no_data']}")
    print(f"  結果登録: {stats['results']}件")
    print(f"  チーム新規追加: {stats['teams_created']}")


if __name__ == "__main__":
    main()
