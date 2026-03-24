"""
Liquipediaの大会ページからALGS Year 6全リージョンのチーム+ロスターを取得
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import time
import re
import json

LP_HEADERS = {"User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app; contact@apex-esports-db.com)"}
client = httpx.Client(timeout=30)

REGIONS = {
    "APAC_N": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/APAC_North",
    "NA": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/Americas",
    "EMEA": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/EMEA",
    "APAC_S": "Apex_Legends_Global_Series/2026/Split_1/Pro_League/APAC_South",
}


def fetch_page(title):
    url = "https://liquipedia.net/apexlegends/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }
    resp = client.get(url, params=params, headers=LP_HEADERS)
    if resp.status_code != 200:
        return ""
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        revs = page.get("revisions", [])
        if revs:
            return revs[0].get("*", "")
    return ""


def extract_teams(wiki):
    """TeamCard形式のチーム+選手を抽出"""
    teams = []

    # パターン: {{TeamCard |team=XXX |p1=YYY |p2=ZZZ |p3=WWW
    # 複数行にわたるので DOTALL で
    pattern = r"\{\{TeamCard[^}]*?\|team\s*=\s*([^|\n}]+)(.*?)(?:\}\}|\{\{TeamCard)"

    # まず全体をTeamCardで分割
    cards = re.split(r"(\{\{TeamCard)", wiki)

    for i, card in enumerate(cards):
        if card == "{{TeamCard" and i + 1 < len(cards):
            content = cards[i + 1]

            # チーム名
            team_match = re.search(r"\|team\s*=\s*([^|\n]+)", content)
            if not team_match:
                continue
            team_name = team_match.group(1).strip()

            # 選手
            players = []
            for j in range(1, 7):
                p_pattern = r"\|p" + str(j) + r"\s*=\s*([^|\n]+)"
                pm = re.search(p_pattern, content)
                if pm:
                    pname = pm.group(1).strip()
                    if pname and pname.lower() not in ("tbd", "n/a", ""):
                        # 国旗
                        f_pattern = r"\|p" + str(j) + r"flag\s*=\s*([^|\n]+)"
                        fm = re.search(f_pattern, content)
                        flag = fm.group(1).strip()[:2].lower() if fm else ""
                        players.append({"ign": pname, "flag": flag})

            if team_name and players:
                teams.append({"team": team_name, "players": players})

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

        teams = extract_teams(wiki)
        all_data[region] = teams

        print(f"  チーム数: {len(teams)}")
        for t in teams:
            ps = ", ".join([p["ign"] for p in t["players"][:3]])
            print(f"    {t['team']}: {ps}")

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
