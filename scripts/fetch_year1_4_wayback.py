"""
Wayback Machine経由でLiquipediaからYear 1〜4の大会結果を取得
Liquipedia APIがレート制限中でもWayback Machineのキャッシュから取得可能

使い方:
  python fetch_year1_4_wayback.py          # 本番実行
  python fetch_year1_4_wayback.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse
from datetime import datetime

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=60, follow_redirects=True)
db_client = httpx.Client(timeout=30)

WB_CDX = "https://web.archive.org/cdx/search/cdx"

# === Year 1〜4 主要大会定義 ===
TOURNAMENTS = [
    # === Year 1 (2020-21) ===
    {
        "lp_path": "Apex_Legends_Global_Series/2021/Championship/North_America",
        "name": "ALGS Year 1 Championship - NA",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "NA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
        "wb_after": "20210614",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2021/Championship/EMEA",
        "name": "ALGS Year 1 Championship - EMEA",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "EMEA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
        "wb_after": "20210614",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2021/Championship/APAC_North",
        "name": "ALGS Year 1 Championship - APAC North",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_N",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
        "wb_after": "20210614",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2021/Championship/APAC_South",
        "name": "ALGS Year 1 Championship - APAC South",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_S",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
        "wb_after": "20210614",
    },
    # === Year 2 (2021-22) ===
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Championship",
        "name": "ALGS Year 2 Championship",
        "series": "ALGS Year 2",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2022-07-07",
        "end_date": "2022-07-10",
        "is_lan": True,
        "location": "Raleigh, USA",
        "prize_pool_usd": 2000000,
        "wb_after": "20220711",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Playoffs/North_America",
        "name": "ALGS Year 2 Split 2 Playoffs - NA",
        "series": "ALGS Year 2",
        "event_type": "playoffs",
        "region": "NA",
        "start_date": "2022-04-29",
        "end_date": "2022-05-01",
        "is_lan": True,
        "location": "Stockholm, Sweden",
        "prize_pool_usd": 1000000,
        "wb_after": "20220502",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/North_America",
        "name": "ALGS Year 2 Split 1 Pro League - NA",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
        "wb_after": "20220124",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 2 Split 1 Pro League - EMEA",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
        "wb_after": "20220124",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 2 Split 1 Pro League - APAC North",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
        "wb_after": "20220124",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 2 Split 1 Pro League - APAC South",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
        "wb_after": "20220124",
    },
    # === Year 3 (2022-23) ===
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Championship",
        "name": "ALGS Year 3 Championship",
        "series": "ALGS Year 3",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2023-09-06",
        "end_date": "2023-09-10",
        "is_lan": True,
        "location": "Birmingham, UK",
        "prize_pool_usd": 2000000,
        "wb_after": "20230911",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_1/Playoffs",
        "name": "ALGS Year 3 Split 1 Playoffs",
        "series": "ALGS Year 3",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2023-02-02",
        "end_date": "2023-02-05",
        "is_lan": True,
        "location": "London, UK",
        "prize_pool_usd": 1000000,
        "wb_after": "20230206",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_2/Playoffs",
        "name": "ALGS Year 3 Split 2 Playoffs",
        "series": "ALGS Year 3",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2023-06-01",
        "end_date": "2023-06-04",
        "is_lan": True,
        "location": "Miyazaki, Japan",
        "prize_pool_usd": 1000000,
        "wb_after": "20230605",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/North_America",
        "name": "ALGS Year 3 Split 1 Pro League - NA",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
        "wb_after": "20230123",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 3 Split 1 Pro League - EMEA",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
        "wb_after": "20230123",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 3 Split 1 Pro League - APAC North",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
        "wb_after": "20230123",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 3 Split 1 Pro League - APAC South",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
        "wb_after": "20230123",
    },
    # === Year 4 (2023-25) ===
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_1/Playoffs",
        "name": "ALGS Year 4 Split 1 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-03-28",
        "end_date": "2024-03-31",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
        "wb_after": "20240401",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_2/Playoffs",
        "name": "ALGS Year 4 Split 2 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-09-12",
        "end_date": "2024-09-15",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
        "wb_after": "20240916",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/North_America",
        "name": "ALGS Year 4 Split 1 Pro League - NA",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
        "wb_after": "20240304",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 4 Split 1 Pro League - EMEA",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
        "wb_after": "20240304",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 4 Split 1 Pro League - APAC North",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
        "wb_after": "20240304",
    },
    {
        "lp_path": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 4 Split 1 Pro League - APAC South",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
        "wb_after": "20240304",
    },
]


def normalize_name(name):
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
            print(f"  GET エラー: {resp.status_code}")
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


def get_wayback_snapshot(lp_path, after_date):
    """Wayback Machineから大会終了後のスナップショットを取得"""
    cache_file = os.path.join(CACHE_DIR, f"wb_{lp_path.replace('/', '_')}.html")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    lp_url = f"liquipedia.net/apexlegends/{lp_path}"

    # スナップショット検索
    params = {
        "url": lp_url,
        "output": "json",
        "limit": "5",
        "fl": "timestamp,statuscode",
        "from": after_date,
    }
    resp = client.get(WB_CDX, params=params)
    if resp.status_code != 200:
        print(f"    CDX エラー: {resp.status_code}")
        return None

    data = resp.json()
    if len(data) < 2:
        # after_dateより前も試す
        params2 = {
            "url": lp_url,
            "output": "json",
            "limit": "3",
            "fl": "timestamp,statuscode",
        }
        resp2 = client.get(WB_CDX, params=params2)
        if resp2.status_code == 200:
            data = resp2.json()
        if len(data) < 2:
            print(f"    スナップショットなし")
            return None

    # 200のスナップショットを探す（ヘッダー行をスキップ）
    snapshots = [row for row in data[1:] if row[1] == "200"]
    if not snapshots:
        print(f"    有効なスナップショットなし")
        return None

    # 最新のスナップショットを使用
    ts = snapshots[-1][0]
    wb_url = f"https://web.archive.org/web/{ts}id_/https://liquipedia.net/apexlegends/{lp_path}"
    print(f"    Wayback: {ts}")

    time.sleep(2)  # レート制限対策

    resp3 = client.get(wb_url)
    if resp3.status_code != 200:
        print(f"    HTML取得エラー: {resp3.status_code}")
        return None

    html = resp3.text
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(html)

    return html


def parse_standings_from_html(html):
    """HTMLから大会最終結果（順位・チーム名・ポイント）を抽出"""
    results = []

    # 戦略1: "Finals" セクション内のStandingsテーブルを探す（LAN大会用）
    finals_section = extract_section(html, "Finals")
    if finals_section:
        table_results = find_best_standings_table(finals_section)
        if table_results and 10 <= len(table_results) <= 40:
            return table_results

    # 戦略2: "Overall Standings" セクション
    overall_section = extract_section(html, "Overall_Standings")
    if overall_section:
        table_results = find_best_standings_table(overall_section)
        if table_results:
            return table_results

    # 戦略3: ページ全体から「Standings」を含む最適なテーブルを探す
    # Pro League等はセクション分けが異なる場合がある
    # 20〜40チームのStandingsテーブルを優先
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)

    candidates = []
    for table in tables:
        team_refs = re.findall(r'data-highlightingclass="([^"]+)"', table)
        unique_teams = len(set(team_refs))
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL)

        if unique_teams < 5:
            continue

        has_standings = "Standings" in table
        has_total = "Total" in table

        # スコアリング: Pro League最終順位は通常20〜40チーム
        score = 0
        if has_standings:
            score += 30
        if has_total:
            score += 20
        # 20チーム前後が最終順位表の可能性が高い
        if 15 <= unique_teams <= 40:
            score += 25
        elif 10 <= unique_teams <= 50:
            score += 10
        # チーム数が多すぎる場合はペナルティ（グループ分けの可能性）
        if unique_teams > 50:
            score -= 20

        candidates.append((score, unique_teams, table))

    candidates.sort(key=lambda x: (-x[0], -x[1]))

    for score, unique_teams, table in candidates[:3]:
        table_results = parse_table_rows(table)
        if table_results and len(table_results) >= 10:
            return table_results

    return results


def extract_section(html, section_id):
    """HTMLからセクションを抽出（h2/h3のspan id で区切る）"""
    pattern = rf'<span[^>]*id="{section_id}"'
    start_match = re.search(pattern, html)
    if not start_match:
        return None

    # 次のh2/h3セクションまで
    rest = html[start_match.start():]
    next_section = re.search(r'<h[23][^>]*><span[^>]*id="(?!.*(edit))', rest[100:])
    if next_section:
        return rest[:100 + next_section.start()]
    return rest[:50000]  # セクション見つからなければ50KB分


def find_best_standings_table(section_html):
    """セクション内から最適なStandingsテーブルを探す"""
    tables = re.findall(r'<table[^>]*>(.*?)</table>', section_html, re.DOTALL)

    best_results = []
    best_score = 0

    for table in tables:
        team_refs = re.findall(r'data-highlightingclass="([^"]+)"', table)
        unique_teams = len(set(team_refs))

        if unique_teams < 5:
            continue

        has_standings = "Standings" in table
        score = unique_teams + (20 if has_standings else 0)

        if score > best_score:
            parsed = parse_table_rows(table)
            if parsed:
                best_results = parsed
                best_score = score

    return best_results


def parse_table_rows(table_html):
    """テーブルの行から順位・チーム名・ポイントを抽出"""
    results = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)

    for row in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        if len(cells) < 2:
            continue

        # 順位を探す
        first_cell = re.sub(r'<[^>]+>', '', cells[0]).strip().rstrip('.')
        if not first_cell or not first_cell.replace('-', '').isdigit():
            continue

        placement = int(first_cell.split('-')[0])

        # チーム名
        team_name = None
        for cell in cells[1:3]:
            hl_match = re.search(r'data-highlightingclass="([^"]+)"', cell)
            if hl_match:
                team_name = hl_match.group(1)
                break
            link_match = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', cell)
            if link_match:
                candidate = link_match.group(1)
                if candidate and not candidate.startswith('File:'):
                    team_name = candidate
                    break

        if not team_name:
            continue

        # ポイント（"Total"列 = 通常3列目）
        total_points = None
        for cell in cells[2:4]:
            cell_text = re.sub(r'<[^>]+>', '', cell).strip()
            if cell_text.isdigit() and int(cell_text) > 0:
                total_points = int(cell_text)
                break

        results.append({
            "placement": placement,
            "team_name": team_name,
            "total_points": total_points,
        })

    return results


def parse_prize_pool_from_html(html):
    """HTMLからPrize Poolセクションの結果を抽出"""
    results = []

    # Prize Pool表: class="prizepooltable"
    # 各行: placement, team, prize
    prize_sections = re.findall(
        r'<div[^>]*class="[^"]*prizepooltable[^"]*"[^>]*>(.*?)</div>\s*(?:</div>)',
        html, re.DOTALL
    )

    if not prize_sections:
        return results

    for section in prize_sections:
        rows = re.findall(r'<div[^>]*class="[^"]*csstable-widget-row[^"]*"[^>]*>(.*?)</div>\s*</div>', section, re.DOTALL)
        for row in rows:
            # 順位
            place_match = re.search(r'<div[^>]*class="[^"]*prizepooltable-place[^"]*"[^>]*>(.*?)</div>', row, re.DOTALL)
            if not place_match:
                continue
            place_text = re.sub(r'<[^>]+>', '', place_match.group(1)).strip()
            if not place_text or not place_text[0].isdigit():
                continue
            placement = int(re.match(r'(\d+)', place_text).group(1))

            # チーム名
            team_match = re.search(r'data-highlightingclass="([^"]+)"', row)
            if not team_match:
                team_link = re.search(r'<a[^>]*title="([^"]+)"', row)
                if team_link:
                    team_name = team_link.group(1)
                else:
                    continue
            else:
                team_name = team_match.group(1)

            # 賞金
            prize_match = re.search(r'\$[\d,]+', row)
            prize_usd = None
            if prize_match:
                prize_usd = int(prize_match.group().replace('$', '').replace(',', ''))

            results.append({
                "placement": placement,
                "team_name": team_name,
                "prize_usd": prize_usd,
            })

    return results


def match_team(team_name, teams_by_norm):
    """チーム名マッチング（複数戦略）"""
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]

    # 括弧除去
    clean = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
    cn = normalize_name(clean)
    if cn and cn in teams_by_norm:
        return teams_by_norm[cn]

    # "Team " プレフィックス
    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + team_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]

    # サフィックス除去
    for suffix in [" esports", " gaming", " e-sports", " esport", " gg"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("Year 1-4 大会結果取得（Wayback Machine経由）")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # DB既存データ
    print("--- DB既存データ取得 ---")
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

    tournament_slugs = {t["slug"] for t in existing_tournaments}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)}")

    # 大会ごとに処理
    stats = {"created": 0, "skipped": 0, "results": 0, "matched": 0, "unmatched": 0}
    unmatched_teams = {}

    for tdef in TOURNAMENTS:
        name = tdef["name"]
        slug = make_slug(name)
        print(f"\n--- {name} ---")

        if slug in tournament_slugs:
            print("  既にDB登録済み。スキップ")
            stats["skipped"] += 1
            continue

        # Wayback Machineから取得
        html = get_wayback_snapshot(tdef["lp_path"], tdef["wb_after"])
        if not html:
            print("  HTML取得失敗")
            continue

        print(f"  HTML: {len(html)}文字")

        # 結果パース（2つの方法を試す）
        results = parse_standings_from_html(html)
        if not results:
            results = parse_prize_pool_from_html(html)
        if not results:
            print("  結果パース失敗")
            # デバッグ: テーブルを探索
            tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
            team_tables = []
            for i, t in enumerate(tables):
                team_refs = re.findall(r'data-highlightingclass="([^"]+)"', t)
                if team_refs:
                    team_tables.append((i, len(set(team_refs)), set(team_refs)))
            if team_tables:
                print(f"  チーム名を含むテーブル:")
                for idx, count, names in sorted(team_tables, key=lambda x: -x[1])[:3]:
                    print(f"    テーブル{idx}: {count}チーム: {list(names)[:5]}")
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

        # 大会DB登録
        tourney_data = {
            "name": name,
            "slug": slug,
            "series": tdef["series"],
            "event_type": tdef["event_type"],
            "region": tdef["region"],
            "start_date": tdef["start_date"],
            "end_date": tdef["end_date"],
            "is_lan": tdef.get("is_lan", False),
            "location": tdef.get("location"),
            "prize_pool_usd": tdef.get("prize_pool_usd"),
            "status": "completed",
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{tdef['lp_path']}",
        }
        created = supabase_insert("tournaments", [tourney_data])
        if not created:
            print("  大会登録失敗")
            continue

        tournament_id = created[0]["id"]
        tournament_slugs.add(slug)
        stats["created"] += 1

        # 結果DB登録
        to_insert = []
        for r in results:
            team = match_team(r["team_name"], teams_by_norm)
            if team:
                stats["matched"] += 1
                to_insert.append({
                    "tournament_id": tournament_id,
                    "team_id": team["id"],
                    "placement": r["placement"],
                    "prize_usd": r.get("prize_usd"),
                    "total_points": r.get("total_points"),
                })
            else:
                stats["unmatched"] += 1
                unmatched_teams[r["team_name"]] = unmatched_teams.get(r["team_name"], 0) + 1

        if to_insert:
            inserted = supabase_insert("tournament_results", to_insert)
            count = len(inserted) if inserted else 0
            stats["results"] += count
            print(f"  結果登録: {count}件")

    # レポート
    print("\n" + "=" * 60)
    print("結果レポート")
    print("=" * 60)
    print(f"  大会新規登録: {stats['created']}")
    print(f"  大会スキップ: {stats['skipped']}")
    print(f"  結果登録: {stats['results']}件")
    print(f"  チームマッチ: {stats['matched']}")
    print(f"  チーム未マッチ: {stats['unmatched']}")

    if unmatched_teams:
        print(f"\n--- 未マッチチーム ---")
        for name, count in sorted(unmatched_teams.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}回")


if __name__ == "__main__":
    main()
