#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""映画番組表抽出・映画情報総合照会ツール

Version:
    1.0.0 (2026/02/26)
    1.1.0 (2026/02/26) 映画.comの評価値を追加
    1.4.0 (2026/02/28)
    1.6.1 (2026/03/01) IMDbの評価値を追加
Author:
    Google Gemini
"""

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import pandas as pd
import re
import requests
import time
from typing import Dict, List, Optional, Tuple, Any
import urllib.parse

# ==========================================
# 設定エリア（グローバル変数）
# ==========================================
TARGET_CHANNEL_PREFIX: str = "193-"     # 193ch = WOWWOWシネマ
DB_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie_database.csv")
DB_COLUMNS: List[str] = ['映画名', '公開年', '評価', 'ID', '原題', 'IMDb']
# ==========================================


def load_movie_db() -> Dict[str, Dict[str, str]]:
    """ローカルのCSVファイルから映画データベースを読み込む。

    Returns:
        Dict[str, Dict[str, str]]: 映画名をキーとし、詳細情報（公開年、評価等）を値とする辞書。
            ファイルが存在しない、または読み込みに失敗した場合は空の辞書を返す。
    """
    if os.path.exists(DB_FILE):
        try:
            df_db = pd.read_csv(DB_FILE, encoding='utf_8_sig')
            df_db = df_db.fillna("")
            return df_db.set_index('映画名').to_dict('index')
        except Exception as e:
            print(f"DB読み込み警告: {e}")
    return {}


def save_movie_db(movie_cache: Dict[str, Dict[str, str]]) -> None:
    """現在のキャッシュをローカルのCSVファイルに保存する。

    Args:
        movie_cache (Dict[str, Dict[str, str]]): 保存対象となる映画データの辞書。
    """
    df_db = pd.DataFrame.from_dict(movie_cache, orient='index').reset_index()
    df_db.columns = DB_COLUMNS
    df_db.to_csv(DB_FILE, index=False, encoding='utf_8_sig')
    print(f"--- データベースを更新しました (合計: {len(df_db)}件) ---")


def is_cinema_in_title(title: str) -> bool:
    """番組名に映画を示す記号「🈙」が含まれているか判定する。

    Args:
        title (str): 判定対象の番組タイトル。

    Returns:
        bool: 「🈙」が含まれている場合はTrue、そうでない場合はFalse。
    """
    return '🈙' in title


def is_length_one_hour_over(start_str: str, end_str: str) -> bool:
    """番組の放送時間が1時間を超えているか判定する。

    Args:
        start_str (str): 放送開始時間（YYYYMMDDHHMM形式）。
        end_str (str): 放送終了時間（YYYYMMDDHHMM形式）。

    Returns:
        bool: 放送時間が1時間を超える場合はTrue、そうでない場合はFalse。
    """
    try:
        fmt = '%Y%m%d%H%M'
        diff = datetime.strptime(end_str, fmt) - datetime.strptime(start_str, fmt)
        return diff > timedelta(hours=1)
    except BaseException:
        return False


def clean_title(title: str) -> str:
    """番組名から属性記号や括弧内の不要なテキストを除去する。

    Args:
        title (str): 処理前の番組タイトル。

    Returns:
        str: 記号や括弧内テキストを除去したクリーンな映画タイトル。
    """
    title = re.sub(r'[\[［\(（].*?[\]］\)）]', '', title)
    symbols = ['🈙', '🅍', '🈑', '🈔', '🈓', '🈗', '🈘', '🈚', '🈛', '🈜', '🈝', '🈞', '🈟', '㊙', '🈠']
    for s in symbols:
        title = title.replace(s, '')
    return title.strip()


def get_original_title(movie_id: str) -> str:
    """映画.comの個別ページから原題を取得する。

    Args:
        movie_id (str): 映画.comの映画ID。

    Returns:
        str: 取得した原題。見つからない場合は空文字を返す。
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
            html_content = data_tag.decode_contents()
            pattern = r'(?:原題または英題：|原題：)(.*?)(?:<br|/?>|$)'
            match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)

            if match:
                original_title = match.group(1).strip()
                return re.sub(r'<[^>]+>', '', original_title)

    except Exception as e:
        print(f"原題取得エラー (ID: {movie_id}): {e}")
    return ""


