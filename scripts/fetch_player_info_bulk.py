"""
全選手のLiquipediaページからSNS・real_name・nationalityを一括取得
→ players テーブルを更新

使い方:
  python fetch_player_info_bulk.py --dry-run    # DB更新なし
  python fetch_player_info_bulk.py              # 本番実行
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse

CACHE_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/scripts/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LP_API = "https://liquipedia.net/apexlegends/api.php"
LP_HEADERS = {
    "User-Agent": "ApexEsportsDB/1.0 (https://apex-esports-db.vercel.app)",
    "Accept-Encoding": "gzip",
}

SUPABASE_URL = "https://lmuphucmbfhojuxzsajt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxtdXBodWNtYmZob2p1eHpzYWp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNjc2MjAsImV4cCI6MjA4OTk0MzYyMH0.1LQA_OQS39jQawNSYwoa_4kAGVaR5TqNWkfvBYfD-kU"

DB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

client = httpx.Client(timeout=30)
lp_client = httpx.Client(timeout=30, headers=LP_HEADERS)

# リクエスト間隔
BATCH_DELAY = 3  # バッチクエリ間（秒）
SEARCH_DELAY = 2  # 検索API間（秒）
BATCH_SIZE = 50   # MediaWiki APIの最大バッチサイズ


def normalize(name):
    return "".join(c.lower() for c in name if c.isalnum())


def supabase_get_all(table, params):
    all_data = []
    offset = 0
    while True:
        p = {**params, "limit": "1000", "offset": str(offset)}
        resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            print(f"  GET エラー: {resp.status_code}")
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return all_data


def supabase_update(player_id, data):
    headers = {**DB_HEADERS, "Prefer": "return=minimal"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/players",
        params={"id": f"eq.{player_id}"},
        json=data,
        headers=headers,
    )
    return resp.status_code in (200, 204)


def batch_query_lp(titles):
    """Liquipedia APIでページをバッチ取得（最大50件）"""
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }
    for attempt in range(3):
        try:
            resp = lp_client.get(LP_API, params=params)
        except Exception as e:
            print(f"    HTTPエラー: {e}")
            time.sleep(30)
            continue

        if resp.status_code == 429:
            wait = 60 * (attempt + 1)
            print(f"    レート制限。{wait}秒待機...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"    HTTPエラー: {resp.status_code}")
            return {}

        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        result = {}
        for pid, pdata in pages.items():
            if pid == "-1":
                continue
            title = pdata.get("title", "")
            revisions = pdata.get("revisions", [])
            if revisions:
                result[title] = revisions[0].get("*", "")
        return result

    return {}


def search_lp(query):
    """Liquipedia検索APIで選手ページを探す"""
    params = {
        "action": "opensearch",
        "search": query,
        "limit": "5",
        "format": "json",
    }
    try:
        resp = lp_client.get(LP_API, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) >= 2:
                return data[1]  # タイトルのリスト
    except Exception:
        pass
    return []


def extract_player_info(wikitext):
    """wikitextからSNS・real_name・nationalityを抽出"""
    info = {}

    # Infobox player チェック
    if "Infobox player" not in wikitext and "Player" not in wikitext:
        return None

    # real_name (romanized_name優先、なければname)
    for field in ["romanized_name", "name"]:
        m = re.search(rf"\|\s*{field}\s*=\s*(.+?)(?:\n|\|)", wikitext)
        if m:
            val = m.group(1).strip()
            # wikiリンク除去
            val = re.sub(r"\[\[([^|\]]+)\|?[^\]]*\]\]", r"\1", val)
            if val and len(val) > 1 and val != "N/A":
                info["real_name"] = val
                break

    # nationality
    m = re.search(r"\|\s*(?:country|nationality)\s*=\s*(\w+)", wikitext)
    if m:
        country = m.group(1).strip().lower()
        # 国コード変換（よくある国）
        COUNTRY_MAP = {
            "us": "us", "usa": "us", "unitedstates": "us",
            "jp": "jp", "japan": "jp",
            "kr": "kr", "korea": "kr", "southkorea": "kr",
            "gb": "gb", "uk": "gb", "unitedkingdom": "gb", "england": "gb", "scotland": "gb", "wales": "gb",
            "ca": "ca", "canada": "ca",
            "au": "au", "australia": "au",
            "se": "se", "sweden": "se",
            "de": "de", "germany": "de",
            "fr": "fr", "france": "fr",
            "br": "br", "brazil": "br",
            "ru": "ru", "russia": "ru",
            "dk": "dk", "denmark": "dk",
            "fi": "fi", "finland": "fi",
            "no": "no", "norway": "no",
            "es": "es", "spain": "es",
            "it": "it", "italy": "it",
            "nl": "nl", "netherlands": "nl",
            "pl": "pl", "poland": "pl",
            "th": "th", "thailand": "th",
            "id": "id", "indonesia": "id",
            "sg": "sg", "singapore": "sg",
            "my": "my", "malaysia": "my",
            "ph": "ph", "philippines": "ph",
            "tw": "tw", "taiwan": "tw",
            "hk": "hk", "hongkong": "hk",
            "mx": "mx", "mexico": "mx",
            "ar": "ar", "argentina": "ar",
            "cl": "cl", "chile": "cl",
            "in": "in", "india": "in",
            "cn": "cn", "china": "cn",
            "pt": "pt", "portugal": "pt",
            "be": "be", "belgium": "be",
            "at": "at", "austria": "at",
            "ch": "ch", "switzerland": "ch",
            "ie": "ie", "ireland": "ie",
            "nz": "nz", "newzealand": "nz",
            "za": "za", "southafrica": "za",
            "mm": "mm", "myanmar": "mm",
            "vn": "vn", "vietnam": "vn",
            "sa": "sa", "saudiarabia": "sa",
            "ae": "ae", "uae": "ae",
        }
        code = COUNTRY_MAP.get(country, country[:2] if len(country) == 2 else None)
        if code and len(code) == 2:
            info["nationality"] = code

    # SNS
    sns_fields = {
        "twitter": ("twitter_url", "https://x.com/{}"),
        "twitch": ("twitch_url", "https://twitch.tv/{}"),
        "youtube": ("youtube_url", "https://youtube.com/{}"),
    }

    for wiki_field, (db_field, url_tmpl) in sns_fields.items():
        m = re.search(rf"\|\s*{wiki_field}\s*=\s*(.+?)(?:\n|\|)", wikitext)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ("n/a", "none", ""):
                # URLかハンドルか判定
                if val.startswith("http"):
                    info[db_field] = val
                else:
                    # ハンドルからURL生成
                    handle = val.split("/")[-1].strip()
                    if handle:
                        info[db_field] = url_tmpl.format(handle)

    return info if info else None


def clean_ign(ign):
    """IGNからチームプレフィックスを除去して検索用の名前を生成"""
    # よくあるプレフィックス
    prefixes = [
        "FLCN ", "RC ", "Twitch ", "TTV ", "YT ", "TSM ", "NRG ", "C9 ",
        "LG ", "CLG ", "COL ", "SEN ", "FaZe ", "100T ", "G2 ",
    ]
    clean = ign
    for p in prefixes:
        if ign.startswith(p):
            clean = ign[len(p):]
            break
    return clean


def main():
    parser = argparse.ArgumentParser(description="選手情報一括取得")
    parser.add_argument("--dry-run", action="store_true", help="DB更新なし")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia 選手情報一括取得")
    print("=" * 60)

    if args.dry_run:
        print("DRY-RUN モード\n")

    # 全選手取得
    print("--- DB選手取得 ---")
    players = supabase_get_all("players", {
        "select": "id,ign,twitter_url,twitch_url,youtube_url,liquipedia_url,real_name,nationality",
    })
    print(f"  全選手: {len(players)}")

    # Phase 1: 既にLiquipedia URLがあるがSNS等が欠けてる選手
    phase1 = [p for p in players if p.get("liquipedia_url") and (
        not p.get("twitter_url") or not p.get("real_name")
    )]
    # Phase 2: Liquipedia URLがない選手
    phase2 = [p for p in players if not p.get("liquipedia_url")]

    print(f"  Phase 1（LP URLあり、情報不足）: {len(phase1)}")
    print(f"  Phase 2（LP URL未検索）: {len(phase2)}")

    stats = {"updated": 0, "found": 0, "not_found": 0, "lp_requests": 0}

    # === Phase 1: Liquipedia URLからページ取得 ===
    print(f"\n{'='*60}")
    print("Phase 1: LP URLあり選手の情報補完")
    print(f"{'='*60}")

    # URLからタイトルを抽出
    phase1_titles = {}
    for p in phase1:
        url = p["liquipedia_url"]
        # https://liquipedia.net/apexlegends/PlayerName → PlayerName
        title = url.split("/apexlegends/")[-1] if "/apexlegends/" in url else None
        if title:
            # URLデコード
            title = title.replace("_", " ").replace("%20", " ")
            phase1_titles[title] = p

    # バッチ取得
    titles_list = list(phase1_titles.keys())
    for i in range(0, len(titles_list), BATCH_SIZE):
        batch = titles_list[i:i+BATCH_SIZE]
        print(f"  バッチ {i//BATCH_SIZE + 1}/{(len(titles_list)-1)//BATCH_SIZE + 1} ({len(batch)}件)")

        pages = batch_query_lp(batch)
        stats["lp_requests"] += 1

        for title, wikitext in pages.items():
            player = phase1_titles.get(title)
            if not player:
                # 正規化して再マッチ
                for t, p in phase1_titles.items():
                    if normalize(t) == normalize(title):
                        player = p
                        break
            if not player:
                continue

            info = extract_player_info(wikitext)
            if not info:
                continue

            # 既存データと差分があるものだけ更新
            update = {}
            for field in ["real_name", "nationality", "twitter_url", "twitch_url", "youtube_url"]:
                if field in info and not player.get(field):
                    update[field] = info[field]

            if update:
                stats["found"] += 1
                if not args.dry_run:
                    supabase_update(player["id"], update)
                    stats["updated"] += 1
                else:
                    print(f"    {player['ign']}: {list(update.keys())}")

        time.sleep(BATCH_DELAY)

    print(f"  Phase 1 完了: {stats['found']}件の新情報")

    # === Phase 2: Liquipedia URLなし選手のページ検索 ===
    print(f"\n{'='*60}")
    print("Phase 2: LP URL未検索選手のページ探索")
    print(f"{'='*60}")

    # IGNでバッチ検索（まずIGNそのままでページ取得を試す）
    ign_to_player = {}
    search_titles = []
    for p in phase2:
        ign = p["ign"]
        clean = clean_ign(ign)
        # 検索候補: クリーンIGN（メイン）
        search_titles.append(clean)
        ign_to_player[normalize(clean)] = p
        # 元のIGNも候補に（異なる場合のみ）
        if clean != ign:
            ign_to_player[normalize(ign)] = p

    # 重複除去
    seen = set()
    unique_titles = []
    for t in search_titles:
        n = normalize(t)
        if n not in seen and n:
            seen.add(n)
            unique_titles.append(t)

    print(f"  検索対象: {len(unique_titles)}件")

    found_phase2 = 0
    not_found_phase2 = 0

    for i in range(0, len(unique_titles), BATCH_SIZE):
        batch = unique_titles[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(unique_titles) - 1) // BATCH_SIZE + 1
        print(f"  バッチ {batch_num}/{total_batches} ({len(batch)}件)")

        pages = batch_query_lp(batch)
        stats["lp_requests"] += 1

        matched_in_batch = 0
        for title, wikitext in pages.items():
            # タイトルからプレイヤーをマッチ
            norm_title = normalize(title)
            player = ign_to_player.get(norm_title)

            if not player:
                # 部分マッチ
                for norm_ign, p in ign_to_player.items():
                    if norm_ign in norm_title or norm_title in norm_ign:
                        player = p
                        break

            if not player:
                continue

            info = extract_player_info(wikitext)
            if not info:
                continue

            # LP URLも設定
            lp_url = f"https://liquipedia.net/apexlegends/{title.replace(' ', '_')}"

            update = {"liquipedia_url": lp_url}
            for field in ["real_name", "nationality", "twitter_url", "twitch_url", "youtube_url"]:
                if field in info and not player.get(field):
                    update[field] = info[field]

            found_phase2 += 1
            matched_in_batch += 1

            if not args.dry_run:
                supabase_update(player["id"], update)
                stats["updated"] += 1
            else:
                fields = [k for k in update if k != "liquipedia_url"]
                print(f"    {player['ign']} → {title} ({', '.join(fields) if fields else 'LP URLのみ'})")

        print(f"    マッチ: {matched_in_batch}/{len(batch)}")
        time.sleep(BATCH_DELAY)

    stats["found"] += found_phase2
    stats["not_found"] = len(unique_titles) - found_phase2

    # レポート
    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  Phase 1 情報補完: {stats['found'] - found_phase2}件")
    print(f"  Phase 2 新規発見: {found_phase2}件")
    print(f"  Phase 2 未発見: {stats['not_found']}件")
    print(f"  DB更新: {stats['updated']}件")
    print(f"  Liquipediaリクエスト: {stats['lp_requests']}回")


if __name__ == "__main__":
    main()
