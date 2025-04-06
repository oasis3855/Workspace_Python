#!/usr/bin/python3

import requests
import json
import csv

# JSONファイルのURL
json_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"

# ローカルにJSONデータを取得する関数（インターネット接続が必要）
response = requests.get(json_url)
data = response.json()

# CSVファイル名
csv_file = "amedas_locations.csv"

# CSVファイルを作成
with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    # ヘッダーを記入
    writer.writerow(["観測地点番号", "観測地点名"])

    # JSONデータを解析して観測地点番号と観測地点名を抽出
    for station_id, station_info in data.items():
        station_name = station_info.get("kjName", "")  # 観測地点名を取得
        writer.writerow([station_id, station_name])

print(f"CSVファイル '{csv_file}' が作成されました。")
