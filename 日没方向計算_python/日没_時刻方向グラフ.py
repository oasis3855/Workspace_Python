#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
================================================================================
日没時刻と方位角のグラフ表示スクリプト
================================================================================

概要:
    指定された緯度・経度に基づき、pyephemライブラリを使用して
    一年間の日没時刻（JST）と日没方位角（度）を計算し、Matplotlibでグラフ表示する。

実行環境:
    Python 3.x
    必要なライブラリ: pyephem, numpy, matplotlib
    CUI版として動作し、実行時にグラフウィンドウを開く。

最終更新日: 2025-12-06
作成者: Google Gemini3

================================================================================
"""

import math
import ephem
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
import sys
from typing import List, Tuple

# =================================================================
# グローバル変数として計算対象の緯度・経度を指定 (ここを編集)
# 例: 大阪 (北緯 34.67 度, 東経 135.5 度)
TARGET_LATITUDE_DEG = 34.67
TARGET_LONGITUDE_DEG = 135.5
TARGET_ELEVATION = 3000.0  # 標高 [m]
# =================================================================

# --- 天文計算関数 ---


def calculate_sunset_data(latitude_deg: float,
                          longitude_deg: float) -> Tuple[List[str],
                                                         List[float],
                                                         List[float]]:
    """
    指定された緯度と経度に基づき、一年間の日没時刻と方位角を計算する。

    Args:
        latitude_deg (float): 観測地点の緯度（度）。北緯は正（+）、南緯は負（-）。
        longitude_deg (float): 観測地点の経度（度）。

    Returns:
        Tuple[List[str], List[float], List[float]]:
            計算結果を格納した3要素のタプル。要素は以下の通り。
            1. 日付のリスト (List[str]): "MM/DD" 形式の日付文字列リスト。
            2. 日没時刻のリスト (List[float]): JSTでの日没時刻（時間＋小数）のリスト。
            3. 日没方位角のリスト (List[float]): 北を0/360度とする方位角（度）のリスト。
            ※ 白夜・極夜で日没がない日は NaN (np.nan) が格納される。
    """
    # 観測地点を設定
    obs = ephem.Observer()
    # ephemは文字列形式の緯度・経度を要求するため変換
    obs.lat = str(latitude_deg)
    obs.lon = str(longitude_deg)

    # 空気屈折効果をEphemに計算させる(標高が0m以上の場合必要。真空の場合の伏角を与え、気圧・気温を設定すると空気屈折が自動計算される)
    obs.elevation = TARGET_ELEVATION        # 標高 [m]
    R = 6371000.0                   # 地球半径 [m]
    dip_noair = math.sqrt(2 * TARGET_ELEVATION / R) * 180.0 / math.pi      # 真空の場合(厳密)
    obs.horizon = str(-dip_noair)   # Ephemの標準値は 伏角 0 [度] @ 標高0m
    pressure = 1013.25 * (1 - 2.25577e-5 * TARGET_ELEVATION) ** 5.2559      # 標高による気圧補正
    obs.pressure = pressure         # Ephemの標準値は 1010.0 [hPa] @ 標高0m
    temperature = 15.0 - 0.6 * TARGET_ELEVATION / 100
    obs.temperature = temperature   # Ephemの標準値は 15.0 [℃] @ 標高0m

    dates = []
    sunset_times_hours = []
    sunset_azimuths = []

    # JSTはUTC+9時間
    JST_OFFSET_HOURS = 9.0

    # 1年間の日付を生成（来年の1月1日から366日分）
    start_date = datetime(datetime.now().year + 1, 1, 1)

    for i in range(366):
        current_date = start_date + timedelta(days=i)
        obs.date = current_date

        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        try:
            # 日没時刻をUTCで計算
            sunset_time_ephem = obs.next_setting(sun)

            # datetimeオブジェクトに変換（UTCとして扱う）
            sunset_time_utc = sunset_time_ephem.datetime()

            # 日付のリストに追加 (月/日形式)
            dates.append(current_date.strftime('%m/%d'))

            # 日没時の太陽の方位角を計算
            obs.date = sunset_time_ephem
            sun.compute(obs)
            azimuth_rad = sun.az
            azimuth_deg = np.degrees(azimuth_rad)
            sunset_azimuths.append(azimuth_deg)

            # 時刻を「時間（小数）」で表現
            sunset_hour_utc = (
                sunset_time_utc.hour +
                sunset_time_utc.minute / 60.0 +
                sunset_time_utc.second / 3600.0
            )

            # --- JST への変換 ---
            # JST時刻 = UTC時刻 + 9時間
            jst_sunset_hour = sunset_hour_utc + JST_OFFSET_HOURS

            # 24時を超えた場合は翌日の時刻として扱う (例: 25.0 -> 1.0)
            if jst_sunset_hour >= 24.0:
                jst_sunset_hour -= 24.0

            sunset_times_hours.append(jst_sunset_hour)

        except (ephem.AlwaysUpError, ephem.NeverUpError):
            # 白夜または極夜
            dates.append(current_date.strftime('%m/%d'))
            sunset_times_hours.append(np.nan)
            sunset_azimuths.append(np.nan)

    return dates, sunset_times_hours, sunset_azimuths

# --- グラフ描画関数 ---


def plot_data(latitude: float, dates: List[str], times: List[float], azimuths: List[float]) -> None:
    """
    計算結果をMatplotlibでプロットし、表示する。

    Args:
        latitude (float): グラフ表示対象の緯度（度）。
        dates (List[str]): グラフのX軸に使用する日付（月/日形式の文字列）のリスト。
        times (List[float]): 各日付の日没時刻（時間＋小数：例 18.5）のリスト。
        azimuths (List[float]): 各日付の日没方位角（度）のリスト。

    Returns:
        None: グラフを描画し、表示するのみで、値を返さない。
    """
    fig = plt.figure(figsize=(12, 8))

    # 1つ目のサブプロット: 日没時刻
    ax1 = fig.add_subplot(211)
    ax1.plot(times, color='b')
    ax1.set_title(
        f"緯度 {latitude}°、経度 {TARGET_LONGITUDE_DEG}° 、標高 {TARGET_ELEVATION}m における日没時刻と方位角（一年間）",
        fontsize=16)
    # ラベルを JST に変更
    ax1.set_ylabel("日没時刻 (時, JST)")
    ax1.grid(True)

    # Y軸の時刻フォーマットを調整 (例: 18.5 -> 18:30)
    from matplotlib.ticker import FuncFormatter

    def time_formatter(y, pos):
        h = int(y)
        m = int((y - h) * 60)
        return f"{h:02d}:{m:02d}"
    ax1.yaxis.set_major_formatter(FuncFormatter(time_formatter))

    # X軸のラベル設定（日付）
    num_ticks = 12
    step = len(dates) // num_ticks
    tick_indices = np.arange(0, len(dates), step)
    tick_labels = [dates[i] for i in tick_indices]

    ax1.set_xticks(tick_indices)
    ax1.set_xticklabels(tick_labels, rotation=45, ha='right')
    ax1.tick_params(labelbottom=False)

    # 2つ目のサブプロット: 日没方位角
    ax2 = fig.add_subplot(212, sharex=ax1)
    ax2.plot(azimuths, color='r')
    ax2.set_ylabel("日没方位角 (度)")
    ax2.set_xlabel("月/日")
    ax2.grid(True)

    ax2.set_yticks(np.arange(240, 310, 10))
    ax2.set_ylim(230, 310)

    ax2.set_xticks(tick_indices)
    ax2.set_xticklabels(tick_labels, rotation=45, ha='right')

    # レイアウト調整と描画
    fig.tight_layout()
    plt.show()


# --- メイン処理 ---
if __name__ == "__main__":

    latitude = TARGET_LATITUDE_DEG
    longitude = TARGET_LONGITUDE_DEG

    # 入力値の確認
    if not (-90 <= latitude <= 90):
        print(f"エラー: 緯度 {latitude}° は -90 から 90 の間で入力してください。", file=sys.stderr)
        sys.exit(1)
    if not (122.95 <= longitude <= 153.98):
        print("--- 警告 ---", file=sys.stderr)
        print(f"経度 {longitude}° は日本の領土の標準的な範囲外です。", file=sys.stderr)
        # 警告に留め、処理は続行する

    print(f"緯度 {latitude}°、経度 {longitude}° の日没データを計算中...")
    dates, times, azimuths = calculate_sunset_data(latitude, longitude)

    if not dates:
        print("エラー: 計算に失敗しました。", file=sys.stderr)
        sys.exit(1)

    print("計算完了。グラフを表示します。（ウィンドウがポップアップします）")
    plot_data(latitude, dates, times, azimuths)
