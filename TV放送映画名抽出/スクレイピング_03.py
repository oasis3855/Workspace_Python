"""WOWOWシネマ番組表抽出・公開年＆評価＆原題照会ツール

指定された日付のBS番組表から特定チャンネルの映画情報を抽出し、
映画.comのデータ（公開年、評価、ID、原題）と照合してデータベース化およびCSV出力します。

■ アップデート (v1.4.0):
- get_original_title 関数を実装し、映画個別ページから原題を抽出する機能を追加。
- すべての通知メッセージからアイコン（絵文字）を除去。
- キャッシュに原題がない場合、IDをもとに自動補完するロジックを実装。

Version: 1.4.0
Author: Google Gemini
Requires: Python 3.9+, requests, beautifulsoup4, pandas
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Any

# ==========================================
# 設定エリア（グローバル変数）
# ==========================================
TARGET_CHANNEL_PREFIX: str = "193-"
DB_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie_database.csv")
DB_COLUMNS: List[str] = ['映画名', '公開年', '評価', 'ID', '原題', 'IMDb']
# ==========================================


def load_movie_db() -> Dict[str, Dict[str, str]]:
    """ローカルのCSVファイルから映画データベースを読み込む。"""
    if os.path.exists(DB_FILE):
        try:
            df_db = pd.read_csv(DB_FILE, encoding='utf_8_sig')
            # 欠損値を空文字に変換
            df_db = df_db.fillna("")
            return df_db.set_index('映画名').to_dict('index')
        except Exception as e:
            print(f"DB読み込み警告: {e}")
    return {}


def save_movie_db(movie_cache: Dict[str, Dict[str, str]]) -> None:
    """現在のキャッシュをローカルのCSVファイルに保存する。"""
    df_db = pd.DataFrame.from_dict(movie_cache, orient='index').reset_index()
    df_db.columns = DB_COLUMNS
    df_db.to_csv(DB_FILE, index=False, encoding='utf_8_sig')
    print(f"--- データベースを更新しました (合計: {len(df_db)}件) ---")


def is_cinema_in_title(title: str) -> bool:
    """番組名に映画を示す記号「🈙」が含まれているか判定する。"""
    return '🈙' in title


def is_length_one_hour_over(start_str: str, end_str: str) -> bool:
    """番組の放送時間が1時間を超えているか判定する。"""
    try:
        fmt = '%Y%m%d%H%M'
        diff = datetime.strptime(end_str, fmt) - datetime.strptime(start_str, fmt)
        return diff > timedelta(hours=1)
    except BaseException:
        return False


def clean_title(title: str) -> str:
    """番組名から属性記号や括弧内の不要なテキストを除去する。"""
    title = re.sub(r'[\[［\(（].*?[\]］\)）]', '', title)
    symbols = ['🈙', '🅍', '🈑', '🈔', '🈓', '🈗', '🈘', '🈚', '🈛', '🈜', '🈝', '🈞', '🈟', '㊙', '🈠']
    for s in symbols:
        title = title.replace(s, '')
    return title.strip()


def get_original_title(movie_id: str) -> str:
    """映画の個別ページから原題を取得する。

    Args:
        movie_id (str): 映画.comの映画ID。

    Returns:
        str: 取得した原題。見つからない場合は空文字。
    """
    if not movie_id:
        return ""

    url = f"https://eiga.com/movie/{movie_id}/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        time.sleep(1.0)
        res = requests.get(url, headers=headers)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        data_tag = soup.find('p', class_='data')
        if data_tag:
            # HTMLの中身（タグ含む）を文字列として取得
            html_content = data_tag.decode_contents()

            # 「原題：」または「原題または英題：」から、次の <br までの最短一致を抽出
            # 改行が含まれる場合も想定し、末尾は <br か 文字列の終わり($) を指定
            pattern = r'(?:原題または英題：|原題：)(.*?)(?:<br|/?>|$)'
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)

            if match:
                # 抽出した文字列から、念のため残ったHTMLタグを除去して返す
                original_title = match.group(1).strip()
                return re.sub(r'<[^>]+>', '', original_title)

    except Exception as e:
        print(f"原題取得エラー (ID: {movie_id}): {e}")

    return ""


def get_movie_info(cleaned_title: str, movie_cache: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """映画の各種情報を取得する。DBにない場合や原題が欠けている場合はWebから補填する。"""
    if not cleaned_title:
        return {k: "" for k in DB_COLUMNS[1:]}

    # 1. キャッシュチェック
    if cleaned_title in movie_cache:
        info = movie_cache[cleaned_title]
        # IDがあるが原題が空の場合、自動で補完を試みる
        if info.get("ID") and not info.get("原題"):
            print(f"原題を補完中: {cleaned_title}")
            info["原題"] = get_original_title(info["ID"])
        return info

    # 2. Web検索
    search_url = f"https://eiga.com/search/{cleaned_title}/movie/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        time.sleep(1.0)
        res = requests.get(search_url, headers=headers)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        movie_items = soup.select('section#rslt-movie ul.list-tile > li')
        candidates: List[Dict[str, str]] = []

        if movie_items:
            for item in movie_items:
                title_tag = item.find('p', class_='title')
                time_tag = item.find('small', class_='time')
                rating_tag = item.find('p', class_='rating-star')
                link_tag = item.find('a')

                if title_tag and time_tag:
                    found_title = title_tag.get_text(strip=True)

                    movie_id = ""
                    if link_tag and 'href' in link_tag.attrs:
                        id_match = re.search(r'/movie/(\d+)/', link_tag['href'])
                        movie_id = id_match.group(1) if id_match else ""

                    year_match = re.search(r'\d{4}', time_tag.get_text(strip=True))
                    year = year_match.group() if year_match else "不明"

                    rating = rating_tag.get_text(strip=True) if rating_tag else "-"
                    if not rating:
                        rating = "-"

                    movie_data = {
                        "公開年": year, "評価": rating, "ID": movie_id,
                        "原題": "", "IMDb": ""
                    }

                    if found_title == cleaned_title:
                        # 完全一致した場合、その場で原題も取得
                        movie_data["原題"] = get_original_title(movie_id)
                        movie_cache[cleaned_title] = movie_data
                        return movie_data

                    movie_data["映画名"] = found_title
                    candidates.append(movie_data)

        # 3. ユーザー選択
        selected_data = {k: ("不明" if k == "公開年" else "-" if k == "評価" else "")
                         for k in DB_COLUMNS[1:]}
        if candidates:
            print(f"\n「{cleaned_title}」の一致候補:")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}: {c['映画名']} ({c['公開年']}) [評価:{c['評価']}]")
            print(f"  0: スキップ")

            while True:
                choice = input(f"選択 (0-{len(candidates)}): ").strip()
                if choice == "0":
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    target = candidates[int(choice) - 1]
                    # 選択された候補の原題を取得
                    orig_title = get_original_title(target["ID"])
                    selected_data = {
                        "公開年": target["公開年"], "評価": target["評価"],
                        "ID": target["ID"], "原題": orig_title, "IMDb": ""
                    }
                    break
                print("無効な入力です。")

        movie_cache[cleaned_title] = selected_data
        return selected_data

    except Exception as e:
        print(f"検索エラー: {e}")
        return {k: "" for k in DB_COLUMNS[1:]}


def main() -> None:
    """メイン実行処理。"""
    print(f"=== 番組表抽出ツール v1.4.0 (対象ID: {TARGET_CHANNEL_PREFIX}) ===")

    default_date = datetime.now().strftime('%Y%m%d')
    user_input = input(f"取得日(8桁)を入力 [デフォルト: {default_date}] > ").strip()
    target_date = user_input if user_input else default_date

    if not (target_date.isdigit() and len(target_date) == 8):
        print(f"エラー: '{target_date}' は無効な形式です。8桁の数字で入力してください。")
        return

    url = f"https://bangumi.org/epg/bs?broad_cast_date={target_date}"
    movie_cache = load_movie_db()

    print(f"\nデータ取得中 [対象: {TARGET_CHANNEL_PREFIX} / 日付: {target_date}]...")
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"通信エラー: {e}")
        return

    program_items = soup.find_all(
        'li', attrs={
            'se-id': lambda x: x and x.startswith(TARGET_CHANNEL_PREFIX)})

    if not program_items:
        print(f"該当チャンネルのデータが見つかりませんでした。")
        return

    final_results: List[List[str]] = []
    for item in program_items:
        s, e = item.get('s'), item.get('e')
        title_tag = item.find('p', class_='program_title')
        if not (s and e and title_tag):
            continue

        raw_title = title_tag.get_text(strip=True)
        if not is_cinema_in_title(raw_title) or not is_length_one_hour_over(s, e):
            continue

        cleaned_title = clean_title(raw_title)
        info = get_movie_info(cleaned_title, movie_cache)

        dt_str = datetime.strptime(s, '%Y%m%d%H%M').strftime('%Y/%m/%d %H:%M')
        final_results.append([
            dt_str, cleaned_title, info["公開年"], info["評価"],
            info["ID"], info["原題"], info["IMDb"]
        ])
        print(f"採用: [{dt_str}] {cleaned_title} ({info['公開年']}) 原題: {info['原題']}")

    if final_results:
        out_cols = ['日時', '番組名', '公開年', '評価', 'ID', '原題', 'IMDb']
        df = pd.DataFrame(final_results, columns=out_cols)

        clean_id = TARGET_CHANNEL_PREFIX.replace("-", "")
        output_path = os.path.join(
            os.path.dirname(DB_FILE),
            f"channel_{clean_id}_{target_date}.csv")

        df.to_csv(output_path, index=False, encoding='utf_8_sig')
        print(f"\n保存完了: {output_path}")
        save_movie_db(movie_cache)
    else:
        print("\n条件に一致する映画はありませんでした。")


if __name__ == "__main__":
    main()
