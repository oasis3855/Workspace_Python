#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定された緯度・経度に基づき太陽の軌道を計算・可視化するスクリプト。

このモジュールは、pyephemライブラリを使用して特定地点の日の出、日没、
および標高別の伏角変化を計算し、その結果を大気屈折の有無を含めて
Matplotlibを使用して2段のグラフで可視化します。

Attributes:
    TARGET_LATITUDE_DEG (float): 観測地点のデフォルト緯度（度）。
    TARGET_LONGITUDE_DEG (float): 観測地点のデフォルト経度（度）。

Requires:
    - Python 3.x
    - ephem: 天文計算用ライブラリ (pip install pyephem)
    - numpy: 数値計算用ライブラリ (pip install numpy)
    - matplotlib: グラフ描画用ライブラリ (pip install matplotlib)

Author:
    Google Gemini3

Version:
    1.0.0 (2025/12/29)
"""

import ephem  # type: ignore
import math
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from matplotlib.ticker import FuncFormatter
from typing import List, Dict, Tuple

# =================================================================
# グローバル設定変数 (デフォルト値を変えるには、ここを編集してください)
# =================================================================
TARGET_LATITUDE_DEG = 34.67
TARGET_LONGITUDE_DEG = 135.50
DIP_MODE_EPHEM = True       # 伏角の空気屈折効果をEphemの内部計算モードにするかどうか
# =================================================================


def calculate_sun_times(
    lat: float,
    lon: float,
    elevation: float,
    start_date: datetime,
    days_count: int,
    with_refraction: bool
) -> Tuple[List[float], List[float]]:
    """指定された条件下での日の出・日の入り時刻のリストを計算する。

    標高による伏角を計算し、大気屈折の有無に応じた補正係数を適用する。

    Args:
        lat (float): 観測地点の緯度（度）。
        lon (float): 観測地点の経度（度）。
        elevation (float): 観測地点の標高（メートル）。
        start_date (datetime): 計算開始年月日。
        days_count (int): 計算を行う日数。
        with_refraction (bool): 大気屈折を考慮する場合はTrue、幾何学的な場合はFalse。

    Returns:
        Tuple[List[float], List[float]]: 以下のリストを含むタプル。
            - rise_times (List[float]): 各日の日の出時刻（時間単位のfloat、JST）。
            - set_times (List[float]): 各日の日の入り時刻（時間単位のfloat、JST）。
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.elevation = elevation

    # 伏角の計算
    R = 6371000.0           # 地球半径 [m]
    # dip_noair = 0.03211 * math.sqrt(elevation)                      # 真空の場合(近似)
    dip_noair = math.sqrt(2 * elevation / R) * 180.0 / math.pi      # 真空の場合(厳密)
    dip_ref = 0.04785 * math.sqrt(elevation)                        # 空気中の場合(実効値の近似)

    obs.horizon = str(-dip_noair)

    if (with_refraction):
        # 大気中の場合（空気屈折あり）
        if (DIP_MODE_EPHEM):    # 空気屈折計算はEphemで行う
            # 伏角を真空中の値(dip_noair)で設定した場合、気圧・気温を設定するとEphemが自動的に空気補正を行ってくれる
            pressure_0m = 1013.25   # 標高 0mの気圧 [hPa]
            pressure = pressure_0m * (1 - 2.25577e-5 * elevation) ** 5.2559
            temperature_0m = 15.0   # 標高 0mの気温 [℃]
            temperature = temperature_0m - 0.6 * elevation / 100
            obs.pressure = pressure         # Ephemの標準値は 1010.0 [hPa]
            obs.temperature = temperature   # Ephemの標準値は 15.0 [℃]
        else:   # 空気屈折計算はEphemではなく、屈折効果込みのdip_refを用いる
            obs.horizon = str(-dip_ref)             # stringで渡す場合の単位は degree
            # 伏角を空気中の値(dip_ref)で設定した場合、Ephemの自動空気補正を無効化するために 気圧を 0 に設定する
            obs.pressure = 0.0              # Ephemの標準値は 1010.0 [hPa]
    else:
        # Ephemの自動空気補正を無効化するために 気圧を 0 に設定する
        obs.pressure = 0.0              # Ephemの標準値は 1010.0 [hPa]

    rise_times = []
    set_times = []
    jst_offset = timedelta(hours=9)

    for i in range(days_count):
        current_date = start_date + timedelta(days=i)
        obs.date = current_date - jst_offset
        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        try:
            # 日の出
            rise_time_ephem = obs.next_rising(sun)
            rise_jst = rise_time_ephem.datetime() + jst_offset
            rise_times.append(rise_jst.hour + rise_jst.minute / 60.0 + rise_jst.second / 3600.0)

            # 日没
            set_time_ephem = obs.next_setting(sun)
            set_jst = set_time_ephem.datetime() + jst_offset
            set_times.append(set_jst.hour + set_jst.minute / 60.0 + set_jst.second / 3600.0)
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rise_times.append(np.nan)
            set_times.append(np.nan)

    return rise_times, set_times


