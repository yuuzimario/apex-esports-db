"""
Liquipedia ALGS Year 6 大会ページから全チーム+ロスターを取得
形式: {{Opponent|team |players={{Persons |{{Person|player}} ... }}
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import time
import re
import json

LP_HEADERS = {"User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)"}
client = httpx.Client(timeout=30)

REGIONS = {
    "APAC_N": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/APAC_North",
    "NA": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/Americas",
    "EMEA": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/EMEA",
    "APAC_S": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/APAC_South",
}


def fetch_page(title):
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {"action": "query", "titles": title, "prop": "revisions", "rvprop": "content", "format": "json"}
    resp = client.get(url, params=params, headers=LP_HEADERS)
    if resp.status_code != 200:
        return ""
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        revs = page.get("revisions", [])
        if revs:
            return revs[0].get("*", "")
    return ""


def extract_teams_v2(wiki):
    """{{Opponent|team}} + {{Person|player}} 形式を抽出"""
    teams = []

    # Participantsセクションを見つける
    participants_idx = wiki.find("==Participants==")
    if participants_idx < 0:
        return teams

    participants_section = wiki[participants_idx:]

    # {{Opponent|TEAM_NAME で分割
    opponent_blocks = re.split(r"\{\{Opponent\|", participants_section)

    for block in opponent_blocks[1:]:  # 最初は空
        # チーム名（最初の改行or|まで）
        team_match = re.match(r"([^\n|]+)", block)
        if not team_match:
            continue
        team_name = team_match.group(1).strip()
        if not team_name or team_name.startswith("{"):
            continue

        # 選手を取得: {{Person|PLAYER_NAME|flag=XX}}
        players = []
        for pm in re.finditer(r"\{\{Person\|([^|}]+)(?:\|([^}]*))?", block):
            pname = pm.group(1).strip()
            extras = pm.group(2) or ""

            # Coachやstaffは除外
            if "role=Coach" in extras or "type=staff" in extras:
                continue

            # 国旗取得
            flag_match = re.search(r"flag=(\w+)", extras)
            flag = flag_match.group(1)[:2].upper() if flag_match else ""

            if pname and pname.lower() not in ("tbd", "n/a", ""):
                players.append({"ign": pname, "flag": flag})

        if team_name and players:
            teams.append({"team": team_name, "players": players[:4]})  # 最大4人（サブ含む）

    return teams


def main():
    all_data = {}

    for region, page_title in REGIONS.items():
        print(f"\n=== {region} ===")
        wiki = fetch_page(page_title)
        time.sleep(3)

        if not wiki:
            print("  ページ取得失敗")
            continue

        teams = extract_teams_v2(wiki)
        all_data[region] = teams

        print(f"  チーム数: {len(teams)}")
        for t in teams:
            ps = ", ".join([p["ign"] for p in t["players"][:3]])
            extra = f" +{len(t['players'])-3}" if len(t["players"]) > 3 else ""
            print(f"    {t['team']}: {ps}{extra}")

    # JSON保存
    output = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/algs_year6_teams.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\n\n=== 統計 ===")
    total = sum(len(v) for v in all_data.values())
    print(f"総チーム数: {total}")
    for region, teams in all_data.items():
        print(f"  {region}: {len(teams)} チーム")
    print(f"\n保存先: {output}")


if __name__ == "__main__":
    main()
