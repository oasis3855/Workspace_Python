"""WOWOWシネマ番組表抽出・公開年照会ツール

このスクリプトは、指定された日付のBS番組表（bangumi.org）からWOWOWシネマの情報を取得し、
特定の条件でフィルタリングしてCSV出力します。

■ 主な機能:
1. 番組表のスクレイピングと「🈙マーク」「1時間超」によるフィルタリング。
2. 映画名をもとにした「映画.com」からの公開年照会。
3. ローカルCSV（movie_database.csv）によるデータのキャッシュ化。
4. 完全一致がない場合の対話型ユーザー選択インターフェース。

Version: 1.0.0
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
from typing import Dict, List, Optional

# データベースファイルのパス
DB_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movie_database.csv")


def load_movie_db() -> Dict[str, str]:
    """ローカルのCSVファイルから映画データベースを読み込む。

    Returns:
        Dict[str, str]: 映画名をキー、公開年を値とする辞書。ファイルがない場合は空の辞書を返す。
    """
    if os.path.exists(DB_FILE):
        df_db = pd.read_csv(DB_FILE, encoding='utf_8_sig')
        # 映画名をキー、公開年を値（文字列）として辞書化
        return dict(zip(df_db['映画名'], df_db['公開年'].astype(str)))
    return {}


def save_movie_db(movie_cache: Dict[str, str]) -> None:
    """現在のキャッシュをローカルのCSVファイルに保存する。

    Args:
        movie_cache (Dict[str, str]): 保存対象の映画データ辞書。
    """
    df_db = pd.DataFrame(list(movie_cache.items()), columns=['映画名', '公開年'])
    df_db.to_csv(DB_FILE, index=False, encoding='utf_8_sig')
    print(f"--- データベースを更新しました (合計: {len(df_db)}件) ---")


def is_cinema_in_title(title: str) -> bool:
    """番組名に映画を示す記号「🈙」が含まれているか判定する。

    Args:
        title (str): 判定対象の番組名。

    Returns:
        bool: 「🈙」が含まれていればTrue、そうでなければFalse。
    """
    return '🈙' in title


def is_length_one_hour_over(start_str: str, end_str: str) -> bool:
    """番組の放送時間が1時間を超えているか判定する。

    Args:
        start_str (str): 開始日時 (形式: YYYYMMDDHHMM)。
        end_str (str): 終了日時 (形式: YYYYMMDDHHMM)。

    Returns:
        bool: 1時間を超えていればTrue、そうでなければFalse。
    """
    try:
        fmt = '%Y%m%d%H%M'
        start_dt = datetime.strptime(start_str, fmt)
        end_dt = datetime.strptime(end_str, fmt)
        return (end_dt - start_dt) > timedelta(hours=1)
    except Exception:
        return False


def clean_title(title: str) -> str:
    """番組名から属性記号や括弧内の不要なテキストを除去する。

    Args:
        title (str): クリーニング前の番組名。

    Returns:
        str: クリーニング後の映画名。
    """
# 括弧内の情報を削除（[映], [字], （吹）など）
    title = re.sub(r'[\[［\(（].*?[\]］\)）]', '', title)

    # 特定のUnicode特殊記号を削除（🈠 を追加）
    symbols = [
        '🈙', '🅍', '🈑', '🈔', '🈓', '🈗', '🈘', '🈚',
        '🈛', '🈜', '🈝', '🈞', '🈟', '㊙', '🈠'
    ]
    for s in symbols:
        title = title.replace(s, '')

    return title.strip()


def get_release_year(cleaned_title: str, movie_cache: Dict[str, str]) -> str:
    """映画の公開年を取得する（DB優先、なければWeb検索、最終手段としてユーザー選択）。

    Args:
        cleaned_title (str): クリーニング済みの映画名。
        movie_cache (Dict[str, str]): 現在の映画データベースキャッシュ。

    Returns:
        str: 公開年（西暦4桁）。見つからない場合は「不明」。
    """
    if not cleaned_title:
        return ""

    # 1. データベース(キャッシュ)をチェック
    if cleaned_title in movie_cache:
        return movie_cache[cleaned_title]

    # 2. データベースになければWebアクセス
    search_url = f"https://eiga.com/search/{cleaned_title}/movie/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0"}

    try:
        time.sleep(1.0)  # サーバー負荷軽減のための待機
        res = requests.get(search_url, headers=headers)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        # 映画検索結果のリスト構造を抽出
        movie_items = soup.select('section#rslt-movie ul.list-tile > li')

        candidates: List[Dict[str, str]] = []
        if movie_items:
            for item in movie_items:
                title_tag = item.find('p', class_='title')
                time_tag = item.find('small', class_='time')

                if title_tag and time_tag:
                    found_title = title_tag.get_text(strip=True)
                    release_date = time_tag.get_text(strip=True)
                    year_match = re.search(r'\d{4}', release_date)
                    year = year_match.group() if year_match else "不明"

                    # 完全一致判定
                    if found_title == cleaned_title:
                        movie_cache[cleaned_title] = year
                        return year

                    candidates.append({"title": found_title, "year": year})

        # 3. 完全一致がなかった場合、ユーザーに対話形式で選択させる
        selected_year = "不明"
        if candidates:
            print(f"\n⚠️ 「{cleaned_title}」の完全一致がDB及び検索結果にありません。")
            for i, c in enumerate(candidates, 1):
                print(f"  {i}: {c['title']} ({c['year']})")
            print(f"  0: スキップ（不明として処理）")

            while True:
                choice = input(f"番号を選択してください (0-{len(candidates)}): ").strip()
                if choice == "0":
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    selected_year = candidates[int(choice) - 1]["year"]
                    break
                print("無効な入力です。再度入力してください。")

        # 結果をキャッシュに保存
        movie_cache[cleaned_title] = selected_year
        return selected_year

    except Exception as e:
        print(f"Error fetching data for {cleaned_title}: {e}")
        return "不明"


def main() -> None:
    """メイン実行処理。ユーザー入力を受け付け、番組表取得、解析、保存を行う。"""
    print("=== WOWOWシネマ 番組表抽出ツール ===")
    target_date: str = input("取得したい日付を8桁の数字で入力してください (例: 20260226)\n日付 > ").strip()

    # 入力バリデーション
    if not (target_date.isdigit() and len(target_date) == 8):
        print("❌ エラー: 日付は8桁の数字で入力してください。")
        return

    url: str = f"https://bangumi.org/epg/bs?broad_cast_date={target_date}"
    movie_cache: Dict[str, str] = load_movie_db()

    print(f"\n📡 番組表を取得中: {url}")
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.encoding = 'utf-8'
        if res.status_code != 200:
            print(f"❌ サイトにアクセスできませんでした (Status: {res.status_code})")
            return
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"❌ 通信エラーが発生しました: {e}")
        return

    # WOWOWシネマ(BS 193ch)のアイテムを抽出
    program_items = soup.find_all('li', attrs={'se-id': lambda x: x and x.startswith('193-')})

    if not program_items:
        print(f"⚠️ 指定された日付 ({target_date}) のWOWOWシネマ番組データが見つかりませんでした。")
        return

    final_results: List[List[str]] = []
    print(f"🔍 フィルタリング開始 (全{len(program_items)}番組)...")

    for item in program_items:
        s: Optional[str] = item.get('s')  # 開始時間
        e: Optional[str] = item.get('e')  # 終了時間
        title_tag = item.find('p', class_='program_title')

        if not (s and e and title_tag):
            continue

        raw_title: str = title_tag.get_text(strip=True)

        # 映画フラグおよび放送時間のチェック
        if not is_cinema_in_title(raw_title):
            continue
        if not is_length_one_hour_over(s, e):
            continue

        cleaned_title: str = clean_title(raw_title)

        # 公開年の特定
        release_year: str = get_release_year(cleaned_title, movie_cache)

        dt_obj = datetime.strptime(s, '%Y%m%d%H%M')
        formatted_dt: str = dt_obj.strftime('%Y/%m/%d %H:%M')

        final_results.append([formatted_dt, cleaned_title, release_year])
        print(f"採用: [{formatted_dt}] {cleaned_title} ({release_year})")

    # 結果の出力
    if final_results:
        df = pd.DataFrame(final_results, columns=['日時', '番組名', '公開年(映画の場合)'])
        output_path: str = os.path.join(os.path.dirname(DB_FILE), f"wowow_cinema_{target_date}.csv")
        df.to_csv(output_path, index=False, encoding='utf_8_sig')

        print(f"\n✅ 今日の映画リストを保存しました: {output_path}")
        save_movie_db(movie_cache)
    else:
        print("\n🤔 条件（🈙マーク、1時間超）に一致する映画は見つかりませんでした。")


if __name__ == "__main__":
    main()