def get_imdb_rating(original_title: str, release_year: str) -> str:
    """IMDbの検索結果一覧からスクレイピングしてRatingを取得する。

    タイトルが完全一致しない場合は候補を表示し、ユーザーに選択を促す。

    Args:
        original_title (str): 照会する映画の原題。
        release_year (str): 公開年（4桁の数字）。

    Returns:
        str: IMDbのRating値。取得できなかった場合は空文字、または「-」を返す。
    """
    if not original_title or not release_year:
        return ""

    # 公開年の前後1年を含めて検索URLを作成
    try:
        base_year = int(release_year)
        start_year, end_year = base_year - 1, base_year + 1
    except ValueError:
        start_year, end_year = release_year, release_year

    # encoded_title = requests.utils.quote(original_title) # type: ignore
    encoded_title = urllib.parse.quote(original_title)
    search_url = f"https://www.imdb.com/search/title/?title={encoded_title}&release_date={start_year}-01-01,{end_year}-12-31&title_type=feature"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        time.sleep(1.5)
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # 候補映画のリストアイテムを取得
        items = soup.select('li.ipc-metadata-list-summary-item')
        candidates: List[Dict[str, str]] = []

        for item in items:
            title_tag = item.select_one('h3.ipc-title__text')
            rating_tag = item.select_one('span.ipc-rating-star--rating')

            if title_tag:
                # タイトル取得（「1. Movie Title」のような番号を除去）
                raw_name = title_tag.get_text(strip=True)
                found_name = re.sub(r'^\d+\.\s+', '', raw_name)

                # Rating取得
                rating = rating_tag.get_text(strip=True) if rating_tag else "-"

                # タイトルが完全一致（大文字小文字無視）なら即時確定
                if found_name.lower() == original_title.lower():
                    return rating

                candidates.append({"title": found_name, "rating": rating})

        # 完全一致がなかった場合のユーザー選択
        if candidates:
            print(f"\nIMDbの候補一覧 (検索: {original_title}):")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}: {c['title']} [Rating: {c['rating']}]")
            print(f"  0: スキップ")

            while True:
                choice = input(f"IMDb選択 (0-{len(candidates)}): ").strip()
                if choice == "0":
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    return candidates[int(choice) - 1]["rating"]
                print("無効な入力です。")

    except Exception as e:
        print(f"IMDb取得エラー ({original_title}): {e}")

    return ""


