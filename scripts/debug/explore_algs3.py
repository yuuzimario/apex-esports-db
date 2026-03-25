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
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        print("  ERROR: " + str(e))
        return None

# === 1. シーズン一覧 ===
print("=== 1. /v1/seasons ===")
seasons = api_get("/v1/seasons")
print(json.dumps(seasons, indent=2))

# Year 6のシーズンID
y6_season_id = "01KEAJYDXP9CBK44PPW7XWDNB3"

# === 2. トーナメント一覧 ===
print("\n=== 2. /v1/seasons/{y6}/tournaments ===")
tournaments = api_get("/v1/seasons/" + y6_season_id + "/tournaments")
if tournaments:
    print(json.dumps(tournaments, indent=2)[:3000])

# === 3. リージョン一覧（トーナメントから取得） ===
if tournaments:
    for t in tournaments if isinstance(tournaments, list) else [tournaments]:
        tid = t.get("id", "")
        tname = t.get("name", "")
        print("\n=== 3. Tournament: " + tname + " (" + tid + ") ===")

        # リージョン
        regions = api_get("/v1/tournaments/" + tid + "/regions")
        if regions:
            print("Regions:")
            print(json.dumps(regions, indent=2)[:2000])

            # 各リージョンのチーム
            region_list = regions if isinstance(regions, list) else regions.get("regions", [])
            for r in region_list[:5]:
                rid = r.get("id", "")
                rname = r.get("name", "")
                print("\n--- Region: " + rname + " (" + rid + ") ---")

                # チーム
                teams = api_get("/v1/regions/" + rid + "/teams")
                if teams:
                    teams_list = teams if isinstance(teams, list) else teams.get("teams", [])
                    print("Teams (" + str(len(teams_list)) + "):")
                    print(json.dumps(teams_list[:3], indent=2)[:2000])

                # イベント
                events = api_get("/v1/regions/" + rid + "/events")
                if events:
                    events_list = events if isinstance(events, list) else events.get("events", [])
                    print("Events (" + str(len(events_list)) + "):")
                    for ev in events_list[:2]:
                        print("  " + ev.get("name", "") + " (" + ev.get("id", "") + ")")

# === 4. 追加APIパス探索 ===
print("\n=== 4. Additional API path exploration ===")
extra_paths = [
    "/v1/tournaments",
    "/v1/tournaments/" + "01KEAJZ74Q4V48HV07Y2S6FA2M",
    "/v1/tournaments/" + "01KEAJZ74Q4V48HV07Y2S6FA2M" + "/teams",
    "/v1/tournaments/" + "01KEAJZ74Q4V48HV07Y2S6FA2M" + "/rosters",
    "/v1/events/01KH74518P0RXFSHRZJDD7Y0SA/teams",
    "/v1/events/01KH74518P0RXFSHRZJDD7Y0SA/rosters",
    "/v1/phases/01KH74519BVP3FFPQ0THW93FMF/teams",
    "/v1/phases/01KH74519BVP3FFPQ0THW93FMF/rosters",
    "/v1/series/01KH74519X6P7G56R7DCV0JPN6/teams",
    "/v1/series/01KH74519X6P7G56R7DCV0JPN6/rosters",
    "/v1/stats/events/01KH74518P0RXFSHRZJDD7Y0SA",
    "/v1/transactions",
    "/v1/championship-points",
    "/openapi.json",
    "/swagger.json",
    "/docs",
    "/api-docs",
]

for path in extra_paths:
    result = api_get(path)
    if result is not None:
        output = json.dumps(result, indent=2)
        if len(output) > 50:
            print("\n" + path + " -> OK (" + str(len(output)) + " chars)")
            print(output[:1500])
    else:
        print(path + " -> FAILED")

print("\n=== Done ===")
