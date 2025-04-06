#!/usr/bin/python3

import json
import requests
import tkinter as tk
from tkinter import ttk
from datetime import datetime

# JSONファイルのURL（観測地点一覧）
station_list_url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"

# 観測地点一覧データを取得
response = requests.get(station_list_url)
station_data = response.json()

# 観測地点名のリストを作成
station_names = [info.get("kjName", "") for info in station_data.values()]

# 最新気象データを取得して表示する関数


def fetch_weather_data():
    selected_station_name = combo_box.get()
    station_id = None

    # 選択された観測地点名に対応する観測地点番号を取得
    for station_key, station_info in station_data.items():
        if station_info.get("kjName") == selected_station_name:
            station_id = station_key
            break

    if station_id is None:
        result_label.config(text="選択された観測地点名に対応する番号が見つかりません。")
        return

    # 今日の日付を取得
    now = datetime.now()
    yyyymmdd = now.strftime("%Y%m%d")
    h3 = (now.hour // 3) * 3  # 最新の3時間区分

    # 気象観測データのURLを構築
    weather_data_url = f"https://www.jma.go.jp/bosai/amedas/data/point/{station_id}/{yyyymmdd}_{h3}.json"

    # 気象観測データを取得
    weather_response = requests.get(weather_data_url)
    if weather_response.status_code == 200:
        weather_data = weather_response.json()
        # 最新のデータを取得
        latest_time = max(weather_data.keys())  # 最も新しい時刻
        latest_temp = weather_data[latest_time].get("temp", [None])[0]  # 気温を取得

        if latest_temp is not None:
            result_label.config(
                text=f"観測地点名: {selected_station_name}\n観測地点番号: {station_id}\n最新の気温: {latest_temp}℃")
        else:
            result_label.config(text="気温データが利用できません。")
    else:
        result_label.config(text="気象観測データの取得に失敗しました。")


# Tkinter ウィンドウを設定
window = tk.Tk()
window.title("観測地点選択と気象データ表示")
window.geometry("400x250")

# 説明ラベル
label = tk.Label(window, text="観測地点名を選択してください：")
label.pack(pady=10)

# コンボボックス（プルダウンリスト）
combo_box = ttk.Combobox(window, values=station_names, state="readonly")
combo_box.pack(pady=10)

# ボタン
button = tk.Button(window, text="気象データを取得", command=fetch_weather_data)
button.pack(pady=10)

# 結果ラベル
result_label = tk.Label(window, text="")
result_label.pack(pady=10)

# ウィンドウを実行
window.mainloop()
