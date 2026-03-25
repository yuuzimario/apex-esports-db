"""
Step 4: 3ソース統合 → 差分レポート生成 → Supabase更新
ALGS API (基準) + Battlefy (補助) + Liquipedia (SNS) を統合
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
from datetime import datetime, date

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)

# 国旗コードからリージョン推定
FLAG_TO_REGION = {
    "JP": "APAC_N", "KR": "APAC_N",
    "US": "NA", "CA": "NA", "MX": "NA", "BR": "NA",
    "GB": "EMEA", "DE": "EMEA", "FR": "EMEA", "ES": "EMEA", "IT": "EMEA",
    "SE": "EMEA", "FI": "EMEA", "NO": "EMEA", "DK": "EMEA", "PL": "EMEA",
    "RU": "EMEA", "UA": "EMEA", "NL": "EMEA", "PT": "EMEA", "BE": "EMEA",
    "AT": "EMEA", "CH": "EMEA", "TR": "EMEA", "SA": "EMEA", "AE": "EMEA",
    "IL": "EMEA", "MA": "EMEA", "EG": "EMEA", "ZA": "EMEA", "CZ": "EMEA",
    "RO": "EMEA", "HU": "EMEA", "GR": "EMEA", "BG": "EMEA", "RS": "EMEA",
    "HR": "EMEA", "BA": "EMEA", "SK": "EMEA", "LT": "EMEA", "LV": "EMEA",
    "EE": "EMEA", "KZ": "EMEA", "UZ": "EMEA", "GE": "EMEA", "IE": "EMEA",
    "AU": "APAC_S", "NZ": "APAC_S", "SG": "APAC_S", "TH": "APAC_S",
    "PH": "APAC_S", "MY": "APAC_S", "ID": "APAC_S", "VN": "APAC_S",
    "TW": "APAC_S", "HK": "APAC_S", "CN": "APAC_S", "IN": "APAC_S",
}


def normalize_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def supabase_get(table, params=None):
    resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params or {}, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


def supabase_upsert(table, data):
    if not data:
        return []
    headers = {**HEADERS, "Prefer": "return=representation,resolution=merge-duplicates"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  UPSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def supabase_update(table, match_col, match_val, data):
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?{match_col}=eq.{match_val}",
        json=data,
        headers=headers,
    )
    if resp.status_code not in (200, 204):
        print(f"  UPDATE エラー ({table}): {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json() if resp.text else []


def supabase_insert(table, data):
    if not data:
        return []
    headers = {**HEADERS, "Prefer": "return=representation"}
    resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
    if resp.status_code not in (200, 201):
        print(f"  INSERT エラー ({table}): {resp.status_code}: {resp.text[:300]}")
        return []
    return resp.json()


def main():
    print("=" * 60)
    print("Step 4: データ統合 & Supabase更新")
    print("=" * 60)

    # データ読み込み
    with open(os.path.join(CACHE_DIR, "algs_rosters.json"), "r", encoding="utf-8") as f:
        algs_data = json.load(f)

    with open(os.path.join(CACHE_DIR, "liquipedia_sns.json"), "r", encoding="utf-8") as f:
        sns_data = json.load(f)

    # Liquipedia SNSをIGN正規化名でインデックス化
    lp_by_norm = {}
    for norm_key, pdata in sns_data.get("players", {}).items():
        lp_by_norm[norm_key] = pdata
        # IGNの正規化版でもマッピング
        ign_norm = normalize_name(pdata.get("ign", ""))
        if ign_norm and ign_norm != norm_key:
            lp_by_norm[ign_norm] = pdata

    # ===== 既存DB データ取得 =====
    print("\n--- 既存DBデータ取得 ---")
    existing_teams = supabase_get("teams", {"select": "*", "is_active": "eq.true"})
    existing_players = supabase_get("players", {"select": "*"})
    existing_rosters = supabase_get("team_rosters", {"select": "*", "left_at": "is.null"})

    teams_by_slug = {t["slug"]: t for t in existing_teams}
    teams_by_norm = {normalize_name(t["name"]): t for t in existing_teams}
    players_by_slug = {p["slug"]: p for p in existing_players}
    players_by_norm = {normalize_name(p["ign"]): p for p in existing_players}

    print(f"  既存チーム: {len(existing_teams)}")
    print(f"  既存選手: {len(existing_players)}")
    print(f"  既存ロースター: {len(existing_rosters)}")

    # ===== 差分レポート =====
    diff_report = {
        "generated_at": datetime.now().isoformat(),
        "new_teams": [],
        "new_players": [],
        "roster_changes": [],
        "sns_updates": [],
        "stats": {},
    }

    # ===== チーム処理 =====
    print("\n--- チーム処理 ---")
    teams_created = 0
    teams_updated = 0

    # ALGSの全チームを処理
    algs_team_map = {}  # team_name_norm -> team_db_id

    for region, teams in algs_data["regions"].items():
        for team in teams:
            team_name = team["name"]
            team_norm = normalize_name(team_name)
            team_slug = make_slug(team_name)

            existing = teams_by_norm.get(team_norm) or teams_by_slug.get(team_slug)

            if existing:
                algs_team_map[team_norm] = existing["id"]
                teams_updated += 1
            else:
                # 新規チーム作成
                new_team = {
                    "slug": team_slug,
                    "name": team_name,
                    "short_name": team.get("short_name", "")[:20] or None,
                    "region": region,
                    "is_active": True,
                }
                result = supabase_insert("teams", [new_team])
                if result:
                    algs_team_map[team_norm] = result[0]["id"]
                    teams_by_norm[team_norm] = result[0]
                    teams_by_slug[team_slug] = result[0]
                    diff_report["new_teams"].append({"name": team_name, "region": region})
                    teams_created += 1
                    print(f"  新規チーム: {team_name} ({region})")

    print(f"  既存: {teams_updated}, 新規作成: {teams_created}")

    # ===== 選手処理 =====
    print("\n--- 選手処理 ---")
    players_created = 0
    players_updated = 0
    sns_updated = 0

    algs_player_map = {}  # player_ign_norm -> player_db_id

    for region, teams in algs_data["regions"].items():
        for team in teams:
            for player in team["players"]:
                ign = player["ign"].strip()
                ign_norm = normalize_name(ign)
                player_slug = make_slug(ign)

                # 既存選手を検索
                existing = players_by_norm.get(ign_norm) or players_by_slug.get(player_slug)

                # Liquipedia SNS情報を取得
                lp_info = lp_by_norm.get(ign_norm, {})
                sns = lp_info.get("sns", {})
                extra = lp_info.get("extra", {})

                # SNS URLを構築
                twitter_url = sns.get("twitter", {}).get("url")
                twitch_url = sns.get("twitch", {}).get("url")
                youtube_url = sns.get("youtube", {}).get("url")

                # Liquipedia URL
                lp_url = lp_info.get("liquipedia_url")

                # プロフィール画像（ALGS APIの画像を優先）
                profile_image = player.get("image_url")

                # 国籍（Liquipediaから）
                nationality = extra.get("country", "")[:2].upper() if extra.get("country") else None

                if existing:
                    algs_player_map[ign_norm] = existing["id"]

                    # SNS情報の更新チェック
                    update_data = {}
                    if twitter_url and not existing.get("twitter_url"):
                        update_data["twitter_url"] = twitter_url
                    if twitch_url and not existing.get("twitch_url"):
                        update_data["twitch_url"] = twitch_url
                    if youtube_url and not existing.get("youtube_url"):
                        update_data["youtube_url"] = youtube_url
                    if lp_url and not existing.get("liquipedia_url"):
                        update_data["liquipedia_url"] = lp_url
                    if profile_image and not existing.get("profile_image_url"):
                        update_data["profile_image_url"] = profile_image
                    if nationality and not existing.get("nationality"):
                        update_data["nationality"] = nationality

                    if update_data:
                        update_data["updated_at"] = datetime.now().isoformat()
                        supabase_update("players", "id", existing["id"], update_data)
                        sns_updated += 1
                        diff_report["sns_updates"].append({
                            "ign": ign,
                            "updates": list(update_data.keys()),
                        })

                    players_updated += 1
                else:
                    # 新規選手作成
                    new_player = {
                        "slug": player_slug,
                        "ign": ign,
                        "region": region,
                        "role": player.get("role", "player"),
                        "twitter_url": twitter_url,
                        "twitch_url": twitch_url,
                        "youtube_url": youtube_url,
                        "liquipedia_url": lp_url,
                        "profile_image_url": profile_image,
                        "nationality": nationality,
                        "is_active": True,
                    }

                    # 本名（Liquipediaから）
                    if extra.get("real_name"):
                        new_player["real_name"] = extra["real_name"]

                    result = supabase_insert("players", [new_player])
                    if result:
                        algs_player_map[ign_norm] = result[0]["id"]
                        players_by_norm[ign_norm] = result[0]
                        players_by_slug[player_slug] = result[0]
                        diff_report["new_players"].append({
                            "ign": ign,
                            "team": team["name"],
                            "region": region,
                        })
                        players_created += 1
                    else:
                        # slug重複の可能性→リージョン付きslugでリトライ
                        new_player["slug"] = f"{player_slug}-{region.lower().replace('_', '-')}"
                        result = supabase_insert("players", [new_player])
                        if result:
                            algs_player_map[ign_norm] = result[0]["id"]
                            players_by_norm[ign_norm] = result[0]
                            players_created += 1

    print(f"  既存: {players_updated}, 新規作成: {players_created}, SNS更新: {sns_updated}")

    # ===== ロースター処理 =====
    print("\n--- ロースター処理 ---")
    rosters_created = 0
    rosters_ended = 0

    # 現在のロースターをチームID別にインデックス化
    current_rosters_by_team = {}
    for r in existing_rosters:
        tid = r["team_id"]
        if tid not in current_rosters_by_team:
            current_rosters_by_team[tid] = []
        current_rosters_by_team[tid].append(r)

    today = date.today().isoformat()

    for region, teams in algs_data["regions"].items():
        for team in teams:
            team_norm = normalize_name(team["name"])
            team_id = algs_team_map.get(team_norm)
            if not team_id:
                continue

            # ALGSの選手IDセット
            algs_player_ids = set()
            for player in team["players"]:
                ign_norm = normalize_name(player["ign"].strip())
                pid = algs_player_map.get(ign_norm)
                if pid:
                    algs_player_ids.add(pid)

            # 現在のDB上のロースター
            db_roster = current_rosters_by_team.get(team_id, [])
            db_player_ids = {r["player_id"] for r in db_roster}

            # 新メンバー（ALGSにいるがDBにいない）
            new_members = algs_player_ids - db_player_ids
            # 脱退メンバー（DBにいるがALGSにいない）
            left_members = db_player_ids - algs_player_ids

            for pid in new_members:
                new_roster = {
                    "team_id": team_id,
                    "player_id": pid,
                    "role": "player",
                    "joined_at": today,
                    "is_substitute": False,
                    "source_url": "https://algs.ea.com",
                }
                result = supabase_insert("team_rosters", [new_roster])
                if result:
                    rosters_created += 1

            for pid in left_members:
                # 脱退日を設定
                for r in db_roster:
                    if r["player_id"] == pid:
                        supabase_update("team_rosters", "id", r["id"], {"left_at": today})
                        rosters_ended += 1
                        break

            if new_members or left_members:
                new_igns = []
                left_igns = []
                for p in team["players"]:
                    pnorm = normalize_name(p["ign"].strip())
                    pid = algs_player_map.get(pnorm)
                    if pid in new_members:
                        new_igns.append(p["ign"])
                for r in db_roster:
                    if r["player_id"] in left_members:
                        # 選手名を逆引き
                        for p in existing_players:
                            if p["id"] == r["player_id"]:
                                left_igns.append(p["ign"])
                                break

                diff_report["roster_changes"].append({
                    "team": team["name"],
                    "region": region,
                    "joined": new_igns,
                    "left": left_igns,
                })

    print(f"  新規ロースター: {rosters_created}, 脱退処理: {rosters_ended}")

    # ===== 差分レポート保存 =====
    diff_report["stats"] = {
        "teams_created": teams_created,
        "teams_updated": teams_updated,
        "players_created": players_created,
        "players_updated": players_updated,
        "sns_updated": sns_updated,
        "rosters_created": rosters_created,
        "rosters_ended": rosters_ended,
    }

    report_path = os.path.join(CACHE_DIR, "diff_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(diff_report, f, ensure_ascii=False, indent=2)

    # ===== サマリー =====
    print(f"\n{'=' * 60}")
    print("統合完了サマリー:")
    print(f"  チーム: {teams_updated}更新 + {teams_created}新規")
    print(f"  選手: {players_updated}更新 + {players_created}新規 + {sns_updated}件SNS追加")
    print(f"  ロースター: {rosters_created}加入 + {rosters_ended}脱退")

    if diff_report["new_teams"]:
        print(f"\n新規チーム ({len(diff_report['new_teams'])}):")
        for t in diff_report["new_teams"][:10]:
            print(f"  - {t['name']} ({t['region']})")

    if diff_report["roster_changes"]:
        print(f"\nロースター変更 ({len(diff_report['roster_changes'])}):")
        for c in diff_report["roster_changes"][:15]:
            print(f"  {c['team']} ({c['region']}):")
            if c["joined"]:
                print(f"    加入: {', '.join(c['joined'])}")
            if c["left"]:
                print(f"    脱退: {', '.join(c['left'])}")

    print(f"\n差分レポート: {report_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
