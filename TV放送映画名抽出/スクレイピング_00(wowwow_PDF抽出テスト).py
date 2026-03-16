import os

import pdfplumber
import pandas as pd
import re
import requests


def download_pdf(url, save_path):
    response = requests.get(url)
    with open(save_path, 'wb') as f:
        f.write(response.content)


def extract_wowow_schedule(pdf_path):
    data = []
    current_date = "2026/03/01"  # 初期値（PDF内の日付を検知して更新）

    # 時刻パターン (例: 04:30 や 01:15)
    time_pattern = re.compile(r'^(\d{2}:\d{2})\s+(.*)')
    # 日付パターン (例: 3/1(日) などを検知する場合)
    date_pattern = re.compile(r'(\d{1,2})/(\d{1,2})\(.\)')

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                # 日付の更新チェック
                date_match = date_pattern.search(line)
                if date_match:
                    month = date_match.group(1).zfill(2)
                    day = date_match.group(2).zfill(2)
                    current_date = f"2026/{month}/{day}"

                # 時刻と番組名の抽出
                time_match = time_pattern.match(line)
                if time_match:
                    time_str = time_match.group(1)
                    title = time_match.group(2).strip()

                    # 不要な記号や解説文を簡易的に掃除
                    # ※必要に応じてさらに細かくフィルタリング可能
                    data.append([current_date, time_str, title])

    return data


def extract_vertical_scan(pdf_path):
    all_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 1. ページの全体サイズを取得
            width = page.width
            height = page.height

            # 2. カラムの範囲を定義 (WOWOWのPDFに合わせて調整が必要)
            # 例: 1ページに8日分（月〜日の7日 + 左端の時間軸など）ある場合
            num_columns = 8
            col_width = width / num_columns

            # 上下のヘッダー・フッターを除外するためのマージン（ピクセル単位）
            top_margin = 50
            bottom_margin = 50

            for i in range(num_columns):
                # 3. 縦方向の切り出し範囲 (x0, top, x1, bottom) を計算
                x0 = i * col_width
                x1 = (i + 1) * col_width

                # 特定のカラムだけを切り抜く
                column_area = (x0, top_margin, x1, height - bottom_margin)
                cropped_page = page.crop(column_area)

                # 4. 切り抜いた範囲内だけでテキストを抽出（これが縦方向スキャンになる）
                column_text = cropped_page.extract_text()

                if column_text:
                    # ここで日付判定や時刻・番組名のパースを行う
                    # parsed_rows = parse_lines(column_text)
                    # all_data.extend(parsed_rows)
                    pass

    return all_data


def extract_by_auto_columns(pdf_path):
    all_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 1. ページ内のすべての「縦線」を取得
            # v['width'] < 1 は、細長い線（縦線）をフィルタリングする条件
            vertical_lines = [v for v in page.edges if v['width'] < 1]

            # 2. 縦線の X 座標を抽出してソート（重複は丸めて排除）
            x_coords = sorted(list(set([round(v['x0'], 1) for v in vertical_lines])))

            # 3. 隣り合う縦線の間を「カラム」として切り抜く
            for i in range(len(x_coords) - 1):
                x0 = x_coords[i]
                x1 = x_coords[i + 1]

                # あまりに狭い隙間（マージンなど）はスキップ
                if x1 - x0 < 20:
                    continue

                # カラム範囲でクロップ (x0, top, x1, bottom)
                # ページ上部のヘッダーなどを避けるため top を少し下げる
                crop_area = (x0, 40, x1, page.height - 40)
                cropped_page = page.crop(crop_area)

                # 4. 切り出したカラム内を「縦に」スキャンしてテキスト抽出
                column_text = cropped_page.extract_text()

                if column_text:
                    # ここで各行をパースしてリストに追加
                    print(f"--- Column {i} Start ---")
                    print(column_text)
                    print(f"--- Column {i} End ---")

    return all_data


# スクリプトファイルが存在するディレクトリの絶対パスを取得
base_dir = os.path.dirname(os.path.abspath(__file__))

# 実行
url = "https://www.wowow.co.jp/dpm/pdf/wowow_monthly202603_cinema.pdf"
pdf_file = os.path.join(base_dir, "wowow_202603.pdf")
csv_file = os.path.join(base_dir, "wowow_schedule_202603.csv")

print("Downloading PDF...")
download_pdf(url, pdf_file)

print("Extracting data...")
# schedule_data = extract_wowow_schedule(pdf_file)
schedule_data = extract_by_auto_columns(pdf_file)

# CSVへ出力
df = pd.DataFrame(schedule_data, columns=['日付', '時刻', '番組名（映画名）'])
df.to_csv(csv_file, index=False, encoding='utf_8_sig')

print(f"完了！ {len(df)} 件の番組を抽出しました。")
