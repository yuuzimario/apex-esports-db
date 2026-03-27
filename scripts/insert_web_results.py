"""Web検索で取得したYear 4 Championship + Split 1 Playoffs結果を投入"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import httpx
import re

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"
h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
client = httpx.Client(timeout=30)


def normalize(n):
    return "".join(c.lower() for c in n if c.isalnum()) if n else ""


def make_slug(name):
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return re.sub(r"-+", "-", slug) or "unknown"


# チーム辞書
r = client.get(f"{SUPABASE_URL}/rest/v1/teams", params={"select": "id,name,slug,short_name", "limit": "2000"}, headers=h)
teams_db = r.json()
teams_by_norm = {}
for t in teams_db:
    teams_by_norm[normalize(t["name"])] = t
    if t.get("short_name"):
        teams_by_norm[normalize(t["short_name"])] = t
    if t["name"].lower().startswith("team "):
        teams_by_norm[normalize(t["name"][5:])] = t
    for sfx in [" Esports", " Gaming", " E-Sports"]:
        if t["name"].endswith(sfx):
            teams_by_norm[normalize(t["name"][:len(t["name"]) - len(sfx)])] = t


def find_team(name):
    n = normalize(name)
    if n in teams_by_norm:
        return teams_by_norm[n]
    if name.lower().startswith("team "):
        n2 = normalize(name[5:])
        if n2 in teams_by_norm:
            return teams_by_norm[n2]
    else:
        n2 = normalize("team " + name)
        if n2 in teams_by_norm:
            return teams_by_norm[n2]
    for sfx in [" esports", " gaming"]:
        if name.lower().endswith(sfx):
            n3 = normalize(name[:len(name) - len(sfx)])
            if n3 in teams_by_norm:
                return teams_by_norm[n3]
    return None


def ensure_team(name):
    team = find_team(name)
    if team:
        return team
    new_data = [{"name": name, "slug": make_slug(name), "is_active": False}]
    resp = client.post(f"{SUPABASE_URL}/rest/v1/teams", json=new_data, headers={**h, "Prefer": "return=representation"})
    if resp.status_code in (200, 201):
        team = resp.json()[0]
        teams_by_norm[normalize(name)] = team
        print(f"  新規チーム: {name}")
        return team
    print(f"  チーム作成失敗: {name} {resp.status_code}")
    return None


def insert_results(tournament_id, results_data, label):
    to_insert = []
    for r in results_data:
        team = ensure_team(r["team"])
        if not team:
            continue
        entry = {
            "tournament_id": tournament_id,
            "team_id": team["id"],
            "placement": r["placement"],
        }
        entry["prize_usd"] = r.get("prize_usd")
        entry["total_points"] = r.get("points")
        entry["total_kills"] = r.get("kills")
        to_insert.append(entry)

    if not to_insert:
        return 0
    resp = client.post(f"{SUPABASE_URL}/rest/v1/tournament_results", json=to_insert, headers={**h, "Prefer": "return=representation"})
    if resp.status_code in (200, 201):
        count = len(resp.json())
        print(f"{label}: {count}件登録")
        return count
    print(f"{label}: エラー {resp.status_code} {resp.text[:200]}")
    return 0


def create_tournament(data):
    resp = client.post(f"{SUPABASE_URL}/rest/v1/tournaments", json=[data], headers={**h, "Prefer": "return=representation"})
    if resp.status_code in (200, 201):
        return resp.json()[0]
    print(f"大会作成エラー: {resp.status_code} {resp.text[:200]}")
    return None


# ========================================
# Year 4 Championship（Dexertoデータ、40チーム）
# ========================================
y4_champ = [
    {"placement": 1, "team": "GoNext Esports", "prize_usd": 600000},
    {"placement": 2, "team": "Alliance", "prize_usd": 320000},
    {"placement": 3, "team": "Team Falcons", "prize_usd": 210000},
    {"placement": 4, "team": "ShopifyRebellion", "prize_usd": 170000},
    {"placement": 5, "team": "Virtus.pro", "prize_usd": 130000},
    {"placement": 6, "team": "Complexity Gaming", "prize_usd": 100000},
    {"placement": 7, "team": "Luminosity Gaming", "prize_usd": 80000},
    {"placement": 8, "team": "FURIA Esports", "prize_usd": 60000},
    {"placement": 9, "team": "VK Gaming", "prize_usd": 50000},
    {"placement": 10, "team": "Fnatic", "prize_usd": 40000},
    {"placement": 11, "team": "Aurora Gaming", "prize_usd": 32000},
    {"placement": 12, "team": "Guild Esports", "prize_usd": 30000},
    {"placement": 13, "team": "TSM", "prize_usd": 28000},
    {"placement": 14, "team": "Envy", "prize_usd": 26000},
    {"placement": 15, "team": "ENTER FORCE.36", "prize_usd": 24000},
    {"placement": 16, "team": "EXO Clan", "prize_usd": 22000},
    {"placement": 17, "team": "Liquid Alienware", "prize_usd": 21000},
    {"placement": 18, "team": "Noctem", "prize_usd": 20000},
    {"placement": 19, "team": "Team Burger", "prize_usd": 19000},
    {"placement": 20, "team": "Gaimin Gladiators", "prize_usd": 18000},
    {"placement": 21, "team": "100 Thieves"},
    {"placement": 22, "team": "GHS Professional"},
    {"placement": 23, "team": "Green Stego"},
    {"placement": 24, "team": "OrglessandHungry"},
    {"placement": 25, "team": "Zero Tenacity"},
    {"placement": 26, "team": "Cloud9"},
    {"placement": 27, "team": "Crazy Raccoon"},
    {"placement": 28, "team": "Dragons Esports"},
    {"placement": 29, "team": "FaZe Clan"},
    {"placement": 30, "team": "Disguised"},
    {"placement": 31, "team": "NRG"},
    {"placement": 32, "team": "Ninjas in Pyjamas"},
    {"placement": 33, "team": "Source XNY"},
    {"placement": 34, "team": "Supernova"},
    {"placement": 35, "team": "DreamFire"},
    {"placement": 36, "team": "Oblivion"},
    {"placement": 37, "team": "Reignite"},
    {"placement": 38, "team": "Shadow3690"},
    {"placement": 39, "team": "Stallions"},
    {"placement": 40, "team": "Meteor"},
]

# ========================================
# Year 4 Split 1 Playoffs（esports.gg、20チーム）
# ========================================
y4_split1 = [
    {"placement": 1, "team": "REJECT WINNITY"},
    {"placement": 2, "team": "DarkZero Esports"},
    {"placement": 3, "team": "Fnatic"},
    {"placement": 4, "team": "Siren"},
    {"placement": 5, "team": "Not Moist"},
    {"placement": 6, "team": "Aurora Gaming"},
    {"placement": 7, "team": "LEGND"},
    {"placement": 8, "team": "Luminosity Gaming"},
    {"placement": 9, "team": "Virtus.pro"},
    {"placement": 10, "team": "Disguised"},
    {"placement": 11, "team": "Cloud9"},
    {"placement": 12, "team": "OMiT"},
    {"placement": 13, "team": "Spacestation Gaming"},
    {"placement": 14, "team": "2R1C"},
    {"placement": 15, "team": "Team Liquid"},
    {"placement": 16, "team": "TSM"},
    {"placement": 17, "team": "Alliance"},
    {"placement": 18, "team": "o7"},
    {"placement": 19, "team": "Elevate"},
    {"placement": 20, "team": "KN"},
]

# ========================================
# 実行
# ========================================
total_results = 0
total_teams = 0

# Year 4 Championship（既存大会ID）
print("=== Year 4 Championship ===")
total_results += insert_results("a3b9c653-01ce-45d8-84cf-72d9fc09daa3", y4_champ, "Y4 Championship")

# Year 4 Split 1 Playoffs（既に投入済みならスキップ）
print("\n=== Year 4 Split 1 Playoffs ===")
existing_s1 = client.get(f"{SUPABASE_URL}/rest/v1/tournaments", params={"select": "id", "slug": "eq.algs-year-4-split-1-playoffs"}, headers=h).json()
if existing_s1:
    # 結果チェック
    existing_r = client.get(f"{SUPABASE_URL}/rest/v1/tournament_results", params={"select": "id", "tournament_id": f"eq.{existing_s1[0]['id']}", "limit": "1"}, headers=h).json()
    if existing_r:
        print("  既に結果あり。スキップ")
    else:
        total_results += insert_results(existing_s1[0]["id"], y4_split1, "Y4 Split 1 Playoffs")
else:
    t = create_tournament({
    "name": "ALGS Year 4 Split 1 Playoffs",
    "slug": "algs-year-4-split-1-playoffs",
    "series": "ALGS Year 4",
    "event_type": "playoffs",
    "region": "GLOBAL",
    "start_date": "2024-05-02",
    "end_date": "2024-05-05",
    "is_lan": True,
    "location": "Los Angeles, USA",
    "prize_pool_usd": 1000000,
    "status": "completed",
})
if t:
    total_results += insert_results(t["id"], y4_split1, "Y4 Split 1 Playoffs")

print(f"\n=== 完了: 結果{total_results}件 ===")
