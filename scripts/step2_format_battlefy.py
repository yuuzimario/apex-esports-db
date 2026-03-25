"""
Step 2: Battlefy発見データからPro League対象チームのロースターを抽出・整形
Online Opens全体のリーダーボードデータを使い、ALGS API (Step 1) のチームと照合する
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
from datetime import datetime

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"

# リージョン名の正規化
REGION_MAP = {
    "americas": "NA",
    "asia-pacific-north": "APAC_N",
    "asia-pacific-south": "APAC_S",
    "europe-middle-east-and-africa": "EMEA",
}


def normalize_name(name):
    """名前を正規化（小文字+空白除去+特殊文字除去）"""
    return "".join(c.lower() for c in name if c.isalnum())


def main():
    print("=" * 60)
    print("Step 2: Battlefyデータ整形・照合")
    print("=" * 60)

    # Battlefy発見データ読み込み
    with open(os.path.join(CACHE_DIR, "battlefy_discovery.json"), "r", encoding="utf-8") as f:
        bf_data = json.load(f)

    # ALGS APIデータ読み込み
    with open(os.path.join(CACHE_DIR, "algs_rosters.json"), "r", encoding="utf-8") as f:
        algs_data = json.load(f)

    # Battlefyの全チーム・選手をリージョン別に整理
    bf_teams_by_region = {}
    for lb_key, lb_data in bf_data["leaderboards"].items():
        teams_list = lb_data.get("teams", [])
        for team in teams_list:
            region_raw = team.get("region", "")
            region = REGION_MAP.get(region_raw, region_raw)
            if region not in bf_teams_by_region:
                bf_teams_by_region[region] = {}

            team_name = team["name"]
            players = [p["name"] for p in team.get("breakdown", [])]
            bf_teams_by_region[region][normalize_name(team_name)] = {
                "name": team_name,
                "battlefy_team_id": team.get("teamID", ""),
                "score": team.get("score", 0),
                "rank": team.get("rank", 0),
                "players": players,
            }

    # ALGSチームとBattlefyチームを照合
    result = {
        "source": "battlefy (Online Opens leaderboard)",
        "fetched_at": bf_data.get("discovered_at", ""),
        "formatted_at": datetime.now().isoformat(),
        "regions": {},
        "match_stats": {},
    }

    total_matched = 0
    total_unmatched = 0
    total_roster_diff = 0

    for region, algs_teams in algs_data["regions"].items():
        bf_region = bf_teams_by_region.get(region, {})
        matched_teams = []
        unmatched = []

        for algs_team in algs_teams:
            algs_name_norm = normalize_name(algs_team["name"])
            algs_players = {normalize_name(p["ign"]) for p in algs_team["players"]}

            # 名前で直接マッチ
            bf_team = bf_region.get(algs_name_norm)

            # マッチしなかった場合、部分一致を試みる
            if not bf_team:
                for bf_norm, bf_candidate in bf_region.items():
                    if bf_norm in algs_name_norm or algs_name_norm in bf_norm:
                        bf_team = bf_candidate
                        break

            if bf_team:
                bf_players = {normalize_name(p) for p in bf_team["players"]}
                common = algs_players & bf_players
                algs_only = algs_players - bf_players
                bf_only = bf_players - algs_players

                has_diff = len(algs_only) > 0 or len(bf_only) > 0
                if has_diff:
                    total_roster_diff += 1

                matched_teams.append({
                    "algs_name": algs_team["name"],
                    "battlefy_name": bf_team["name"],
                    "battlefy_team_id": bf_team["battlefy_team_id"],
                    "battlefy_score": bf_team["score"],
                    "battlefy_rank": bf_team["rank"],
                    "algs_players": [p["ign"] for p in algs_team["players"]],
                    "battlefy_players": bf_team["players"],
                    "roster_match": not has_diff,
                    "common_players": list(common),
                    "algs_only": list(algs_only),
                    "battlefy_only": list(bf_only),
                })
                total_matched += 1
            else:
                unmatched.append(algs_team["name"])
                total_unmatched += 1

        result["regions"][region] = {
            "matched": matched_teams,
            "unmatched_in_algs": unmatched,
        }

        print(f"\n--- {region} ---")
        print(f"  マッチ: {len(matched_teams)}/{len(algs_teams)}")
        if unmatched:
            print(f"  未マッチ（ALGSのみ）: {', '.join(unmatched)}")

        # ロースター差分を表示
        diffs = [t for t in matched_teams if not t["roster_match"]]
        if diffs:
            print(f"  ロースター差分あり: {len(diffs)}チーム")
            for d in diffs[:5]:
                print(f"    {d['algs_name']}:")
                if d['algs_only']:
                    print(f"      ALGS のみ: {d['algs_only']}")
                if d['battlefy_only']:
                    print(f"      Battlefyのみ: {d['battlefy_only']}")

    result["match_stats"] = {
        "total_algs_teams": sum(len(r) for r in algs_data["regions"].values()),
        "total_matched": total_matched,
        "total_unmatched": total_unmatched,
        "total_roster_diff": total_roster_diff,
    }

    # 保存
    output_path = os.path.join(CACHE_DIR, "battlefy_rosters.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"照合結果: {total_matched}/{total_matched + total_unmatched} マッチ")
    print(f"ロースター差分: {total_roster_diff} チーム")
    print(f"保存先: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
