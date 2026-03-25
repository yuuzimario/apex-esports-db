"""
Step 3: Liquipedia MediaWiki APIから選手のSNS情報をバルク取得
ALGS APIで取得した479選手のTwitter/Twitch/YouTube/Instagram等を収集
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
os.makedirs(CACHE_DIR, exist_ok=True)

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

client = httpx.Client(timeout=30, headers=LP_HEADERS)

# SNSフィールドの抽出パターン
SNS_FIELDS = {
    "twitter": r"\|\s*twitter\s*=\s*([^\n|]+)",
    "twitch": r"\|\s*twitch\s*=\s*([^\n|]+)",
    "youtube": r"\|\s*youtube\s*=\s*([^\n|]+)",
    "youtube2": r"\|\s*youtube2\s*=\s*([^\n|]+)",
    "instagram": r"\|\s*instagram\s*=\s*([^\n|]+)",
    "tiktok": r"\|\s*tiktok\s*=\s*([^\n|]+)",
    "reddit": r"\|\s*reddit\s*=\s*([^\n|]+)",
    "mildom": r"\|\s*mildom\s*=\s*([^\n|]+)",
    "discord": r"\|\s*discord\s*=\s*([^\n|]+)",
}

# 追加情報のパターン
EXTRA_FIELDS = {
    "real_name": r"\|\s*(?:name|romanized_name)\s*=\s*([^\n|]+)",
    "birth_date": r"\|\s*birth_date\s*=\s*([^\n|]+)",
    "country": r"\|\s*country\s*=\s*([^\n|]+)",
    "team": r"\|\s*team\s*=\s*([^\n|]+)",
    "role": r"\|\s*role\s*=\s*([^\n|]+)",
    "input": r"\|\s*input\s*=\s*([^\n|]+)",
}


def normalize_name(name):
    """名前を正規化"""
    return "".join(c.lower() for c in name if c.isalnum())


def build_sns_url(platform, handle):
    """ハンドルからURLを構築"""
    handle = handle.strip()
    if not handle:
        return None

    # 既にURLの場合はそのまま
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
    """wikitextからSNS情報と追加情報を抽出"""
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


def fetch_player_pages_bulk(titles):
    """複数ページのwikitextをバルク取得（最大50件/リクエスト）"""
    results = {}
    batch_size = 50  # MediaWikiは50件まで

    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        titles_str = "|".join(batch)

        params = {
            "action": "query",
            "titles": titles_str,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
        }

        try:
            resp = client.get(LP_API, params=params)
            if resp.status_code != 200:
                print(f"  APIエラー: {resp.status_code} (batch {i//batch_size + 1})")
                time.sleep(5)
                continue

            data = resp.json()
            pages = data.get("query", {}).get("pages", {})

            for page_id, page in pages.items():
                if int(page_id) < 0:
                    continue  # ページが存在しない
                title = page.get("title", "")
                revs = page.get("revisions", [])
                if revs:
                    # rvslots=main の場合
                    content = revs[0].get("slots", {}).get("main", {}).get("*", "")
                    if not content:
                        content = revs[0].get("*", "")
                    if content:
                        results[title] = content

        except Exception as e:
            print(f"  リクエストエラー: {e}")

        # レート制限: 2秒間隔
        time.sleep(2)
        print(f"  バッチ {i//batch_size + 1}/{(len(titles) + batch_size - 1)//batch_size} 完了 ({len(results)} ページ取得)")

    return results


def main():
    print("=" * 60)
    print("Step 3: Liquipedia SNS情報バルク取得")
    print("=" * 60)

    # ALGS APIデータから選手名リストを構築
    with open(os.path.join(CACHE_DIR, "algs_rosters.json"), "r", encoding="utf-8") as f:
        algs_data = json.load(f)

    # 全選手のIGNを収集（重複排除）
    all_players = {}
    for region, teams in algs_data["regions"].items():
        for team in teams:
            for player in team["players"]:
                ign = player["ign"]
                # Liquipediaページタイトルはそのまま選手名を使う
                # プレフィックス（チーム名等）がついている場合は除去
                clean_ign = ign
                # "FLCN ImperialHal" → "ImperialHal"
                # "RC Axis" → "Axis"
                # ただし、スペース区切りの名前もある（"15Years FengchunOvO"）
                # まずはそのまま検索し、ダメなら加工を試みる
                all_players[normalize_name(clean_ign)] = {
                    "ign": ign,
                    "team": team["name"],
                    "region": region,
                }

    print(f"対象選手数: {len(all_players)}")

    # チーム名プレフィックスの除去バリエーションも用意
    search_titles = []
    ign_to_norm = {}

    for norm, info in all_players.items():
        ign = info["ign"]
        search_titles.append(ign)
        ign_to_norm[ign] = norm

        # プレフィックス除去版も追加（スペースで分割して最後の単語のみ）
        parts = ign.split()
        if len(parts) > 1:
            # "FLCN ImperialHal" → "ImperialHal"
            suffix = parts[-1]
            if suffix != ign:
                search_titles.append(suffix)
                ign_to_norm[suffix] = norm

    # 重複除去
    search_titles = list(dict.fromkeys(search_titles))
    print(f"検索タイトル数: {len(search_titles)}（バリエーション含む）")

    # バルク取得
    print("\nLiquipedia APIバルク取得開始...")
    wiki_pages = fetch_player_pages_bulk(search_titles)
    print(f"\n取得成功: {len(wiki_pages)} ページ")

    # SNS情報抽出
    player_sns = {}
    for title, wikitext in wiki_pages.items():
        norm = ign_to_norm.get(title)
        if norm and norm in all_players:
            info = extract_player_info(wikitext)
            player_info = all_players[norm]
            player_sns[norm] = {
                "ign": player_info["ign"],
                "team": player_info["team"],
                "region": player_info["region"],
                "liquipedia_title": title,
                "liquipedia_url": f"https://liquipedia.net/apexlegends/{title.replace(' ', '_')}",
                **info,
            }

    # 統計
    sns_counts = {}
    for p in player_sns.values():
        for platform in p.get("sns", {}):
            sns_counts[platform] = sns_counts.get(platform, 0) + 1

    # 結果
    result = {
        "source": "liquipedia.net/apexlegends",
        "fetched_at": datetime.now().isoformat(),
        "total_searched": len(all_players),
        "total_found": len(player_sns),
        "total_not_found": len(all_players) - len(player_sns),
        "sns_coverage": sns_counts,
        "players": player_sns,
        "not_found": [
            info["ign"] for norm, info in all_players.items()
            if norm not in player_sns
        ],
    }

    # 保存
    output_path = os.path.join(CACHE_DIR, "liquipedia_sns.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"SNS情報取得結果:")
    print(f"  検索: {len(all_players)} 選手")
    print(f"  発見: {len(player_sns)} 選手")
    print(f"  未発見: {len(all_players) - len(player_sns)} 選手")
    print(f"\nSNSカバー率:")
    for platform, count in sorted(sns_counts.items(), key=lambda x: -x[1]):
        pct = count / len(player_sns) * 100 if player_sns else 0
        print(f"  {platform}: {count} ({pct:.1f}%)")
    print(f"\n未発見選手（先頭20件）:")
    for ign in result["not_found"][:20]:
        print(f"  - {ign}")
    print(f"\n保存先: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
