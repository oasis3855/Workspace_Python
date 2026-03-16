"""WOWOWシネマ番組表抽出・公開年＆評価照会ツール

このスクリプトは、指定された日付のBS番組表（bangumi.org）からWOWOWシネマの情報を取得し、
特定の条件でフィルタリングして、公開年と評価値（eiga.comより）を添えてCSV出力します。

■ 主な機能:
1. 番組表のスクレイピングと「🈙マーク」「1時間超」によるフィルタリング。
2. 映画名をもとにした「映画.com」からの公開年および評価（rating-star）の照会。
3. ローカルCSV（movie_database.csv）によるデータのキャッシュ化。
4. 完全一致がない場合の対話型ユーザー選択インターフェース。

Version: 1.1.0
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
from typing import Dict, List, Optional, Tuple

# データベースファイルのパス
DB_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie_database.csv")


def load_movie_db() -> Dict[str, Tuple[str, str]]:
    """ローカルのCSVファイルから映画データベースを読み込む。

    Returns:
        Dict[str, Tuple[str, str]]: 映画名をキー、(公開年, 評価)のタプルを値とする辞書。
    """
    if os.path.exists(DB_FILE):
        try:
            df_db = pd.read_csv(DB_FILE, encoding='utf_8_sig')
            # 必要な列が存在するか確認
            if all(col in df_db.columns for col in ['映画名', '公開年', '評価']):
                return {
                    row['映画名']: (str(row['公開年']), str(row['評価']))
                    for _, row in df_db.iterrows()
                }
        except Exception as e:
            print(f"⚠️ DB読み込み警告: {e}")
    return {}


def save_movie_db(movie_cache: Dict[str, Tuple[str, str]]) -> None:
    """現在のキャッシュをローカルのCSVファイルに保存する。

    Args:
        movie_cache (Dict[str, Tuple[str, str]]): 保存対象の映画データ辞書。
    """
    data_list = [
        {'映画名': name, '公開年': info[0], '評価': info[1]}
        for name, info in movie_cache.items()
    ]
    df_db = pd.DataFrame(data_list)
    df_db.to_csv(DB_FILE, index=False, encoding='utf_8_sig')
    print(f"--- データベースを更新しました (合計: {len(df_db)}件) ---")


def is_cinema_in_title(title: str) -> bool:
    """番組名に映画を示す記号「🈙」が含まれているか判定する。"""
    return '🈙' in title


def is_length_one_hour_over(start_str: str, end_str: str) -> bool:
    """番組の放送時間が1時間を超えているか判定する。"""
    try:
        fmt = '%Y%m%d%H%M'
        start_dt = datetime.strptime(start_str, fmt)
        end_dt = datetime.strptime(end_str, fmt)
        return (end_dt - start_dt) > timedelta(hours=1)
    except Exception:
        return False


def clean_title(title: str) -> str:
    """番組名から属性記号や括弧内の不要なテキストを除去する。"""
    title = re.sub(r'[\[［\(（].*?[\]］\)）]', '', title)
    # 🈠 を含む特殊記号を削除
    symbols = [
        '🈙', '🅍', '🈑', '🈔', '🈓', '🈗', '🈘', '🈚',
        '🈛', '🈜', '🈝', '🈞', '🈟', '㊙', '🈠'
    ]
    for s in symbols:
        title = title.replace(s, '')
    return title.strip()


def get_movie_info(cleaned_title: str, movie_cache: Dict[str, Tuple[str, str]]) -> Tuple[str, str]:
    """映画の公開年と評価を取得する。

    Args:
        cleaned_title (str): クリーニング済みの映画名。
        movie_cache (Dict): 現在のキャッシュ。

    Returns:
        Tuple[str, str]: (公開年, 評価)。見つからない場合は ("不明", "-")。
    """
    if not cleaned_title:
        return ("", "")

    # 1. キャッシュチェック
    if cleaned_title in movie_cache:
        return movie_cache[cleaned_title]

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

                if title_tag and time_tag:
                    found_title = title_tag.get_text(strip=True)
                    release_date = time_tag.get_text(strip=True)
                    year_match = re.search(r'\d{4}', release_date)
                    year = year_match.group() if year_match else "不明"

                    # 評価値の取得 (テキストが存在しない場合は "-" とする)
                    rating = rating_tag.get_text(strip=True) if rating_tag else "-"
                    if not rating:
                        rating = "-"

                    # 完全一致判定
                    if found_title == cleaned_title:
                        movie_cache[cleaned_title] = (year, rating)
                        return year, rating

                    candidates.append({"title": found_title, "year": year, "rating": rating})

        # 3. ユーザー選択
        selected_info = ("不明", "-")
        if candidates:
            print(f"\n⚠️ 「{cleaned_title}」の完全一致がありません。候補から選んでください:")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}: {c['title']} ({c['year']}) [評価: {c['rating']}]")
            print(f"  0: スキップ")

            while True:
                choice = input(f"選択 (0-{len(candidates)}): ").strip()
                if choice == "0":
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    target = candidates[int(choice) - 1]
                    selected_info = (target["year"], target["rating"])
                    break
                print("無効な入力です。")

        movie_cache[cleaned_title] = selected_info
        return selected_info

    except Exception as e:
        print(f"Error fetching data: {e}")
        return ("不明", "-")


def main() -> None:
    """メイン実行処理。"""
    print("=== WOWOWシネマ 番組表抽出ツール v1.1.1 ===")
    
    # 1. デフォルト値（今日の日付）の生成
    default_date: str = datetime.now().strftime('%Y%m%d')
    
    # 2. ユーザー入力（ENTERのみの場合はデフォルト値を採用）
    prompt = f"取得日(8桁)を入力してください [デフォルト: {default_date}] > "
    user_input: str = input(prompt).strip()
    
    target_date: str = user_input if user_input else default_date

    # 入力バリデーション
    if not (target_date.isdigit() and len(target_date) == 8):
        print(f"❌ エラー: '{target_date}' は無効な形式です。8桁の数字で入力してください。")
        return
    url: str = f"https://bangumi.org/epg/bs?broad_cast_date={target_date}"
    movie_cache = load_movie_db()

    print(f"\n📡 取得中: {url}")
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"❌ 通信エラー: {e}")
        return

    program_items = soup.find_all('li', attrs={'se-id': lambda x: x and x.startswith('193-')})

    final_results: List[List[str]] = []
    print(f"🔍 解析中...")

    for item in program_items:
        s, e = item.get('s'), item.get('e')
        title_tag = item.find('p', class_='program_title')
        if not (s and e and title_tag):
            continue

        raw_title = title_tag.get_text(strip=True)
        if not is_cinema_in_title(raw_title) or not is_length_one_hour_over(s, e):
            continue

        cleaned_title = clean_title(raw_title)

        # 公開年と評価を取得
        release_year, rating = get_movie_info(cleaned_title, movie_cache)

        dt_str = datetime.strptime(s, '%Y%m%d%H%M').strftime('%Y/%m/%d %H:%M')
        final_results.append([dt_str, cleaned_title, release_year, rating])
        print(f"採用: [{dt_str}] {cleaned_title} ({release_year}) [★ {rating}]")

    if final_results:
        # 今日のリスト保存
        df = pd.DataFrame(final_results, columns=['日時', '番組名', '公開年(映画の場合)', '評価'])
        output_path = os.path.join(os.path.dirname(DB_FILE), f"wowow_cinema_{target_date}.csv")
        df.to_csv(output_path, index=False, encoding='utf_8_sig')

        print(f"\n✅ リストを保存しました: {output_path}")
        save_movie_db(movie_cache)
    else:
        print("\n🤔 該当する映画はありませんでした。")


if __name__ == "__main__":
    main()
