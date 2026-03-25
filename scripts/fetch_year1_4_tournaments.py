"""
Liquipedia から Year 1〜4 の主要ALGS大会結果を取得
→ tournaments + tournament_results テーブルに投入

使い方:
  python fetch_year1_4_tournaments.py          # 全大会取得
  python fetch_year1_4_tournaments.py --dry-run  # DB更新なし
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

# === Year 1〜4 主要大会リスト ===
# Liquipediaページ名 → 大会メタデータ
TOURNAMENTS = [
    # Year 1 (2020-21)
    {
        "lp_page": "Apex_Legends_Global_Series/2021/Championship/North_America",
        "name": "ALGS Year 1 Championship - North America",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "NA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2021/Championship/EMEA",
        "name": "ALGS Year 1 Championship - EMEA",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "EMEA",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2021/Championship/APAC_North",
        "name": "ALGS Year 1 Championship - APAC North",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_N",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2021/Championship/APAC_South",
        "name": "ALGS Year 1 Championship - APAC South",
        "series": "ALGS Year 1",
        "event_type": "championship",
        "region": "APAC_S",
        "start_date": "2021-06-06",
        "end_date": "2021-06-13",
        "is_lan": False,
    },
    # Year 2 (2021-22)
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Championship",
        "name": "ALGS Year 2 Championship",
        "series": "ALGS Year 2",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2022-07-07",
        "end_date": "2022-07-10",
        "is_lan": True,
        "location": "Raleigh, USA",
        "prize_pool_usd": 2000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Playoffs/North_America",
        "name": "ALGS Year 2 Playoffs - North America",
        "series": "ALGS Year 2",
        "event_type": "playoffs",
        "region": "NA",
        "start_date": "2022-04-29",
        "end_date": "2022-05-01",
        "is_lan": True,
        "location": "Stockholm, Sweden",
        "prize_pool_usd": 1000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/North_America",
        "name": "ALGS Year 2 Split 1 Pro League - NA",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 2 Split 1 Pro League - EMEA",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 2 Split 1 Pro League - APAC North",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2022/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 2 Split 1 Pro League - APAC South",
        "series": "ALGS Year 2",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2021-10-06",
        "end_date": "2022-01-23",
        "is_lan": False,
    },
    # Year 3 (2022-23)
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Championship",
        "name": "ALGS Year 3 Championship",
        "series": "ALGS Year 3",
        "event_type": "championship",
        "region": "GLOBAL",
        "start_date": "2023-09-06",
        "end_date": "2023-09-10",
        "is_lan": True,
        "location": "Birmingham, UK",
        "prize_pool_usd": 2000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_1/Playoffs",
        "name": "ALGS Year 3 Split 1 Playoffs",
        "series": "ALGS Year 3",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2023-02-02",
        "end_date": "2023-02-05",
        "is_lan": True,
        "location": "London, UK",
        "prize_pool_usd": 1000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_2/Playoffs",
        "name": "ALGS Year 3 Split 2 Playoffs",
        "series": "ALGS Year 3",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2023-06-01",
        "end_date": "2023-06-04",
        "is_lan": True,
        "location": "Miyazaki, Japan",
        "prize_pool_usd": 1000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/North_America",
        "name": "ALGS Year 3 Split 1 Pro League - NA",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 3 Split 1 Pro League - EMEA",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 3 Split 1 Pro League - APAC North",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2023/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 3 Split 1 Pro League - APAC South",
        "series": "ALGS Year 3",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2022-10-08",
        "end_date": "2023-01-22",
        "is_lan": False,
    },
    # Year 4 (2023-25)
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_1/Playoffs",
        "name": "ALGS Year 4 Split 1 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-03-28",
        "end_date": "2024-03-31",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_2/Playoffs",
        "name": "ALGS Year 4 Split 2 Playoffs",
        "series": "ALGS Year 4",
        "event_type": "playoffs",
        "region": "GLOBAL",
        "start_date": "2024-09-12",
        "end_date": "2024-09-15",
        "is_lan": True,
        "location": "Los Angeles, USA",
        "prize_pool_usd": 1000000,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/North_America",
        "name": "ALGS Year 4 Split 1 Pro League - NA",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "NA",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/EMEA",
        "name": "ALGS Year 4 Split 1 Pro League - EMEA",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "EMEA",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/APAC_North",
        "name": "ALGS Year 4 Split 1 Pro League - APAC North",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "APAC_N",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
    },
    {
        "lp_page": "Apex_Legends_Global_Series/2025/Split_1/Pro_League/APAC_South",
        "name": "ALGS Year 4 Split 1 Pro League - APAC South",
        "series": "ALGS Year 4",
        "event_type": "pro_league",
        "region": "APAC_S",
        "start_date": "2023-11-25",
        "end_date": "2024-03-03",
        "is_lan": False,
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

    try:
        resp = lp_client.get(LP_API, params=params)
    except Exception as e:
        print(f"    HTTPエラー: {e}")
        return None

    if resp.status_code == 429:
        # 段階的バックオフ（60秒→120秒→180秒）
        for wait in [60, 120, 180]:
            print(f"    レート制限。{wait}秒待機...")
            time.sleep(wait)
            try:
                resp = lp_client.get(LP_API, params=params)
                if resp.status_code != 429:
                    break
            except Exception as e:
                print(f"    リトライ失敗: {e}")
                return None

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


def parse_prize_pool(wikitext):
    """{{TeamPrizePool}} から順位とチーム名を抽出"""
    results = []

    # TeamPrizePoolブロックを探す
    # {{Slot|...}} を順番に取得
    slot_pattern = r"\{\{Slot\s*\|([^}]*(?:\{\{[^}]*\}\}[^}]*)*)\}\}"
    slots = re.findall(slot_pattern, wikitext)

    placement = 0
    for slot_content in slots:
        placement += 1

        # チーム名を抽出: {{Opponent|team_name}} or {{Opponent|team_name|...}}
        opponent_match = re.search(r"\{\{Opponent\|([^|}]+)", slot_content)
        if not opponent_match:
            continue
        team_name = opponent_match.group(1).strip()

        # 賞金
        prize_match = re.search(r"usdprize\s*=\s*([\d,]+)", slot_content)
        prize_usd = int(prize_match.group(1).replace(",", "")) if prize_match else None

        # ポイント
        points_match = re.search(r"points\d?\s*=\s*([\d,]+)", slot_content)
        points = int(points_match.group(1).replace(",", "")) if points_match else None

        # 同着（place=X-Yパターン）
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


def match_team(team_name, teams_by_norm):
    """チーム名マッチング"""
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
    for suffix in [" esports", " gaming", " e-sports", " esport", " gg"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]

    return None


def main():
    parser = argparse.ArgumentParser(description="Year 1-4 大会結果取得")
    parser.add_argument("--dry-run", action="store_true", help="DB更新なし")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia Year 1-4 大会結果取得")
    print("=" * 60)

    if args.dry_run:
        print("DRY-RUN モード")

    # 既存データ取得
    print("\n--- 既存データ取得 ---")
    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_tournaments = supabase_get("tournaments", {"select": "id,name,slug"})

    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        # サフィックス除去バリエーション
        name = t["name"]
        if name.lower().startswith("team "):
            teams_by_norm[normalize_name(name[5:])] = t
        for sfx in [" esports", " gaming", " e-sports"]:
            if name.lower().endswith(sfx):
                teams_by_norm[normalize_name(name[:len(name) - len(sfx)])] = t

    tournament_slugs = {t["slug"] for t in existing_tournaments}
    print(f"  チーム: {len(existing_teams)} / 大会: {len(existing_tournaments)}")

    # 大会ごとに処理
    stats = {
        "tournaments_created": 0,
        "tournaments_skipped": 0,
        "results_created": 0,
        "team_matched": 0,
        "team_unmatched": 0,
    }
    unmatched_teams = {}

    for tourney_def in TOURNAMENTS:
        print(f"\n--- {tourney_def['name']} ---")
        slug = make_slug(tourney_def["name"])

        # 既存チェック
        if slug in tournament_slugs:
            print(f"  既にDB登録済み。スキップ")
            stats["tournaments_skipped"] += 1
            continue

        # Liquipediaから取得
        page = fetch_lp_page(tourney_def["lp_page"])
        if not page:
            # リダイレクト対応: 別のページ名パターンを試す
            alt_pages = [
                tourney_def["lp_page"].replace("_", " "),
            ]
            for alt in alt_pages:
                page = fetch_lp_page(alt)
                if page:
                    break
            if not page:
                print(f"  ページ取得失敗")
                time.sleep(5)
                continue

        time.sleep(10)  # レート制限対策

        # 結果パース
        results = parse_prize_pool(page["wikitext"])
        print(f"  結果: {len(results)}チーム")

        if not results:
            print(f"  結果データなし（テンプレート形式が異なる可能性）")
            # wikitext冒頭を出力してデバッグ
            print(f"  wikitext冒頭: {page['wikitext'][:500]}")
            continue

        if args.dry_run:
            for r in results[:5]:
                team = match_team(r["team_name"], teams_by_norm)
                status = "MATCH" if team else "MISS"
                print(f"    {r['placement']:3d}位 | {status} | {r['team_name']:30s} | ${r.get('prize_usd') or 0:>10,}")
            if len(results) > 5:
                print(f"    ... 他 {len(results) - 5}チーム")
            stats["tournaments_skipped"] += 1
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
            "liquipedia_url": f"https://liquipedia.net/apexlegends/{tourney_def['lp_page']}",
        }
        created = supabase_insert("tournaments", [tourney_data])
        if not created:
            print(f"  大会登録失敗")
            continue

        tournament_id = created[0]["id"]
        tournament_slugs.add(slug)
        stats["tournaments_created"] += 1
        print(f"  大会登録: {tourney_def['name']} (ID: {tournament_id})")

        # 結果をDB登録
        results_to_insert = []
        for r in results:
            team = match_team(r["team_name"], teams_by_norm)
            if team:
                stats["team_matched"] += 1
                results_to_insert.append({
                    "tournament_id": tournament_id,
                    "team_id": team["id"],
                    "placement": r["placement"],
                    "prize_usd": r.get("prize_usd"),
                    "total_points": r.get("total_points"),
                })
            else:
                stats["team_unmatched"] += 1
                unmatched_teams[r["team_name"]] = unmatched_teams.get(r["team_name"], 0) + 1

        if results_to_insert:
            inserted = supabase_insert("tournament_results", results_to_insert)
            stats["results_created"] += len(inserted) if inserted else 0
            print(f"  結果登録: {len(inserted) if inserted else 0}件")

    # レポート
    print("\n" + "=" * 60)
    print("結果レポート")
    print("=" * 60)
    print(f"  大会新規登録: {stats['tournaments_created']}")
    print(f"  大会スキップ: {stats['tournaments_skipped']}")
    print(f"  結果登録: {stats['results_created']}件")
    print(f"  チームマッチ: {stats['team_matched']}")
    print(f"  チーム未マッチ: {stats['team_unmatched']}")

    if unmatched_teams:
        print(f"\n--- 未マッチチーム ---")
        for name, count in sorted(unmatched_teams.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}回")


if __name__ == "__main__":
    main()
