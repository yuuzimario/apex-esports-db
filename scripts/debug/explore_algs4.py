import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import urllib.request

BASE = "https://prod-api.algstools.com"

def api_get(path):
    url = BASE + path
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return None

# 先の探索で判明したイベントID（APAC South Split 1）: 01KH74518P0RXFSHRZJDD7Y0SA
# APAC North Split 1 event: 01KH745JD7DQQQC978CZM83R0Z
# マッチデータからtournamentId: 01KEAJZ74Q4V48HV07Y2S6FA2M を取得済み

# まず全リージョンのイベントIDを特定するためマッチページURLからシリーズIDを使う
# ホームページのリンクから各リージョンのマッチIDを取得:
# APAC South: 01KH74519X6P7G56R7DCV0JPN6
# APAC North: 01KH745JDA97FY0G26HXJD2FN2
# EMEA: 01KH4360A08QHMQQQRJDEB00Q5
# Americas: 01KH2HGJB9A69D3G3NW8XN73Q6

series_ids = {
    "APAC South": "01KH74519X6P7G56R7DCV0JPN6",
    "APAC North": "01KH745JDA97FY0G26HXJD2FN2",
    "EMEA": "01KH4360A08QHMQQQRJDEB00Q5",
    "Americas": "01KH2HGJB9A69D3G3NW8XN73Q6",
}

# 各シリーズからeventId, regionIdを取得
print("=== 1. Event/Region IDs from series matches ===")
event_ids = {}
for region, sid in series_ids.items():
    matches = api_get("/v1/series/" + sid + "/matches")
    if matches and matches.get("matches"):
        m = matches["matches"][0]
        eid = m["eventId"]
        rid = m["regionId"]
        tid = m["tournamentId"]
        event_ids[region] = {"eventId": eid, "regionId": rid, "tournamentId": tid}
        print(region + ":")
        print("  eventId: " + eid)
        print("  regionId: " + rid)
        print("  tournamentId: " + tid)

# === 2. 各リージョンのチーム+ロスターを取得 ===
print("\n=== 2. Teams + Rosters per region ===")
all_teams = {}
for region, ids in event_ids.items():
    eid = ids["eventId"]
    teams_data = api_get("/v1/events/" + eid + "/teams")
    if teams_data and teams_data.get("teams"):
        teams = teams_data["teams"]
        all_teams[region] = teams
        print("\n" + region + ": " + str(len(teams)) + " teams")
        for t in teams[:5]:
            players = [p["name"] for p in t.get("players", [])]
            print("  " + t["name"] + " (" + t["shortName"] + ")" +
                  " | group=" + str(t.get("group", "?")) +
                  " | disbanded=" + str(t.get("disbanded")) +
                  " | players=" + str(players))

# === 3. 全チーム数とプレイヤー数の集計 ===
print("\n=== 3. Summary ===")
total_teams = 0
total_players = 0
for region, teams in all_teams.items():
    active = [t for t in teams if not t.get("disbanded")]
    players = sum(len(t.get("players", [])) for t in active)
    total_teams += len(active)
    total_players += players
    print(region + ": " + str(len(active)) + " active teams, " + str(players) + " players")
print("TOTAL: " + str(total_teams) + " teams, " + str(total_players) + " players")

# === 4. チームデータの詳細構造（1チーム分）===
print("\n=== 4. Full team data structure (1 sample) ===")
sample = list(all_teams.values())[0][0]
print(json.dumps(sample, indent=2))

# === 5. イベント構造（全リージョン）===
print("\n=== 5. Event structure for all regions ===")
for region, ids in event_ids.items():
    eid = ids["eventId"]
    structure = api_get("/v1/events/" + eid + "/structure")
    if structure:
        print("\n" + region + " (" + eid + "):")
        print("  name: " + structure.get("name", ""))
        print("  hasStandings: " + str(structure.get("hasStandings")))
        phases = structure.get("phases", [])
        print("  phases (" + str(len(phases)) + "):")
        for ph in phases:
            print("    " + ph["name"] + " (id=" + ph["id"] + ", format=" + ph.get("format", "?") + ")")
            series_list = ph.get("series", [])
            print("    series (" + str(len(series_list)) + "):")
            for s in series_list[:3]:
                print("      " + s["name"] + " (status=" + s["status"] + ")")

# === 6. transactions / championship-points ===
print("\n=== 6. Checking transactions/cp with season filter ===")
for path in [
    "/v1/seasons/01KEAJYDXP9CBK44PPW7XWDNB3/transactions",
    "/v1/seasons/01KEAJYDXP9CBK44PPW7XWDNB3/championship-points",
    "/v1/tournaments/01KEAJZ74Q4V48HV07Y2S6FA2M/transactions",
    "/v1/tournaments/01KEAJZ74Q4V48HV07Y2S6FA2M/championship-points",
]:
    result = api_get(path)
    if result:
        output = json.dumps(result)
        print(path + " -> OK (" + str(len(output)) + " chars)")
        print(output[:500])
    else:
        print(path + " -> FAILED")

# === 7. 全チームデータをファイルに保存 ===
output_path = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/debug/algs_teams_raw.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_teams, f, indent=2, ensure_ascii=False)
print("\nSaved all teams to: " + output_path)

print("\n=== Done ===")
