#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
================================================================================
日没時刻（秒単位）と方位角のリポート出力スクリプト
================================================================================

概要:
    指定された緯度・経度、および開始日・期間に基づき、
    一年間（あるいは指定期間）の日没時刻（JST, 秒まで）と方位角を計算し、
    テキストリスト形式で出力およびグラフ表示する。

実行環境:
    Python 3.x
    必要なライブラリ: pyephem, numpy, matplotlib
    作成者: Google Gemini3

================================================================================
"""

import ephem
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
import sys
from typing import List, Tuple

# =================================================================
# グローバル設定変数 (ここを編集してください)
# =================================================================
# 1. 観測地点の設定 (例: 大阪)
TARGET_LATITUDE_DEG = 34.67
TARGET_LONGITUDE_DEG = 135.5

# 2. 計算開始日の設定
START_YEAR = 2025
START_MONTH = 12
START_DAY = 1

# 3. 計算する日数
NUM_DAYS = 31
# =================================================================


def calculate_sunset_data(
    lat: float, lon: float, start_y: int, start_m: int, start_d: int, days_count: int
) -> List[Tuple[str, str, float]]:
    """
    指定された条件に基づき、日没データを計算してリストで返す。

    Returns:
        List[Tuple[str, str, float]]: (年月日文字列, 時刻文字列, 方位角) のリスト
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)

    results = []
    jst_offset = timedelta(hours=9)
    start_date = datetime(start_y, start_m, start_d)

    for i in range(days_count):
        current_date = start_date + timedelta(days=i)
        # obs.date は UTC で設定（JST 00:00 は UTC 前日15:00だが、
        # 日没計算には十分なマージンがあるため当日00:00 UTCで設定）
        obs.date = current_date

        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        try:
            # 日没時刻をUTCで計算
            sunset_time_ephem = obs.next_setting(sun)

            # 方位角の計算
            obs.date = sunset_time_ephem
            sun.compute(obs)
            azimuth_deg = np.degrees(sun.az)

            # JSTへ変換
            sunset_utc = sunset_time_ephem.datetime()
            sunset_jst = sunset_utc + jst_offset

            # フォーマット整形
            date_str = sunset_jst.strftime('%Y/%m/%d')
            time_str = sunset_jst.strftime('%H:%M:%S')

            results.append((date_str, time_str, azimuth_deg))

        except (ephem.AlwaysUpError, ephem.NeverUpError):
            # 白夜・極夜の場合
            results.append((current_date.strftime('%Y/%m/%d'), "--:--:--", np.nan))

    return results


def plot_data(latitude: float, longitude: float, data: List[Tuple[str, str, float]]) -> None:
    """
    リスト形式のデータを受け取り、Matplotlibでプロットする。
    """
    dates = [d[0][5:] for d in data]  # MM/DD形式に短縮
    # 時刻を数値に変換 (HH:MM:SS -> hours)
    times = []
    for d in data:
        if d[1] == "--:--:--":
            times.append(np.nan)
        else:
            h, m, s = map(int, d[1].split(':'))
            times.append(h + m / 60.0 + s / 3600.0)

    azimuths = [d[2] for d in data]

    fig = plt.figure(figsize=(12, 8))

    # 時刻グラフ
    ax1 = fig.add_subplot(211)
    ax1.plot(times, color='b', marker='.', markersize=2, linestyle='None')
    ax1.set_title(f"日没データ: 緯度 {latitude}°, 経度 {longitude}°", fontsize=14)
    ax1.set_ylabel("日没時刻 (JST)")
    ax1.grid(True)

    from matplotlib.ticker import FuncFormatter
    ax1.yaxis.set_major_formatter(
        FuncFormatter(
            lambda y,
            p: f"{int(y):02d}:{int((y-int(y))*60):02d}"))

    # 方位角グラフ
    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(azimuths, color='r', marker='.', markersize=2, linestyle='None')
    ax2.set_ylabel("日没方位角 (度)")
    ax2.set_xlabel("月/日")
    ax2.grid(True)

    # X軸の間引き設定
    num_ticks = 12
    step = max(1, len(dates) // num_ticks)
    ax2.set_xticks(np.arange(0, len(dates), step))
    ax2.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)

    fig.tight_layout()
    plt.show()


# --- メイン処理 ---
if __name__ == "__main__":

    # エラーチェック (緯度・経度)
    if not (-90 <= TARGET_LATITUDE_DEG <= 90):
        print(f"エラー: 緯度が不正です({TARGET_LATITUDE_DEG})", file=sys.stderr)
        sys.exit(1)

    print(f"--- 日没データリスト (開始: {START_YEAR}/{START_MONTH}/{START_DAY}, 期間: {NUM_DAYS}日間) ---")
    print("年月日,日没時刻,方角(度)")

    # 計算実行
    sunset_results = calculate_sunset_data(
        TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG,
        START_YEAR, START_MONTH, START_DAY, NUM_DAYS
    )

    # リスト出力
    for date_str, time_str, az in sunset_results:
        az_str = f"{az:.1f}" if not np.isnan(az) else "N/A"
        print(f"{date_str},{time_str},{az_str}")

    print("----------------------------------------------------------------")

    # グラフ表示の確認
    ans = input("グラフを表示しますか？ (y/n): ")
    if ans.lower() == 'y':
        plot_data(TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG, sunset_results)
