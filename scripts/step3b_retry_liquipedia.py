"""
Step 3b: 未発見選手の再検索
- 先頭/末尾スペース除去して再検索
- Liquipedia Search APIで曖昧検索
- チーム名プレフィックス除去
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
from datetime import datetime

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

client = httpx.Client(timeout=30, headers=LP_HEADERS)

SNS_FIELDS = {
    "twitter": r"\|\s*twitter\s*=\s*([^\n|]+)",
    "twitch": r"\|\s*twitch\s*=\s*([^\n|]+)",
    "youtube": r"\|\s*youtube\s*=\s*([^\n|]+)",
    "youtube2": r"\|\s*youtube2\s*=\s*([^\n|]+)",
    "instagram": r"\|\s*instagram\s*=\s*([^\n|]+)",
    "tiktok": r"\|\s*tiktok\s*=\s*([^\n|]+)",
    "reddit": r"\|\s*reddit\s*=\s*([^\n|]+)",
    "mildom": r"\|\s*mildom\s*=\s*([^\n|]+)",
}

EXTRA_FIELDS = {
    "real_name": r"\|\s*(?:name|romanized_name)\s*=\s*([^\n|]+)",
    "birth_date": r"\|\s*birth_date\s*=\s*([^\n|]+)",
    "country": r"\|\s*country\s*=\s*([^\n|]+)",
    "team": r"\|\s*team\s*=\s*([^\n|]+)",
    "role": r"\|\s*role\s*=\s*([^\n|]+)",
    "input": r"\|\s*input\s*=\s*([^\n|]+)",
}


def build_sns_url(platform, handle):
    handle = handle.strip()
    if not handle:
        return None
    if handle.startswith("http"):
        return handle
    urls = {
        "twitter": f"https://x.com/{handle}",
        "twitch": f"https://twitch.tv/{handle}",
        "youtube": f"https://youtube.com/{handle}" if handle.startswith("@") or handle.startswith("channel/") else f"https://youtube.com/@{handle}",
        "youtube2": f"https://youtube.com/{handle}" if handle.startswith("@") or handle.startswith("channel/") else f"https://youtube.com/@{handle}",
        "instagram": f"https://instagram.com/{handle}",
        "tiktok": f"https://tiktok.com/@{handle}" if not handle.startswith("@") else f"https://tiktok.com/{handle}",
        "reddit": f"https://reddit.com/user/{handle}",
        "mildom": f"https://mildom.com/{handle}",
    }
    return urls.get(platform)


def extract_player_info(wikitext):
    info = {"sns": {}, "extra": {}}
    for field, pattern in SNS_FIELDS.items():
        m = re.search(pattern, wikitext, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("", "n/a", "none"):
                url = build_sns_url(field, val)
                if url:
                    info["sns"][field] = {"handle": val, "url": url}
    for field, pattern in EXTRA_FIELDS.items():
        m = re.search(pattern, wikitext, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("", "n/a", "none"):
                info["extra"][field] = val
    return info


def normalize_name(name):
    return "".join(c.lower() for c in name if c.isalnum())


def fetch_page(title):
    """1ページのwikitextを取得"""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
    }
    resp = client.get(LP_API, params=params)
    if resp.status_code != 200:
        return None
    pages = resp.json().get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if int(page_id) < 0:
            return None
        revs = page.get("revisions", [])
        if revs:
            content = revs[0].get("slots", {}).get("main", {}).get("*", "")
            if not content:
                content = revs[0].get("*", "")
            return content
    return None


def search_player(query):
    """Liquipedia検索APIで選手を検索"""
    params = {
        "action": "opensearch",
        "search": query,
        "namespace": "0",
        "limit": "5",
        "format": "json",
    }
    resp = client.get(LP_API, params=params)
    if resp.status_code != 200:
        return []
    data = resp.json()
    if len(data) >= 2:
        return data[1]  # タイトルのリスト
    return []


def main():
    print("=" * 60)
    print("Step 3b: 未発見選手の再検索")
    print("=" * 60)

    # 既存データ読み込み
    with open(os.path.join(CACHE_DIR, "liquipedia_sns.json"), "r", encoding="utf-8") as f:
        sns_data = json.load(f)

    with open(os.path.join(CACHE_DIR, "algs_rosters.json"), "r", encoding="utf-8") as f:
        algs_data = json.load(f)

    # 未発見選手のリスト（チーム情報付き）
    not_found_set = set(sns_data["not_found"])
    not_found_with_team = []
    for region, teams in algs_data["regions"].items():
        for team in teams:
            for player in team["players"]:
                if player["ign"] in not_found_set:
                    not_found_with_team.append({
                        "ign": player["ign"],
                        "team": team["name"],
                        "region": region,
                    })

    print(f"未発見選手数: {len(not_found_with_team)}")

    found_extra = {}
    still_not_found = []

    for i, player in enumerate(not_found_with_team):
        ign = player["ign"]
        stripped = ign.strip()

        # まずスペース除去版で直接検索
        if stripped != ign:
            wikitext = fetch_page(stripped)
            time.sleep(2)
            if wikitext:
                info = extract_player_info(wikitext)
                norm = normalize_name(ign)
                found_extra[norm] = {
                    "ign": ign,
                    "team": player["team"],
                    "region": player["region"],
                    "liquipedia_title": stripped,
                    "liquipedia_url": f"https://liquipedia.net/apexlegends/{stripped.replace(' ', '_')}",
                    "match_method": "whitespace_fix",
                    **info,
                }
                print(f"  [{i+1}] {ign} → {stripped} (スペース修正) ✓")
                continue

        # プレフィックス除去（"oh Nocturnal" → "Nocturnal", "Twitch Fredstxr" → "Fredstxr"）
        parts = stripped.split()
        if len(parts) > 1:
            suffix = parts[-1]
            wikitext = fetch_page(suffix)
            time.sleep(2)
            if wikitext and "{{Infobox player" in wikitext.lower():
                info = extract_player_info(wikitext)
                norm = normalize_name(ign)
                found_extra[norm] = {
                    "ign": ign,
                    "team": player["team"],
                    "region": player["region"],
                    "liquipedia_title": suffix,
                    "liquipedia_url": f"https://liquipedia.net/apexlegends/{suffix.replace(' ', '_')}",
                    "match_method": "prefix_removed",
                    **info,
                }
                print(f"  [{i+1}] {ign} → {suffix} (プレフィックス除去) ✓")
                continue

        # Liquipedia検索APIで曖昧検索
        search_results = search_player(stripped)
        time.sleep(2)

        matched = False
        for result_title in search_results:
            # 結果が選手ページかチェック（ざっくり名前が一致するか）
            if normalize_name(stripped) in normalize_name(result_title) or normalize_name(result_title) in normalize_name(stripped):
                wikitext = fetch_page(result_title)
                time.sleep(2)
                if wikitext and "{{Infobox player" in wikitext.lower():
                    info = extract_player_info(wikitext)
                    norm = normalize_name(ign)
                    found_extra[norm] = {
                        "ign": ign,
                        "team": player["team"],
                        "region": player["region"],
                        "liquipedia_title": result_title,
                        "liquipedia_url": f"https://liquipedia.net/apexlegends/{result_title.replace(' ', '_')}",
                        "match_method": "search_api",
                        **info,
                    }
                    print(f"  [{i+1}] {ign} → {result_title} (検索API) ✓")
                    matched = True
                    break

        if not matched:
            still_not_found.append(player)
            if (i + 1) % 20 == 0:
                print(f"  ... {i+1}/{len(not_found_with_team)} 処理済み")

    # 既存データに追加
    for norm, info in found_extra.items():
        sns_data["players"][norm] = info

    # SNSカバー率再計算
    sns_counts = {}
    for p in sns_data["players"].values():
        for platform in p.get("sns", {}):
            sns_counts[platform] = sns_counts.get(platform, 0) + 1

    sns_data["total_found"] = len(sns_data["players"])
    sns_data["total_not_found"] = len(still_not_found)
    sns_data["sns_coverage"] = sns_counts
    sns_data["not_found"] = [p["ign"] for p in still_not_found]
    sns_data["retry_at"] = datetime.now().isoformat()
    sns_data["retry_found"] = len(found_extra)

    # 保存
    output_path = os.path.join(CACHE_DIR, "liquipedia_sns.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sns_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"再検索結果:")
    print(f"  新規発見: {len(found_extra)} 選手")
    print(f"  合計発見: {len(sns_data['players'])} / 478 選手")
    print(f"  最終未発見: {len(still_not_found)} 選手")
    print(f"\nSNSカバー率（更新後）:")
    for platform, count in sorted(sns_counts.items(), key=lambda x: -x[1]):
        pct = count / len(sns_data['players']) * 100 if sns_data['players'] else 0
        print(f"  {platform}: {count} ({pct:.1f}%)")
    print(f"\n保存先: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