def plot_sun_data(
    lat: float,
    lon: float,
    dates_raw: List[datetime],
    elevations: List[int],
    results: Dict
) -> None:
    """計算結果を基に、日出・日入の2段構成グラフを描画する。

    Args:
        lat (float): 観測地点の緯度。
        lon (float): 観測地点の経度。
        dates_raw (List[datetime]): 計算対象日のdatetimeリスト。
        elevations (List[int]): プロット対象の標高リスト。
        results (Dict): 標高をキーとし、'with_ref'と'without_ref'のタプルを持つ計算結果辞書。
    """
    dates_str = [d.strftime('%m/%d') for d in dates_raw]

    fig, (ax_rise, ax_set) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"標高別 日出・日入時刻の変化 (緯度: {lat}°, 経度: {lon}°)", fontsize=16)

    colors = {0: 'blue', 1000: 'green', 2000: 'orange', 3000: 'red'}
    rise_all_curves = []
    set_all_curves = []

    # 時刻用フォーマッタ (HH:MM)
    time_fmt = FuncFormatter(lambda y, p: f"{int(y):02d}:{int(round((y - int(y)) * 60)) % 60:02d}")

    for elev in elevations:
        r_w, s_w = results[elev]['with_ref']
        r_wo, s_wo = results[elev]['without_ref']

        # 上段：日の出
        ax_rise.plot(dates_str, r_w, label=f"{elev}m (屈折有)", color=colors[elev], linestyle='-')
        ax_rise.plot(dates_str, r_wo, label=f"{elev}m (屈折無)", color=colors[elev], linestyle='--')
        rise_all_curves.extend([r_w, r_wo])

        # 下段：日の入り
        ax_set.plot(dates_str, s_w, label=f"{elev}m (屈折有)", color=colors[elev], linestyle='-')
        ax_set.plot(dates_str, s_wo, label=f"{elev}m (屈折無)", color=colors[elev], linestyle='--')
        set_all_curves.extend([s_w, s_wo])

    # 軸のレンジとフォーマット設定
    margin_ratio = 0.05
    for ax, all_data in zip([ax_rise, ax_set], [rise_all_curves, set_all_curves]):
        flat_data = [item for sublist in all_data for item in sublist if not np.isnan(item)]
        if flat_data:
            d_min, d_max = min(flat_data), max(flat_data)
            span = d_max - d_min
            margin = span * margin_ratio if span > 0 else 0.1
            ax.set_ylim(d_min - margin, d_max + margin)

        ax.yaxis.set_major_formatter(time_fmt)
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize='small')

    ax_rise.set_ylabel("日の出時刻 (JST)")
    ax_set.set_ylabel("日の入り時刻 (JST)")
    ax_set.set_xlabel("月/日")

    # X軸の間隔調整
    num_ticks = 12
    step = max(1, len(dates_str) // num_ticks)
    ax_set.set_xticks(np.arange(0, len(dates_str), step))
    ax_set.set_xticklabels([dates_str[i] for i in range(0, len(dates_str), step)], rotation=45)

    plt.tight_layout(rect=[0, 0, 0.9, 0.96])
    print("グラフを表示します...")
    plt.show()


def get_user_inputs() -> Tuple[float, float, datetime, int]:
    """計算開始日と処理期間などのパラメータをユーザから取得する。

    入力が空、または不適切な場合はデフォルト値を設定する。

    Returns:
        Tuple[float, float, datetime, int]: 以下の要素を含むタプル。
            - lat (float): 緯度（度）。
            - lon (float): 経度（度）。
            - start_date (datetime): 計算開始日のdatetimeオブジェクト。
            - num_days (int): 処理期間の日数。
    """
    # 1. 緯度・経度
    loc_prompt = f"緯度,経度 を入力してください (例: 35.68,139.76) [デフォルト: {TARGET_LATITUDE_DEG},{TARGET_LONGITUDE_DEG}]: "
    loc_in = input(loc_prompt).strip()

    if not loc_in:
        lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG
    else:
        try:
            parts = [p.strip() for p in loc_in.split(',')]
            if len(parts) == 2:
                lat, lon = float(parts[0]), float(parts[1])
            else:
                raise ValueError
        except ValueError:
            print("入力形式エラー。デフォルト値を使用します。")
            lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG

    # 2. 開始日
    date_str = input("計算開始 年月日を入力してください (yyyy/mm/dd): ")
    try:
        start_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        print("入力形式が正しくありません。デフォルト値（30日前）を設定します。")
        start_date = datetime.now() - timedelta(days=30)

    # 3. 処理期間
    num_days_str = input("処理期間（日数）を入力してください (デフォルト: 60): ")
    try:
        num_days = int(num_days_str)
    except ValueError:
        print("入力が正しくありません。期間を 60 日に設定しました。")
        num_days = 60

    return lat, lon, start_date, num_days


def main() -> None:
    """スクリプトのメインエントリポイント。"""
    plt.rcParams['font.family'] = 'MS Gothic'

    lat, lon, start_date, num_days = get_user_inputs()

    elevations = [0, 1000, 2000, 3000]
    dates_raw = [start_date + timedelta(days=i) for i in range(num_days)]

    plot_results = {}
    print("計算中...")
    for elev in elevations:
        r_w, s_w = calculate_sun_times(lat, lon, elev, start_date, num_days, True)
        r_wo, s_wo = calculate_sun_times(lat, lon, elev, start_date, num_days, False)
        plot_results[elev] = {
            'with_ref': (r_w, s_w),
            'without_ref': (r_wo, s_wo)
        }

    plot_sun_data(lat, lon, dates_raw, elevations, plot_results)


if __name__ == "__main__":
    main()
