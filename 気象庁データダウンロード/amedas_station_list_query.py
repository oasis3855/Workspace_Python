#!/usr/bin/python3

import json
import requests

# JSONファイルのURL
json_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"

# JSONデータを取得する
response = requests.get(json_url)
data = response.json()

# 観測地点名をプロンプト入力させる
input_name = input("観測地点名を入力してください: ")

# 観測地点番号を検索する
found = False
for station_id, station_info in data.items():
    if station_info.get("kjName") == input_name:  # 日本語の観測地点名を比較
        print(f"観測地点名: {input_name}, 観測地点番号: {station_id}")
        found = True
        break

if not found:
    print(f"観測地点名 '{input_name}' が見つかりませんでした。")
