"""
Liquipedia Player Transfers ページから移籍履歴を一括取得
2020 Q1 〜 2026 Q1 の全四半期ページからTransfer Rowを解析
→ team_rosters テーブルに joined_at / left_at を設定

使い方:
  python fetch_transfer_history.py          # 全期間取得
  python fetch_transfer_history.py --dry-run  # DB更新なし（確認のみ）
  python fetch_transfer_history.py --year 2025  # 特定年のみ
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

# === 設定 ===
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

# 四半期名マッピング
QUARTER_NAMES = {
    1: "1st_Quarter",
    2: "2nd_Quarter",
    3: "3rd_Quarter",
    4: "4th_Quarter",
}

# チーム名エイリアス（Liquipedia名 → DB正規化名にマッピング）
# normalize_name()済みのキーで格納
TEAM_ALIASES = {
    "complexitygaming": "complexity",
    "rejectwinnity": "reject",
    "mdy": "mdyblack",
    "evospredator": "evos",
    "mpiregaming": "mpire",
    "spacestationgaming": "spacestationgaming",  # SSGとして追加予定
    "10kclub": "10kclub",
    "obeyalliance": "alliance",
    # REJECT系
    "rejectwinnity": "reject",
    "rejectwinnityjp": "reject",
    # SCARZ系
    "scarzblack": "scarz",
    "scarzsb": "scarz",
    # その他
    "sunsistergod": "sunsister",
    "10kclub": "10kclub",
    # 大文字小文字の揺れ
    "northeption": "northeption",
    "crazyraccoon": "crazyraccoon",
    "tsm": "tsm",
    "nrg": "nrg",
    "fnatic": "fnatic",
}

# DBに追加すべき有名チーム（歴史的に重要だがDB未登録）
TEAMS_TO_ADD = [
    {"name": "Northeption", "short_name": "NTH", "region": "APAC_N", "is_active": False},
    {"name": "XSET", "short_name": "XSET", "region": "NA", "is_active": False},
    {"name": "Disguised", "short_name": "DSG", "region": "NA", "is_active": False},
    {"name": "SpaceStation Gaming", "short_name": "SSG", "region": "NA", "is_active": False},
    {"name": "Guild Esports", "short_name": "GLD", "region": "EMEA", "is_active": False},
    {"name": "Fire Beavers", "short_name": "FB", "region": "EMEA", "is_active": False},
    {"name": "ONIC Esports", "short_name": "ONIC", "region": "APAC_S", "is_active": False},
    {"name": "Bleed Esports", "short_name": "BLD", "region": "APAC_S", "is_active": False},
    {"name": "K1CK", "short_name": "K1CK", "region": "EMEA", "is_active": False},
    {"name": "IGZIST", "short_name": "IGZ", "region": "APAC_N", "is_active": False},
    {"name": "Setouchi Sparks", "short_name": "STS", "region": "APAC_N", "is_active": False},
    {"name": "Iron Blood Gaming", "short_name": "IBG", "region": "APAC_S", "is_active": False},
    {"name": "GHS Professional", "short_name": "GHS", "region": "APAC_S", "is_active": False},
    {"name": "Element 6", "short_name": "E6", "region": "NA", "is_active": False},
    {"name": "Ethernal", "short_name": "ETH", "region": "EMEA", "is_active": False},
    {"name": "o7", "short_name": "o7", "region": "NA", "is_active": False},
    {"name": "2r1c", "short_name": "2R1C", "region": "EMEA", "is_active": False},
    {"name": "New Esports", "short_name": "NEW", "region": "EMEA", "is_active": False},
    {"name": "Dno", "short_name": "DNO", "region": "EMEA", "is_active": False},
    {"name": "Phoenix Legacy", "short_name": "PL", "region": "NA", "is_active": False},
    {"name": "Lightning Unicorn", "short_name": "LU", "region": "APAC_S", "is_active": False},
    {"name": "Primis Komanda", "short_name": "PK", "region": "EMEA", "is_active": False},
    {"name": "Redragon", "short_name": "RD", "region": "NA", "is_active": False},
    {"name": "Blacklist International", "short_name": "BLCK", "region": "APAC_S", "is_active": False},
    {"name": "Vexed Gaming", "short_name": "VEX", "region": "EMEA", "is_active": False},
    {"name": "The Dojo", "short_name": "DOJO", "region": "APAC_N", "is_active": False},
    {"name": "Nessy", "short_name": "NSY", "region": "NA", "is_active": False},
    {"name": "Pulverex", "short_name": "PVX", "region": "EMEA", "is_active": False},
    {"name": "Team Intel", "short_name": "INT", "region": "EMEA", "is_active": False},
    {"name": "Ronin", "short_name": "RON", "region": "EMEA", "is_active": False},
]


def normalize_name(name):
    """名前を正規化（英数字のみ小文字）"""
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    """URL用スラッグ生成"""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


# === Supabaseヘルパー ===
def supabase_get(table, params=None):
    """Supabaseからデータ取得（ページネーション対応）"""
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
    """Supabaseにデータ挿入"""
    if not data:
        return []
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def supabase_update(table, match_col, match_val, data):
    """Supabaseのレコード更新"""
    headers = {**DB_HEADERS, "Prefer": "return=representation"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}",
        json=data,
        headers=headers,
    )
    if resp.status_code not in (200, 204):
        print(f"  UPDATE エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json() if resp.text else []


# === Liquipedia取得 ===
def fetch_transfer_page(year, quarter):
    """Liquipediaの移籍ページを取得"""
    title = f"Player_Transfers/{year}/{QUARTER_NAMES[quarter]}"
    cache_file = os.path.join(CACHE_DIR, f"transfers_{year}_q{quarter}.json")

    # キャッシュがあればそれを使う（24時間以内）
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if (time.time() - mtime) < 86400:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    print(f"  Liquipedia取得: {title}")
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }

    resp = lp_client.get(LP_API, params=params)
    if resp.status_code != 200:
        print(f"    HTTPエラー: {resp.status_code}")
        return None

    data = resp.json()
    pages = data.get("query", {}).get("pages", {})

    for page_id, page_data in pages.items():
        if page_id == "-1":
            print(f"    ページなし: {title}")
            return None
        revisions = page_data.get("revisions", [])
        if revisions:
            wikitext = revisions[0].get("*", "")
            result = {"title": title, "wikitext": wikitext}
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return result

    return None


def parse_transfer_rows(wikitext):
    """wikitextからTransfer Rowを全て解析"""
    transfers = []

    # {{Transfer Row |...}} を抽出（ネストなし前提）
    pattern = r"\{\{Transfer Row\s*\|([^}]+)\}\}"
    matches = re.findall(pattern, wikitext, re.IGNORECASE)

    for match in matches:
        row = parse_template_params(match)
        if not row.get("name"):
            continue

        # 日付パース
        date_str = row.get("date", "").strip()
        if not date_str:
            continue

        # メイン移籍レコード
        transfer = {
            "date": date_str,
            "player_name": row.get("name", "").strip().rstrip("\t"),
            "flag": row.get("flag", "").strip().lower(),
            "team_from": row.get("team1", "").strip() or None,
            "team_to": row.get("team2", "").strip() or None,
            "role_from": row.get("role1", "").strip() or None,
            "role_to": row.get("role2", "").strip() or None,
        }
        transfers.append(transfer)

        # name2, name3の処理（同一移籍の追加選手）
        for suffix in ["2", "3"]:
            name_key = f"name{suffix}"
            if row.get(name_key, "").strip():
                transfer2 = {
                    "date": date_str,
                    "player_name": row[name_key].strip().rstrip("\t"),
                    "flag": row.get(f"flag{suffix}", "").strip().lower(),
                    "team_from": row.get("team1", "").strip() or None,
                    "team_to": row.get("team2", "").strip() or None,
                    "role_from": row.get("role1", "").strip() or None,
                    "role_to": row.get("role2", "").strip() or None,
                }
                transfers.append(transfer2)

    return transfers


def parse_template_params(params_str):
    """テンプレートパラメータを辞書に変換"""
    result = {}
    # |で分割（ただしネストされたテンプレート内の|は無視）
    depth = 0
    current = ""
    for char in params_str:
        if char == "{":
            depth += 1
            current += char
        elif char == "}":
            depth -= 1
            current += char
        elif char == "|" and depth == 0:
            _parse_kv(current, result)
            current = ""
        else:
            current += char
    if current:
        _parse_kv(current, result)
    return result


def match_team(team_name, teams_by_norm):
    """チーム名マッチング（複数戦略でフォールバック）"""
    # 1. 正規化名で直接マッチ
    tn = normalize_name(team_name)
    if tn in teams_by_norm:
        return teams_by_norm[tn]

    # 2. 括弧を除去してマッチ（"ronin (british team)" → "ronin"）
    clean_name = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
    cn = normalize_name(clean_name)
    if cn and cn in teams_by_norm:
        return teams_by_norm[cn]

    # 3. "Team " プレフィックスを除去/追加してマッチ
    if team_name.lower().startswith("team "):
        short = normalize_name(team_name[5:])
        if short in teams_by_norm:
            return teams_by_norm[short]
    else:
        with_team = normalize_name("team " + team_name)
        if with_team in teams_by_norm:
            return teams_by_norm[with_team]

    # 4. " Esports" 等のサフィックスを除去してマッチ
    for suffix in [" esports", " gaming", " e-sports", " esport", " gg"]:
        if team_name.lower().endswith(suffix):
            short = normalize_name(team_name[:len(team_name) - len(suffix)])
            if short in teams_by_norm:
                return teams_by_norm[short]

    return None


def _parse_kv(s, result):
    """key=value をパース"""
    if "=" in s:
        key, _, value = s.partition("=")
        key = key.strip().lower()
        # refの中身は不要
        if key and key != "ref":
            result[key] = value.strip()


# === メイン処理 ===
def main():
    parser = argparse.ArgumentParser(description="Liquipedia移籍履歴取得")
    parser.add_argument("--dry-run", action="store_true", help="DB更新なし")
    parser.add_argument("--year", type=int, help="特定年のみ取得")
    parser.add_argument("--no-cache", action="store_true", help="キャッシュ無視")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia 移籍履歴一括取得")
    print("=" * 60)

    if args.dry_run:
        print("⚠ DRY-RUN モード（DB更新なし）")

    # --- Step 1: 全移籍データ取得 ---
    print("\n--- Step 1: Liquipediaから移籍データ取得 ---")
    all_transfers = []

    years = [args.year] if args.year else range(2020, 2027)
    for year in years:
        for quarter in range(1, 5):
            # 2026年はQ1のみ
            if year == 2026 and quarter > 1:
                continue

            if args.no_cache:
                cache_file = os.path.join(CACHE_DIR, f"transfers_{year}_q{quarter}.json")
                if os.path.exists(cache_file):
                    os.remove(cache_file)

            page = fetch_transfer_page(year, quarter)
            if page:
                transfers = parse_transfer_rows(page["wikitext"])
                print(f"    {year} Q{quarter}: {len(transfers)}件")
                all_transfers.extend(transfers)
            else:
                print(f"    {year} Q{quarter}: ページなし")

            time.sleep(2)  # レート制限

    print(f"\n  合計移籍レコード: {len(all_transfers)}件")

    # キャッシュに保存
    cache_path = os.path.join(CACHE_DIR, "all_transfers.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(all_transfers, f, ensure_ascii=False, indent=2)
    print(f"  キャッシュ保存: {cache_path}")

    # --- Step 2: 不足チームをDB追加 & 既存データ取得 ---
    print("\n--- Step 2: 不足チームDB追加 & 既存データ取得 ---")

    if not args.dry_run:
        # 既存チーム名を取得して重複チェック
        current_teams = supabase_get("teams", {"select": "name"})
        current_team_norms = {normalize_name(t["name"]) for t in current_teams}

        teams_to_insert = []
        for team_def in TEAMS_TO_ADD:
            if normalize_name(team_def["name"]) not in current_team_norms:
                teams_to_insert.append({
                    "name": team_def["name"],
                    "slug": make_slug(team_def["name"]),
                    "short_name": team_def.get("short_name"),
                    "region": team_def.get("region", "GLOBAL"),
                    "is_active": team_def.get("is_active", False),
                })

        if teams_to_insert:
            result = supabase_insert("teams", teams_to_insert)
            print(f"  新規チーム追加: {len(result)}チーム")
            for t in result:
                print(f"    + {t['name']} ({t['region']})")
        else:
            print("  追加すべき新規チームなし")

    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_players = supabase_get("players", {"select": "id,ign,slug,nationality"})
    existing_rosters = supabase_get("team_rosters", {"select": "*"})

    # インデックス構築
    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        # スラッグでも
        teams_by_norm[normalize_name(t["slug"])] = t

    # エイリアスマッピングを追加
    for alias_norm, target_norm in TEAM_ALIASES.items():
        if target_norm in teams_by_norm and alias_norm not in teams_by_norm:
            teams_by_norm[alias_norm] = teams_by_norm[target_norm]

    # Liquipedia特有の表記揺れ対応（括弧付き、"team"プレフィックス等）
    for t in existing_teams:
        name = t["name"]
        norm = normalize_name(name)
        # "Team X" → "X" の逆引き
        if name.lower().startswith("team "):
            short_norm = normalize_name(name[5:])
            if short_norm not in teams_by_norm:
                teams_by_norm[short_norm] = t
        # "X Esports" → "X" の逆引き
        for suffix in [" esports", " gaming", " e-sports", " esport"]:
            if name.lower().endswith(suffix):
                short_norm = normalize_name(name[:len(name) - len(suffix)])
                if short_norm not in teams_by_norm:
                    teams_by_norm[short_norm] = t

    players_by_norm = {}
    for p in existing_players:
        players_by_norm[normalize_name(p["ign"])] = p

    # 既存ロースターのインデックス（player_id + team_id + joined_at → 重複チェック用）
    roster_keys = set()
    for r in existing_rosters:
        key = f"{r['player_id']}_{r['team_id']}_{r.get('joined_at', '')}"
        roster_keys.add(key)

    print(f"  既存チーム: {len(existing_teams)}")
    print(f"  既存選手: {len(existing_players)}")
    print(f"  既存ロースター: {len(existing_rosters)}")
    print(f"  チーム名インデックス: {len(teams_by_norm)}エントリ")

    # --- Step 3: マッチング & DB投入 ---
    print("\n--- Step 3: マッチング & DB投入 ---")

    stats = {
        "matched_player": 0,
        "unmatched_player": 0,
        "matched_team_from": 0,
        "matched_team_to": 0,
        "unmatched_team": 0,
        "roster_created": 0,
        "roster_updated": 0,
        "skipped_existing": 0,
        "skipped_staff": 0,
    }

    unmatched_players = {}  # name -> count
    unmatched_teams = {}  # name -> count

    # スタッフ/コーチ系ロールはスキップ
    STAFF_ROLES = {"coach", "manager", "analyst", "ceo", "owner", "caster", "streamer", "content creator"}

    for transfer in all_transfers:
        player_name = transfer["player_name"]
        date_str = transfer["date"]

        # スタッフはスキップ
        role_from = (transfer.get("role_from") or "").lower()
        role_to = (transfer.get("role_to") or "").lower()
        if role_from in STAFF_ROLES and role_to in STAFF_ROLES:
            stats["skipped_staff"] += 1
            continue
        if not transfer.get("team_from") and not transfer.get("team_to"):
            # チームなし（引退等）
            stats["skipped_staff"] += 1
            continue

        # 選手マッチング
        player_norm = normalize_name(player_name)
        player = players_by_norm.get(player_norm)
        if not player:
            stats["unmatched_player"] += 1
            unmatched_players[player_name] = unmatched_players.get(player_name, 0) + 1
            continue

        stats["matched_player"] += 1

        # チームマッチング（複数戦略でフォールバック）
        team_from = None
        team_to = None

        if transfer.get("team_from"):
            team_from = match_team(transfer["team_from"], teams_by_norm)
            if team_from:
                stats["matched_team_from"] += 1
            else:
                unmatched_teams[transfer["team_from"]] = unmatched_teams.get(transfer["team_from"], 0) + 1
                stats["unmatched_team"] += 1

        if transfer.get("team_to"):
            team_to = match_team(transfer["team_to"], teams_by_norm)
            if team_to:
                stats["matched_team_to"] += 1
            else:
                unmatched_teams[transfer["team_to"]] = unmatched_teams.get(transfer["team_to"], 0) + 1
                stats["unmatched_team"] += 1

        if args.dry_run:
            continue

        # --- DB更新 ---
        # パターン1: チーム離脱（team_from あり、team_to なし or 別チーム）
        if team_from:
            # 既存ロースターでleft_atが未設定のものを探して更新
            for r in existing_rosters:
                if (r["player_id"] == player["id"]
                        and r["team_id"] == team_from["id"]
                        and r.get("left_at") is None):
                    supabase_update("team_rosters", "id", r["id"], {
                        "left_at": date_str,
                        "source_url": f"https://liquipedia.net/apexlegends/Player_Transfers",
                    })
                    r["left_at"] = date_str  # ローカルも更新
                    stats["roster_updated"] += 1
                    break

        # パターン2: チーム加入（team_to あり）
        if team_to:
            is_sub = role_to.lower() in ("substitute", "sub", "stand-in") if role_to else False
            roster_key = f"{player['id']}_{team_to['id']}_{date_str}"

            if roster_key not in roster_keys:
                new_roster = {
                    "player_id": player["id"],
                    "team_id": team_to["id"],
                    "role": role_to if role_to and role_to.lower() not in STAFF_ROLES else None,
                    "joined_at": date_str,
                    "left_at": None,
                    "is_substitute": is_sub,
                    "source_url": "https://liquipedia.net/apexlegends/Player_Transfers",
                }
                result = supabase_insert("team_rosters", [new_roster])
                if result:
                    roster_keys.add(roster_key)
                    existing_rosters.append(result[0] if result else new_roster)
                    stats["roster_created"] += 1
            else:
                stats["skipped_existing"] += 1

    # --- レポート ---
    print("\n" + "=" * 60)
    print("結果レポート")
    print("=" * 60)
    print(f"  選手マッチ成功: {stats['matched_player']}")
    print(f"  選手マッチ失敗: {stats['unmatched_player']}")
    print(f"  チーム移籍元マッチ: {stats['matched_team_from']}")
    print(f"  チーム移籍先マッチ: {stats['matched_team_to']}")
    print(f"  チームマッチ失敗: {stats['unmatched_team']}")
    print(f"  スタッフ等スキップ: {stats['skipped_staff']}")
    print(f"  ロースター新規作成: {stats['roster_created']}")
    print(f"  ロースター更新(left_at): {stats['roster_updated']}")
    print(f"  既存レコードスキップ: {stats['skipped_existing']}")

    # 未マッチの選手TOP20
    if unmatched_players:
        print(f"\n--- 未マッチ選手 TOP20（{len(unmatched_players)}人中）---")
        sorted_players = sorted(unmatched_players.items(), key=lambda x: -x[1])[:20]
        for name, count in sorted_players:
            print(f"  {name}: {count}回")

    # 未マッチのチームTOP20
    if unmatched_teams:
        print(f"\n--- 未マッチチーム TOP20（{len(unmatched_teams)}チーム中）---")
        sorted_teams = sorted(unmatched_teams.items(), key=lambda x: -x[1])[:20]
        for name, count in sorted_teams:
            print(f"  {name}: {count}回")

    # レポート保存
    report = {
        "generated_at": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "total_transfers": len(all_transfers),
        "stats": stats,
        "unmatched_players": dict(sorted(unmatched_players.items(), key=lambda x: -x[1])[:50]),
        "unmatched_teams": dict(sorted(unmatched_teams.items(), key=lambda x: -x[1])[:50]),
    }
    report_path = os.path.join(CACHE_DIR, "transfer_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  レポート保存: {report_path}")


if __name__ == "__main__":
    main()