def get_movie_info(cleaned_title: str, movie_cache: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """映画の各種情報を取得する。DBにない場合や原題が欠けている場合は映画.comのWebをスクレイピングして補填する。

    Args:
        cleaned_title (str): 検索対象のクリーンな映画タイトル。
        movie_cache (Dict[str, Dict[str, str]]): 現在読み込まれている映画データベース。

    Returns:
        Dict[str, str]: 公開年、評価、ID、原題、IMDbを含む情報の辞書。
    """
    if not cleaned_title:
        return {k: "" for k in DB_COLUMNS[1:]}

    # 1. キャッシュチェック
    if cleaned_title in movie_cache:
        info = movie_cache[cleaned_title]
        if info.get("ID") and not info.get("原題"):
            print(f"原題をmovie_databaseより補完中: {cleaned_title}")
            info["原題"] = get_original_title(info["ID"])
        return info

    # 2. Web検索
    search_url = f"https://eiga.com/search/{cleaned_title}/movie/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print(f"映画.comから情報を取得中: {cleaned_title}")

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
                    id_match = re.search(r'/movie/(\d+)/', link_tag['href']) if link_tag else None
                    movie_id = id_match.group(1) if id_match else ""
                    year_match = re.search(r'\d{4}', time_tag.get_text(strip=True))
                    year = year_match.group() if year_match else "不明"
                    rating = rating_tag.get_text(strip=True) if rating_tag else "-"

                    movie_data = {"公開年": year, "評価": rating, "ID": movie_id, "原題": "", "IMDb": ""}

                    # 映画.comから得た映画名と、番組表から得た映画名の文字列が完全一致した場合は、確定する
                    if found_title == cleaned_title:
                        movie_data["原題"] = get_original_title(movie_id)
                        movie_cache[cleaned_title] = movie_data
                        return movie_data

                    movie_data["映画名"] = found_title
                    candidates.append(movie_data)

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
                    orig_title = get_original_title(target["ID"])
                    selected_data = {
                        "公開年": target["公開年"],
                        "評価": target["評価"],
                        "ID": target["ID"],
                        "原題": orig_title,
                        "IMDb": ""}
                    break
                print("無効な入力です。")

        movie_cache[cleaned_title] = selected_data
        return selected_data

    except Exception as e:
        print(f"検索エラー: {e}")
        return {k: "" for k in DB_COLUMNS[1:]}


def fetch_program_items(target_date: str, prefix: str) -> List[Any]:
    """指定した日付の番組表を取得し、特定のチャンネルでフィルタリングしたリストを返す。

    Args:
        target_date (str): 取得対象日（YYYYMMDD形式）。
        prefix (str): 抽出対象のチャンネル接頭辞（例: "193-"）。

    Returns:
        List[Any]: 条件に合致する番組情報（BeautifulSoupのTagオブジェクト）のリスト。
    """
    url = f"https://bangumi.org/epg/bs?broad_cast_date={target_date}"

    print(f"データ取得中 [日付: {target_date}]...")
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        # チャンネルIDの接頭辞でフィルタリング
        return soup.find_all('li', attrs={'se-id': lambda x: x and x.startswith(prefix)})

    except Exception as e:
        print(f"通信エラー: {e}")
        return []


def process_and_save_results(
        all_program_items: List[Any], movie_cache: Dict[str, Dict[str, str]], start_date: str, end_date: str) -> None:
    """集約された番組リストを精査し、映画情報を取得して一つのCSVに保存する。

    取得したリストはIMDb評価順にソートして出力される。

    Args:
        all_program_items (List[Any]): 取得した全番組のTagオブジェクトリスト。
        movie_cache (Dict[str, Dict[str, str]]): 映画データベースの辞書。
        start_date (str): 取得期間の開始日。
        end_date (str): 取得期間の終了日。
    """
    final_results: List[List[str]] = []

    for item in all_program_items:
        s, e = item.get('s'), item.get('e')
        title_tag = item.find('p', class_='program_title')
        if not (s and e and title_tag):
            continue

        raw_title = title_tag.get_text(strip=True)
        if not is_cinema_in_title(raw_title) or not is_length_one_hour_over(s, e):
            continue

        # 映画.comから公開年、評価、ID、原題を取得
        cleaned_title = clean_title(raw_title)
        info = get_movie_info(cleaned_title, movie_cache)

        # IMDb Rating取得 (原題があるが、IMDbデータが未取得の場合のみ)
        if info.get("原題") and (not info.get("IMDb") or info.get("IMDb") == "-"):
            print(f"IMDb情報を取得中: {info['原題']}")
            info['IMDb'] = get_imdb_rating(info["原題"], info['公開年'])

        dt_str = datetime.strptime(s, '%Y%m%d%H%M').strftime('%Y/%m/%d %H:%M')
        final_results.append([
            dt_str, cleaned_title, info["公開年"], info["評価"],
            info["ID"], info["原題"], info["IMDb"]
        ])
        print(f"採用: [{dt_str}] {cleaned_title} ({info['公開年']}) 原題: {info['原題']} (IMDb: {info['IMDb']})")

    if final_results:
        out_cols = ['日時', '番組名', '公開年', '評価', 'ID', '原題', 'IMDb']
        df = pd.DataFrame(final_results, columns=out_cols)

        # ファイル名の生成 (1日の場合と複数日の場合で切り替え)
        clean_id = TARGET_CHANNEL_PREFIX.replace("-", "")
        if start_date == end_date:
            date_range_str = start_date
        else:
            date_range_str = f"{start_date}-{end_date}"

        output_path = os.path.join(
            os.path.dirname(DB_FILE),
            f"channel_{clean_id}_{date_range_str}.csv")

        df.to_csv(output_path, index=False, encoding='utf_8_sig')
        print(f"\n合計 {len(final_results)} 件の映画情報を保存しました: {output_path}")
        save_movie_db(movie_cache)
    else:
        print("\n指定された期間に一致する映画はありませんでした。")


def main() -> None:
    """メイン実行フロー。"""
    print(f"=== 番組表抽出ツール (対象ID: {TARGET_CHANNEL_PREFIX}) ===")

    # 1. 開始日の入力
    default_date = datetime.now().strftime('%Y%m%d')
    date_input = input(f"取得開始日(8桁)を入力 [デフォルト: {default_date}] > ").strip()
    start_date_str = date_input if date_input else default_date

    if not (start_date_str.isdigit() and len(start_date_str) == 8):
        print(f"エラー: '{start_date_str}' は無効な日付形式です。")
        return

    # 2. 取得日数の入力
    days_input = input("取得日数(最大31日間)を入力 [デフォルト: 1] > ").strip()
    try:
        num_days = int(days_input) if days_input else 1
        if not (1 <= num_days <= 31):
            raise ValueError
    except ValueError:
        print("エラー: 1から31の間の数字を入力してください。")
        return

    # 3. 日付ループでデータを取得・蓄積
    start_date_dt = datetime.strptime(start_date_str, '%Y%m%d')
    all_program_items = []

    for i in range(num_days):
        current_date_dt = start_date_dt + timedelta(days=i)
        current_date_str = current_date_dt.strftime('%Y%m%d')

        # 日別の番組データを取得してリストに追加
        daily_items = fetch_program_items(current_date_str, TARGET_CHANNEL_PREFIX)
        all_program_items.extend(daily_items)

    if not all_program_items:
        print("指定された期間のデータが取得できませんでした。")
        return

    # 4. 映画DB（キャッシュ）の読み込み
    movie_cache = load_movie_db()

    # 5. データの加工・照会・保存
    # 終了日の文字列を取得
    end_date_str = (start_date_dt + timedelta(days=num_days - 1)).strftime('%Y%m%d')
    process_and_save_results(all_program_items, movie_cache, start_date_str, end_date_str)


if __name__ == "__main__":
    main()
