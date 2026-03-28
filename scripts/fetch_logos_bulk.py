"""
ロゴなしチームのLiquipediaページからロゴを一括取得
→ public/logos/ に保存、teams.logo_url を更新

使い方:
  python fetch_logos_bulk.py --dry-run    # DB更新なし
  python fetch_logos_bulk.py              # 本番実行
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import json
import os
import re
import time
import argparse

LOGOS_DIR = "C:/Users/PCUser/Documents/MyApps/Apex-DB/web/public/logos"
os.makedirs(LOGOS_DIR, exist_ok=True)

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
lp_client = httpx.Client(timeout=30, headers=LP_HEADERS, follow_redirects=True)

BATCH_SIZE = 50
BATCH_DELAY = 3
IMAGE_DELAY = 1


def normalize(name):
    return "".join(c.lower() for c in name if c.isalnum())


def supabase_get_all(table, params):
    all_data = []
    offset = 0
    while True:
        p = {**params, "limit": "1000", "offset": str(offset)}
        resp = client.get(f"{SUPABASE_URL}/rest/v1/{table}", params=p, headers=DB_HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        all_data.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return all_data


def supabase_update_team(team_id, data):
    headers = {**DB_HEADERS, "Prefer": "return=minimal"}
    resp = client.patch(
        f"{SUPABASE_URL}/rest/v1/teams",
        params={"id": f"eq.{team_id}"},
        json=data,
        headers=headers,
    )
    return resp.status_code in (200, 204)


def batch_query_lp(titles):
    """Liquipedia APIでページをバッチ取得"""
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
    """Liquipedia検索API"""
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
                return data[1]
    except Exception:
        pass
    return []


def extract_logo_filename(wikitext):
    """wikitextからロゴファイル名を抽出（darkmode優先）"""
    if "Infobox team" not in wikitext:
        return None

    def is_valid_filename(f):
        """画像ファイル名として妥当かチェック"""
        if not f:
            return False
        # 明らかに別フィールドの値
        if f.startswith("|") or f.startswith("{{") or f.startswith("<!--"):
            return False
        # 拡張子チェック
        if any(f.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"]):
            return True
        # ファイル名っぽい（スペースあり、アルファベット含む、短すぎない）
        if len(f) > 3 and re.search(r"[a-zA-Z]", f) and "=" not in f:
            return True
        return False

    # imagedark優先
    for field in ["imagedark", "image"]:
        m = re.search(rf"\|\s*{field}\s*=\s*(.+?)(?:\n|\|)", wikitext)
        if m:
            filename = m.group(1).strip()
            if is_valid_filename(filename):
                return filename

    return None


def get_image_url(filename):
    """Liquipedia APIから画像の実URLを取得"""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        resp = lp_client.get(LP_API, params=params)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                # pid=-1でもimageinfoが返る場合がある（lpcommonsの画像）
                imageinfo = pdata.get("imageinfo", [])
                if imageinfo:
                    return imageinfo[0].get("url")
    except Exception:
        pass
    return None


def download_image(url, filepath):
    """画像をダウンロード"""
    try:
        resp = lp_client.get(url)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def main():
    parser = argparse.ArgumentParser(description="チームロゴ一括取得")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("Liquipedia チームロゴ一括取得")
    print("=" * 60)
    if args.dry_run:
        print("DRY-RUN モード\n")

    # ロゴなしチーム取得
    teams = supabase_get_all("teams", {
        "select": "id,name,slug,logo_url,liquipedia_url,is_active",
    })
    no_logo = [t for t in teams if not t.get("logo_url")]
    # activeチームを優先
    active_no_logo = [t for t in no_logo if t.get("is_active")]
    inactive_no_logo = [t for t in no_logo if not t.get("is_active")]

    print(f"全チーム: {len(teams)}")
    print(f"ロゴなし: {len(no_logo)} (active: {len(active_no_logo)}, inactive: {len(inactive_no_logo)})")

    # activeチームのみ処理（inactiveは省略）
    targets = active_no_logo
    print(f"\n対象: {len(targets)}チーム (activeのみ)")

    stats = {"found": 0, "downloaded": 0, "not_found": 0, "lp_requests": 0}

    # Phase 1: LP URLがあるチーム
    has_lp = [t for t in targets if t.get("liquipedia_url")]
    no_lp = [t for t in targets if not t.get("liquipedia_url")]
    print(f"  LP URLあり: {len(has_lp)}")
    print(f"  LP URLなし: {len(no_lp)}")

    # Phase 1: LP URLからタイトル抽出→バッチ取得
    print(f"\n--- Phase 1: LP URLあり ({len(has_lp)}チーム) ---")
    lp_teams = {}
    for t in has_lp:
        url = t["liquipedia_url"]
        title = url.split("/apexlegends/")[-1].replace("_", " ") if "/apexlegends/" in url else None
        if title:
            lp_teams[title] = t

    titles_list = list(lp_teams.keys())
    for i in range(0, len(titles_list), BATCH_SIZE):
        batch = titles_list[i:i+BATCH_SIZE]
        print(f"  バッチ {i//BATCH_SIZE + 1}/{(len(titles_list)-1)//BATCH_SIZE + 1}")

        pages = batch_query_lp(batch)
        stats["lp_requests"] += 1

        for title, wikitext in pages.items():
            team = lp_teams.get(title)
            if not team:
                for t, tm in lp_teams.items():
                    if normalize(t) == normalize(title):
                        team = tm
                        break
            if not team:
                continue

            logo_file = extract_logo_filename(wikitext)
            if not logo_file:
                continue

            stats["found"] += 1

            if args.dry_run:
                print(f"    {team['name']} → {logo_file}")
                continue

            # 画像URL取得→ダウンロード
            img_url = get_image_url(logo_file)
            stats["lp_requests"] += 1
            time.sleep(IMAGE_DELAY)

            if not img_url:
                continue

            ext = os.path.splitext(logo_file)[1] or ".png"
            local_path = os.path.join(LOGOS_DIR, f"{team['slug']}{ext}")
            if download_image(img_url, local_path):
                stats["lp_requests"] += 1
                db_path = f"/logos/{team['slug']}{ext}"
                update_data = {"logo_url": db_path}
                if not team.get("liquipedia_url"):
                    update_data["liquipedia_url"] = f"https://liquipedia.net/apexlegends/{title.replace(' ', '_')}"
                supabase_update_team(team["id"], update_data)
                stats["downloaded"] += 1
                print(f"    OK: {team['name']} → {db_path}")
            time.sleep(IMAGE_DELAY)

        time.sleep(BATCH_DELAY)

    # Phase 2: LP URLなし → 検索→取得
    print(f"\n--- Phase 2: LP URLなし ({len(no_lp)}チーム、検索) ---")

    # チーム名でバッチ検索（まず名前そのままでページ取得を試す）
    search_map = {}
    search_titles = []
    for t in no_lp:
        name = t["name"]
        search_titles.append(name)
        search_map[normalize(name)] = t

    # 重複除去
    seen = set()
    unique_titles = []
    for t in search_titles:
        n = normalize(t)
        if n not in seen and n:
            seen.add(n)
            unique_titles.append(t)

    for i in range(0, len(unique_titles), BATCH_SIZE):
        batch = unique_titles[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(unique_titles) - 1) // BATCH_SIZE + 1
        print(f"  バッチ {batch_num}/{total_batches}")

        pages = batch_query_lp(batch)
        stats["lp_requests"] += 1

        for title, wikitext in pages.items():
            norm_title = normalize(title)
            team = search_map.get(norm_title)
            if not team:
                for n, t in search_map.items():
                    if n in norm_title or norm_title in n:
                        team = t
                        break
            if not team:
                continue

            logo_file = extract_logo_filename(wikitext)
            if not logo_file:
                continue

            stats["found"] += 1

            if args.dry_run:
                print(f"    {team['name']} → {logo_file}")
                continue

            img_url = get_image_url(logo_file)
            stats["lp_requests"] += 1
            time.sleep(IMAGE_DELAY)

            if not img_url:
                continue

            ext = os.path.splitext(logo_file)[1] or ".png"
            local_path = os.path.join(LOGOS_DIR, f"{team['slug']}{ext}")
            if download_image(img_url, local_path):
                stats["lp_requests"] += 1
                db_path = f"/logos/{team['slug']}{ext}"
                lp_url = f"https://liquipedia.net/apexlegends/{title.replace(' ', '_')}"
                supabase_update_team(team["id"], {"logo_url": db_path, "liquipedia_url": lp_url})
                stats["downloaded"] += 1
                print(f"    OK: {team['name']} → {db_path}")
            time.sleep(IMAGE_DELAY)

        time.sleep(BATCH_DELAY)

    # レポート
    print(f"\n{'='*60}")
    print("結果レポート")
    print(f"{'='*60}")
    print(f"  ロゴ発見: {stats['found']}件")
    print(f"  ダウンロード: {stats['downloaded']}件")
    print(f"  Liquipediaリクエスト: {stats['lp_requests']}回")


if __name__ == "__main__":
    main()
