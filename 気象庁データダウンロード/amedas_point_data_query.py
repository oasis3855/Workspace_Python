#!/usr/bin/python3

import json
import requests
from datetime import datetime

# JSONファイルのURL（観測地点一覧）
station_list_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"

# 観測地点一覧を取得
response = requests.get(station_list_url)
station_data = response.json()

# ユーザに観測地点名を入力させる
input_name = input("観測地点名を入力してください: ")

# 観測地点番号を検索
station_id = None
for station_key, station_info in station_data.items():
    if station_info.get("kjName") == input_name:  # 日本語の観測地点名を比較
        station_id = station_key
        break

if station_id is None:
    print(f"観測地点名 '{input_name}' が見つかりませんでした。")
else:
    # 今日の日付を取得
    now = datetime.now()
    yyyymmdd = now.strftime("%Y%m%d")
    # 最新の時刻（3時間区分）を計算
    h3 = (now.hour // 3) * 3

    # 気象観測データのURLを構築
    weather_data_url = f"https://www.jma.go.jp/bosai/amedas/data/point/{station_id}/{yyyymmdd}_{h3}.json"

    # 気象観測データを取得
    weather_response = requests.get(weather_data_url)
    if weather_response.status_code == 200:
        weather_data = weather_response.json()
        # 最新のデータを取得
        latest_time = max(weather_data.keys())  # 最も新しい時刻を取得
        latest_temp = weather_data[latest_time].get("temp", [None])[0]  # 気温を取得

        if latest_temp is not None:
            print(f"観測地点名: {input_name}, 観測地点番号: {station_id}")
            print(f"最新の気温: {latest_temp}℃")
        else:
            print(f"気温データが利用できません。")
    else:
        print(f"気象観測データの取得に失敗しました (URL: {weather_data_url})。")
