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
    current_date = "2026/03/01" # 初期値（PDF内の日付を検知して更新）
    
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

# 実行
url = "https://www.wowow.co.jp/dpm/pdf/wowow_monthly202603_cinema.pdf"
pdf_file = "wowow_202603.pdf"

print("Downloading PDF...")
download_pdf(url, pdf_file)

print("Extracting data...")
schedule_data = extract_wowow_schedule(pdf_file)

# CSVへ出力
df = pd.DataFrame(schedule_data, columns=['日付', '時刻', '番組名（映画名）'])
df.to_csv('wowow_schedule_202603.csv', index=False, encoding='utf_8_sig')

print(f"完了！ {len(df)} 件の番組を抽出しました。")