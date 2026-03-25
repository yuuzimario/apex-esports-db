"""
DB登録チームに所属歴がある未マッチ選手をSupabaseに追加する
all_transfers.json を参照し、DB既存チームに所属したことがある選手のみ追加

使い方:
  python add_missing_players.py          # 本番実行
  python add_missing_players.py --dry-run  # 確認のみ
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
import re
import argparse
import httpx
import time

# === 設定 ===
CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)


def normalize_name(name):
    """名前を正規化（英数字のみ小文字）"""
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    """URL用スラッグ生成"""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


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


def supabase_insert_batch(table, data, batch_size=50):
    """Supabaseにバッチ挿入（重複はスキップ）"""
    headers = {
        **DB_HEADERS,
        "Prefer": "return=representation,resolution=ignore-duplicates",
    }
    inserted = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=batch, headers=headers)
        if resp.status_code in (200, 201):
            result = resp.json()
            inserted.extend(result)
            if (i // batch_size) % 5 == 0:
                print(f"    バッチ {i // batch_size + 1}: {len(result)}件追加")
        else:
            print(f"  INSERT エラー: {resp.status_code}: {resp.text[:300]}")
        time.sleep(0.2)  # レート制限
    return inserted


# 国旗コード → 国名マッピング（主要なもの）
FLAG_TO_COUNTRY = {
    "jp": "Japan", "kr": "South Korea", "cn": "China", "tw": "Taiwan",
    "us": "United States", "ca": "Canada", "gb": "United Kingdom",
    "uk": "United Kingdom", "au": "Australia", "nz": "New Zealand",
    "fr": "France", "de": "Germany", "se": "Sweden", "no": "Norway",
    "dk": "Denmark", "fi": "Finland", "es": "Spain", "it": "Italy",
    "pt": "Portugal", "nl": "Netherlands", "be": "Belgium", "ch": "Switzerland",
    "at": "Austria", "pl": "Poland", "cz": "Czech Republic", "ru": "Russia",
    "ua": "Ukraine", "br": "Brazil", "ar": "Argentina", "mx": "Mexico",
    "cl": "Chile", "co": "Colombia", "pe": "Peru",
    "th": "Thailand", "ph": "Philippines", "id": "Indonesia", "my": "Malaysia",
    "sg": "Singapore", "vn": "Vietnam", "in": "India", "pk": "Pakistan",
    "sa": "Saudi Arabia", "ae": "UAE", "tr": "Turkey", "il": "Israel",
    "za": "South Africa", "eg": "Egypt", "ng": "Nigeria",
    "ie": "Ireland", "is": "Iceland", "hu": "Hungary", "ro": "Romania",
    "bg": "Bulgaria", "hr": "Croatia", "rs": "Serbia", "sk": "Slovakia",
    "lt": "Lithuania", "lv": "Latvia", "ee": "Estonia",
    "hk": "Hong Kong", "mo": "Macau",
}


def main():
    parser = argparse.ArgumentParser(description="未マッチ選手をDBに追加")
    parser.add_argument("--dry-run", action="store_true", help="DB更新なし")
    args = parser.parse_args()

    print("=" * 60)
    print("未マッチ選手追加（DB登録チーム所属者のみ）")
    print("=" * 60)

    if args.dry_run:
        print("⚠ DRY-RUN モード（DB更新なし）\n")

    # --- Step 1: 移籍データ読み込み ---
    transfers_path = os.path.join(CACHE_DIR, "all_transfers.json")
    with open(transfers_path, "r", encoding="utf-8") as f:
        all_transfers = json.load(f)
    print(f"移籍レコード: {len(all_transfers)}件")

    # --- Step 2: DB既存データ取得 ---
    print("\nDB既存データ取得中...")
    existing_teams = supabase_get("teams", {"select": "id,name,slug,short_name"})
    existing_players = supabase_get("players", {"select": "id,ign,slug"})

    # チーム名インデックス
    teams_by_norm = {}
    for t in existing_teams:
        teams_by_norm[normalize_name(t["name"])] = t
        if t.get("short_name"):
            teams_by_norm[normalize_name(t["short_name"])] = t
        # サフィックス除去
        name = t["name"]
        for suffix in [" Esports", " Gaming", " E-Sports", " Esport"]:
            if name.endswith(suffix):
                short_norm = normalize_name(name[:len(name) - len(suffix)])
                if short_norm not in teams_by_norm:
                    teams_by_norm[short_norm] = t
        # "Team X" → "X"
        if name.lower().startswith("team "):
            short_norm = normalize_name(name[5:])
            if short_norm not in teams_by_norm:
                teams_by_norm[short_norm] = t

    # 追加エイリアス
    TEAM_ALIASES = {
        "complexitygaming": "complexity", "rejectwinnity": "reject",
        "rejectwinnityjp": "reject", "scarzblack": "scarz", "scarzsb": "scarz",
        "sunsistergod": "sunsister", "mdy": "mdyblack",
        "evospredator": "evos", "mpiregaming": "mpire",
        "obeyalliance": "alliance", "10kclub": "10kclub",
    }
    for alias_norm, target_norm in TEAM_ALIASES.items():
        if target_norm in teams_by_norm and alias_norm not in teams_by_norm:
            teams_by_norm[alias_norm] = teams_by_norm[target_norm]

    db_player_norms = {normalize_name(p["ign"]) for p in existing_players}
    db_player_slugs = {p["slug"] for p in existing_players}

    print(f"  DB登録チーム: {len(existing_teams)}")
    print(f"  DB登録選手: {len(existing_players)}")
    print(f"  チーム名インデックス: {len(teams_by_norm)}エントリ")

    # --- Step 3: DB登録チームに所属歴がある未マッチ選手を特定 ---
    print("\n未マッチ選手を分析中...")

    def match_team(team_name):
        """チーム名マッチング"""
        tn = normalize_name(team_name)
        if tn in teams_by_norm:
            return teams_by_norm[tn]
        # 括弧除去
        clean = re.sub(r"\s*\([^)]*\)\s*", "", team_name).strip()
        cn = normalize_name(clean)
        if cn and cn in teams_by_norm:
            return teams_by_norm[cn]
        # Team プレフィックス
        if team_name.lower().startswith("team "):
            short = normalize_name(team_name[5:])
            if short in teams_by_norm:
                return teams_by_norm[short]
        # サフィックス除去
        for sfx in [" esports", " gaming", " e-sports", " esport", " gg"]:
            if team_name.lower().endswith(sfx):
                short = normalize_name(team_name[:len(team_name) - len(sfx)])
                if short in teams_by_norm:
                    return teams_by_norm[short]
        return None

    # 選手ごとの情報を集約
    player_info = {}  # norm_name -> {name, flag, teams: set()}
    for t in all_transfers:
        pname = t["player_name"]
        pnorm = normalize_name(pname)

        if pnorm in db_player_norms:
            continue  # 既にDB登録済み

        if pnorm not in player_info:
            player_info[pnorm] = {
                "name": pname,
                "flag": t.get("flag", ""),
                "db_teams": set(),
                "all_teams": set(),
                "transfer_count": 0,
            }

        player_info[pnorm]["transfer_count"] += 1

        for team_field in ["team_from", "team_to"]:
            team_name = t.get(team_field)
            if team_name:
                player_info[pnorm]["all_teams"].add(team_name)
                matched = match_team(team_name)
                if matched:
                    player_info[pnorm]["db_teams"].add(matched["name"])

    # DB登録チームに所属歴がある選手のみフィルタ
    players_to_add = []
    for pnorm, info in player_info.items():
        if info["db_teams"]:
            players_to_add.append(info)

    # 移籍回数でソート（重要な選手ほど上に）
    players_to_add.sort(key=lambda x: -x["transfer_count"])

    print(f"  全未マッチ選手: {len(player_info)}人")
    print(f"  DB登録チーム所属あり: {len(players_to_add)}人 ← これを追加")

    # サンプル表示
    print(f"\n--- 追加対象の上位30人 ---")
    for p in players_to_add[:30]:
        flag = p["flag"] if p["flag"] else "??"
        teams_str = ", ".join(list(p["db_teams"])[:3])
        print(f"  [{flag}] {p['name']} ({p['transfer_count']}回) → {teams_str}")

    if args.dry_run:
        print(f"\n⚠ DRY-RUN: {len(players_to_add)}人の追加をスキップ")
        return

    # --- Step 4: Supabaseに選手を追加 ---
    print(f"\n--- Step 4: {len(players_to_add)}人をSupabaseに追加 ---")

    records = []
    used_slugs = set(db_player_slugs)
    for p in players_to_add:
        slug = make_slug(p["name"])
        # スラッグ重複回避
        base_slug = slug
        counter = 1
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        used_slugs.add(slug)

        # nationalityカラムはvarchar(2)なので国コードをそのまま使う
        nationality = p["flag"].lower() if p["flag"] else None
        # 2文字を超える場合はNone
        if nationality and len(nationality) > 2:
            nationality = None

        records.append({
            "ign": p["name"],
            "slug": slug,
            "nationality": nationality,
            "is_active": True,
        })

    inserted = supabase_insert_batch("players", records)
    print(f"\n  追加完了: {len(inserted)}人")

    # レポート保存
    report = {
        "total_candidates": len(player_info),
        "added": len(inserted),
        "players": [{"ign": p["name"], "teams": list(p["db_teams"]), "transfers": p["transfer_count"]} for p in players_to_add],
    }
    report_path = os.path.join(CACHE_DIR, "added_players_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  レポート保存: {report_path}")


if __name__ == "__main__":
    main()
