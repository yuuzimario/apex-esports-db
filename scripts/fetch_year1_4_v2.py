"""
Liquipedia から Year 1〜4 の不足ALGS大会結果を取得
→ tournaments + tournament_results テーブルに投入

修正版: 正しいLiquipediaページ名マッピング + 誤ラベル修正 + 2フォーマット対応

使い方:
  python fetch_year1_4_v2.py --dry-run    # DB更新なし（推奨: まず確認）
  python fetch_year1_4_v2.py              # 本番実行
  python fetch_year1_4_v2.py --fix-labels # 既存の誤ラベルを修正（Year 2 Split 1 → Year 3 Split 1）
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

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
lp_client = httpx.Client(timeout=30, headers=LP_HEADERS)

# リクエスト間隔（秒）— IPブロック防止
REQUEST_DELAY = 5

# === 正確なLiquipediaページマッピング ===
# 検証済み: 各ページのDISPLAYTITLEと日付を確認済み
REGIONS = ["North America", "EMEA", "APAC North", "APAC South"]
REGION_MAP = {"North America": "NA", "EMEA": "EMEA", "APAC North": "APAC_N", "APAC South": "APAC_S"}
# DB表示用の名前（既存エントリと一致させる）
REGION_DISPLAY = {"North America": "NA", "EMEA": "EMEA", "APAC North": "APAC North", "APAC South": "APAC South"}

TOURNAMENTS = []

# --- Year 1 (2020-21): Championship のみ（既にDB登録済み。スキップされる） ---
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/Championship/{region}/2021",
        "name": f"ALGS Year 1 Championship - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": REGION_MAP[region],
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    })

# --- Year 2 (2021-22) ---
# Split 1 Pro League: 2021/Split 1/ (日付: 2021-10〜12)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2021/Split 1/Pro League/{region}",
        "sub_page": f"Apex Legends Global Series/2021/Split 1/Pro League/{region}/Regular Season",
        "name": f"ALGS Year 2 Split 1 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2021-10-16",
        "end_date": "2021-12-05",
        "is_lan": False,
        "prize_pool_usd": 125000,
    })

# Split 2 Pro League: 2022/Split 2/ (日付: 2022-03)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2022/Split 2/Pro League/{region}",
        "sub_page": f"Apex Legends Global Series/2022/Split 2/Pro League/{region}/Regular Season",
        "name": f"ALGS Year 2 Split 2 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2022-03-12",
        "end_date": "2022-04-24",
        "is_lan": False,
    })

# Split 2 Playoffs: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2022/Split 2/Playoffs",
    "name": "ALGS Year 2 Split 2 Playoffs",
    "series": "ALGS Year 2",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2022-05-05",
    "end_date": "2022-05-08",
    "is_lan": True,
    "location": "Stockholm, Sweden",
    "prize_pool_usd": 1000000,
})

# Championship: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2022/Championship",
    "name": "ALGS Year 2 Championship",
    "series": "ALGS Year 2",
    "event_type": "championship",
    "region": "GLOBAL",
    "start_date": "2022-07-07",
    "end_date": "2022-07-10",
    "is_lan": True,
    "location": "Raleigh, USA",
    "prize_pool_usd": 2000000,
})

# --- Year 3 (2022-23) ---
# Split 1 Pro League: 2022/Split 1/ (DISPLAYTITLE: 2022-23、日付: 2022-11〜12)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2022/Split 1/Pro League/{region}",
        "name": f"ALGS Year 3 Split 1 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2022-11-06",
        "end_date": "2022-12-18",
        "is_lan": False,
    })

# Split 2 Pro League: 2023/Split 2/ (日付: 2023-03〜05)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2023/Split 2/Pro League/{region}",
        "name": f"ALGS Year 3 Split 2 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2023-03-11",
        "end_date": "2023-05-08",
        "is_lan": False,
    })

# Split 1 Playoffs: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2023/Split 1/Playoffs",
    "name": "ALGS Year 3 Split 1 Playoffs",
    "series": "ALGS Year 3",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2023-02-02",
    "end_date": "2023-02-05",
    "is_lan": True,
    "location": "London, UK",
    "prize_pool_usd": 1000000,
})

# Split 2 Playoffs: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2023/Split 2/Playoffs",
    "name": "ALGS Year 3 Split 2 Playoffs",
    "series": "ALGS Year 3",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2023-06-01",
    "end_date": "2023-06-04",
    "is_lan": True,
    "location": "Miyazaki, Japan",
    "prize_pool_usd": 1000000,
})

# Championship: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2023/Championship",
    "name": "ALGS Year 3 Championship",
    "series": "ALGS Year 3",
    "event_type": "championship",
    "region": "GLOBAL",
    "start_date": "2023-09-06",
    "end_date": "2023-09-10",
    "is_lan": True,
    "location": "Birmingham, UK",
    "prize_pool_usd": 2000000,
})

# --- Year 4 (2023-25) ---
# Split 1 Pro League: 2024/Split 1/ (日付: 2024-01〜03)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2024/Split 1/Pro League/{region}",
        "name": f"ALGS Year 4 Split 1 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2024-01-21",
        "end_date": "2024-03-25",
        "is_lan": False,
    })

# Split 2 Pro League: 2024/Split 2/ (日付: 2024-06〜07)
for region in REGIONS:
    TOURNAMENTS.append({
        "lp_page": f"Apex Legends Global Series/2024/Split 2/Pro League/{region}",
        "name": f"ALGS Year 4 Split 2 Pro League - {REGION_DISPLAY[region]}",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": REGION_MAP[region],
        "start_date": "2024-06-01",
        "end_date": "2024-07-14",
        "is_lan": False,
    })

# Split 1 Playoffs: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2024/Split 1/Playoffs",
    "name": "ALGS Year 4 Split 1 Playoffs",
    "series": "ALGS Year 4",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2024-03-28",
    "end_date": "2024-03-31",
    "is_lan": True,
    "location": "Los Angeles, USA",
    "prize_pool_usd": 1000000,
})

# Split 2 Playoffs: 既にDB登録済み
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2024/Split 2/Playoffs",
    "name": "ALGS Year 4 Split 2 Playoffs",
    "series": "ALGS Year 4",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2024-09-12",
    "end_date": "2024-09-15",
    "is_lan": True,
    "location": "Los Angeles, USA",
    "prize_pool_usd": 1000000,
})

# Championship
TOURNAMENTS.append({
    "lp_page": "Apex Legends Global Series/2025/Championship",
    "name": "ALGS Year 4 Championship",
    "series": "ALGS Year 4",
    "event_type": "championship",
    "region": "GLOBAL",
    "start_date": "2025-01-23",
    "end_date": "2025-01-26",
    "is_lan": True,
    "location": "Riyadh, Saudi Arabia",
    "prize_pool_usd": 2000000,
})


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
    limit = 1000
    while True:
        p = {**(params or {}), "limit": str(limit), "offset": str(offset)}
        resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            print(f"  GET エラー ({table}): {resp.status_code}: {resp.text[:200]}")
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_data


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def supabase_update(table, id_val, data):
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params={"id": f"eq.{id_val}"},
        json=data,
        headers=headers,
    )
    if resp.status_code not in (200, 204):
        print(f"  UPDATE エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return False
    return True


def fetch_lp_page(page_title):
    """Liquipediaページのwikitextを取得（キャッシュ付き）"""
    safe_name = page_title.replace("/", "_").replace(" ", "_")
    cache_file = os.path.join(CACHE_DIR, f"lp_{safe_name}.json")

    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if (time.time() - mtime) < 86400 * 7:  # 7日キャッシュ
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    print(f"    Liquipedia取得: {page_title}")
    params = {
        "action": "query",
        "titles": page_title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }

    for attempt in range(3):
        try:
            resp = lp_client.get(LP_API, params=params)
        except Exception as e:
            print(f"    HTTPエラー: {e}")
            time.sleep(30)
            continue

        if resp.status_code == 429:
            wait = 60 * (attempt + 1)
            print(f"    レート制限。{wait}秒待機...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"    HTTPエラー: {resp.status_code}")
            return None

        data = resp.json()
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_data in pages.items():
            if page_id == "-1":
                print(f"    ページなし: {page_title}")
                return None
            revisions = page_data.get("revisions", [])
            if revisions:
                wikitext = revisions[0].get("*", "")
                result = {"title": page_title, "wikitext": wikitext}
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False)
                return result
        return None

    return None


def parse_prize_pool(wikitext):
    """{{TeamPrizePool}} + {{Slot}} から順位とチーム名を抽出"""
    results = []

    slot_pattern = r"\{\{Slot\s*\|([^}]*(?:\{\{[^}]*\}\}[^}]*)*)\}\}"
    slots = re.findall(slot_pattern, wikitext)

    placement = 0
    for slot_content in slots:
        placement += 1

        opponent_match = re.search(r"\{\{Opponent\|([^|}]+)", slot_content)
        if not opponent_match:
            continue
        team_name = opponent_match.group(1).strip()

        prize_match = re.search(r"usdprize\s*=\s*([\d,]+)", slot_content)
        prize_usd = int(prize_match.group(1).replace(",", "")) if prize_match else None

        points_match = re.search(r"points\d?\s*=\s*([\d,]+)", slot_content)
        points = int(points_match.group(1).replace(",", "")) if points_match else None

        place_match = re.search(r"place\s*=\s*(\d+)(?:-(\d+))?", slot_content)
        if place_match:
            placement = int(place_match.group(1))

        results.append({
            "placement": placement,
            "team_name": team_name,
            "prize_usd": prize_usd,
            "total_points": points,
        })

    return results


def parse_league_standings(wikitext):
    """{{League standings}} から順位とチーム名を抽出（ラウンドポイント合計）"""
    results = []

    # team1=TSM |standings1= 4,5,5,9,3,7 パターン
    team_pattern = r"\|team(\d+)\s*=\s*([^|\n]+)"
    standings_pattern = r"\|standings(\d+)\s*=\s*([^|\n]+)"

    teams = {}
    for m in re.finditer(team_pattern, wikitext):
        idx = int(m.group(1))
        name = m.group(2).strip()
        teams[idx] = {"name": name, "points": 0}

    for m in re.finditer(standings_pattern, wikitext):
        idx = int(m.group(1))
        standings_str = m.group(2).strip()
        # ポイントを合計（- はDQ/欠場を表す）
        total = 0
        for val in standings_str.split(","):
            val = val.strip()
            if val and val != "-":
                try:
                    total += int(val)
                except ValueError:
                    pass
        if idx in teams:
            teams[idx]["points"] = total

    # ポイント降順でソート → 順位割り当て
    sorted_teams = sorted(teams.items(), key=lambda x: -x[1]["points"])
    for rank, (idx, data) in enumerate(sorted_teams, 1):
        results.append({
            "placement": rank,
            "team_name": data["name"],
            "prize_usd": None,
            "total_points": data["points"],
        })

    return results


def parse_results(wikitext):
    """wikitextから結果を抽出（フォーマット自動判定）"""
    # まず TeamPrizePool + Slot を試す
    if "TeamPrizePool" in wikitext or ("{{Slot" in wikitext and "Opponent" in wikitext):
        results = parse_prize_pool(wikitext)
        if results:
            return results, "PrizePool"

    # League standings フォーマット
    if "League standings" in wikitext and "|team1=" in wikitext:
        results = parse_league_standings(wikitext)
        if results:
            return results, "LeagueStandings"

    return [], "Unknown"


def match_team(team_name, teams_by_norm):
    """チーム名マッチング（複数パターン対応）"""
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]

    # 括弧除去
    clean = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
    cn = normalize_name(clean)
    if cn and cn in teams_by_norm:
        return teams_by_norm[cn]

    # "Team "プレフィックス
    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + team_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]

    # サフィックス除去
    for suffix in [" esports", " gaming", " e-sports", " esport", " gg", " club"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]
        # サフィックスを追加して試す
        added = normalize_name(team_name + suffix)
        if added in teams_by_norm:
            return teams_by_norm[added]

    return None


def fix_mislabeled_tournaments(dry_run=False):
    """誤ラベル修正: DBの Year 2 Split 1 Pro League → Year 3 Split 1 Pro League

    理由: 元のスクリプトが Liquipedia の 2022/Split 1/ ページ（実際は2022-23シーズン = Year 3）を
    Year 2 として登録してしまった。実際の日付は2022年11月〜12月（Year 3のSplit 1期間）。
    """
    print("\n" + "=" * 60)
    print("誤ラベル修正: Year 2 Split 1 → Year 3 Split 1")
    print("=" * 60)

    tournaments = supabase_get("tournaments", {
        "select": "id,name,slug,series,start_date,end_date",
        "series": "eq.ALGS Year 2",
        "event_type": "eq.pro_league",
    })

    fixed = 0
    for t in tournaments:
        if "Split 1 Pro League" not in t["name"]:
            continue

        # リージョンを検出
        region_display = "NA"
        lp_region = "North America"
        for display, lp in [("APAC North", "APAC North"), ("APAC South", "APAC South"), ("EMEA", "EMEA"), ("NA", "North America")]:
            if display in t["name"] or (display == "NA" and t["name"].endswith("- NA")):
                region_display = display
                lp_region = lp
                break

        # Year 3の名前に変更
        new_name = t["name"].replace("Year 2", "Year 3")
        new_slug = make_slug(new_name)

        print(f"  {t['name']}")
        print(f"    → {new_name}")
        print(f"    旧日付: {t['start_date']} → {t['end_date']}")
        print(f"    新日付: 2022-11-06 → 2022-12-18")

        if not dry_run:
            supabase_update("tournaments", t["id"], {
                "name": new_name,
                "slug": new_slug,
                "series": "ALGS Year 3",
                "start_date": "2022-11-06",
                "end_date": "2022-12-18",
                "liquipedia_url": f"https://liquipedia.net/apexlegends/Apex_Legends_Global_Series/2022/Split_1/Pro_League/{lp_region.replace(' ', '_')}",
            })
            print(f"    更新完了")
        fixed += 1

    print(f"\n修正: {fixed}件")
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Year 1-4 大会結果取得 v2")
    parser.add_argument("--dry-run", action="store_true", help="DB更新なし")
    parser.add_argument("--fix-labels", action="store_true", help="誤ラベルのみ修正")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia Year 1-4 大会結果取得 v2")
    print("=" * 60)

    if args.dry_run:
        print("DRY-RUN モード")

    # 誤ラベル修正
    if args.fix_labels:
        fix_mislabeled_tournaments(dry_run=args.dry_run)
        return

    # 既存データ取得
    print("\n--- 既存データ取得 ---")
    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get("tournaments", {"select": "id,name,slug,series"})

    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        name = t["name"]
        if name.lower().startswith("team "):
            teams_by_norm[normalize_name(name[5:])] = t
        for sfx in [" esports", " gaming", " e-sports", " esport"]:
            if name.lower().endswith(sfx):
                teams_by_norm[normalize_name(name[:len(name) - len(sfx)])] = t

    tournament_names = {t["name"] for t in existing_tournaments}
    tournament_slugs = {t["slug"] for t in existing_tournaments}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)}")

    # 不足大会のみフィルタ
    missing = []
    for t in TOURNAMENTS:
        slug = make_slug(t["name"])
        if t["name"] in tournament_names or slug in tournament_slugs:
            continue
        missing.append(t)

    print(f"\n--- 不足大会: {len(missing)}件 ---")
    for t in missing:
        print(f"  {t['name']}")

    if not missing:
        print("\n全大会が登録済みです。")
        return

    # 大会ごとに処理
    stats = {
        "tournaments_created": 0,
        "results_created": 0,
        "team_matched": 0,
        "team_unmatched": 0,
        "lp_requests": 0,
    }
    unmatched_teams = {}

    for tourney_def in missing:
        print(f"\n{'='*50}")
        print(f"--- {tourney_def['name']} ---")
        slug = make_slug(tourney_def["name"])

        # Liquipediaから取得
        page = fetch_lp_page(tourney_def["lp_page"])
        stats["lp_requests"] += 1
        if not page:
            print(f"  ページ取得失敗: {tourney_def['lp_page']}")
            time.sleep(REQUEST_DELAY)
            continue

        time.sleep(REQUEST_DELAY)

        # 結果パース
        results, fmt = parse_results(page["wikitext"])
        print(f"  結果: {len(results)}チーム (フォーマット: {fmt})")

        # メインページに結果がない場合、サブページ（Regular Season）を試す
        if not results and tourney_def.get("sub_page"):
            print(f"  サブページを試す: {tourney_def['sub_page']}")
            sub_page = fetch_lp_page(tourney_def["sub_page"])
            stats["lp_requests"] += 1
            if sub_page:
                results, fmt = parse_results(sub_page["wikitext"])
                print(f"  サブページ結果: {len(results)}チーム (フォーマット: {fmt})")
            time.sleep(REQUEST_DELAY)

        if not results:
            print(f"  結果データなし")
            print(f"  wikitext冒頭: {page['wikitext'][:300]}")
            continue

        # チームマッチング
        matched_results = []
        for r in results:
            team = match_team(r["team_name"], teams_by_norm)
            if team:
                stats["team_matched"] += 1
                matched_results.append({
                    **r,
                    "team_id": team["id"],
                    "team_db_name": team["name"],
                })
            else:
                stats["team_unmatched"] += 1
                unmatched_teams[r["team_name"]] = unmatched_teams.get(r["team_name"], 0) + 1

        # dry-run 表示
        if args.dry_run:
            for r in results[:10]:
                team = match_team(r["team_name"], teams_by_norm)
                status = "MATCH" if team else "MISS "
                db_name = f" → {team['name']}" if team else ""
                print(f"    {r['placement']:3d}位 | {status} | {r['team_name']:30s} | pts:{r.get('total_points') or '-':>5} | ${r.get('prize_usd') or 0:>8,}{db_name}")
            if len(results) > 10:
                print(f"    ... 他 {len(results) - 10}チーム")
            matched = sum(1 for r in results if match_team(r["team_name"], teams_by_norm))
            print(f"  マッチ率: {matched}/{len(results)} ({matched*100//len(results)}%)")
            continue

        # 大会をDB登録
        tourney_data = {
            "name": tourney_def["name"],
            "slug": slug,
            "series": tourney_def["series"],
            "event_type": tourney_def["event_type"],
            "region": tourney_def["region"],
            "start_date": tourney_def["start_date"],
            "end_date": tourney_def["end_date"],
            "is_lan": tourney_def.get("is_lan", False),
            "location": tourney_def.get("location"),
            "prize_pool_usd": tourney_def.get("prize_pool_usd"),
            "status": "completed",
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{tourney_def['lp_page'].replace(' ', '_')}",
        }
        created = supabase_insert("tournaments", [tourney_data])
        if not created:
            print(f"  大会登録失敗")
            continue

        tournament_id = created[0]["id"]
        stats["tournaments_created"] += 1
        print(f"  大会登録: {tourney_def['name']}")

        # 結果をDB登録
        results_to_insert = []
        for r in matched_results:
            results_to_insert.append({
                "tournament_id": tournament_id,
                "team_id": r["team_id"],
                "placement": r["placement"],
                "prize_usd": r.get("prize_usd"),
                "total_points": r.get("total_points"),
            })

        if results_to_insert:
            inserted = supabase_insert("tournament_results", results_to_insert)
            count = len(inserted) if inserted else 0
            stats["results_created"] += count
            print(f"  結果登録: {count}件 / {len(results)}チーム中{len(matched_results)}マッチ")

    # レポート
    print("\n" + "=" * 60)
    print("結果レポート")
    print("=" * 60)
    print(f"  大会新規登録: {stats['tournaments_created']}")
    print(f"  結果登録: {stats['results_created']}件")
    print(f"  チームマッチ: {stats['team_matched']}")
    print(f"  チーム未マッチ: {stats['team_unmatched']}")
    print(f"  Liquipediaリクエスト: {stats['lp_requests']}")

    if unmatched_teams:
        print(f"\n--- 未マッチチーム (DBに登録なし) ---")
        for name, count in sorted(unmatched_teams.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}回")


if __name__ == "__main__":
    main()
