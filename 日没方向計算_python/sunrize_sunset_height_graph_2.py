#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""標高と大気屈折のモデルによる日出・日入時刻の差異を比較するスクリプト。

Attributes:
    MAX_HEIGHT (float): 計算を行う最大標高（m）。
"""

import ephem  # type: ignore
import math
import sys
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
MAX_HEIGHT = 4000.0
# =================================================================


def get_user_inputs_for_single_day() -> Tuple[float, float, datetime]:
    """地点と年月日をユーザから取得する。"""
    loc_in = input(f"緯度,経度 [{TARGET_LATITUDE_DEG},{TARGET_LONGITUDE_DEG}]: ").strip()
    if not loc_in:
        lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG
    else:
        parts = loc_in.split(',')
        lat, lon = float(parts[0]), float(parts[1])

    date_str = input("年月日 (yyyy/mm/dd): ")
    try:
        target_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        target_date = datetime.now()
    return lat, lon, target_date


def calculate_sun_times_advanced(
    lat: float,
    lon: float,
    elevations: np.ndarray,
    target_date: datetime,
    mode: str
) -> Tuple[List[float], List[float]]:
    """モード別の伏角と屈折設定で日出・日入時刻を計算する。

    Args:
        mode: 'none' (屈折なし), 'standard' (標準屈折), 'extended' (深い水平線)
    """
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    jst_offset = timedelta(hours=9)
    rise_times, set_times = [], []

    # debug
    print(f"obs.horizon={obs.horizon}")

    for elev in elevations:
        obs.elevation = float(elev)
        h_sqrt = math.sqrt(max(elev, 0))

        # 太陽オブジェクトの準備
        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        if mode == 'none':
            # 1. 大気屈折なし: 幾何学的伏角 + 太陽の屈折補正を無効化
            dip = 0.0321 * h_sqrt  # 1.926/60
            obs.horizon = str(-dip)
            obs.pressure = 0  # 屈折を計算させない
        elif mode == 'standard':
            # 2. 標準屈折: 浮き上がった見かけの伏角 + 標準の太陽屈折
            dip = 0.0295 * h_sqrt  # 1.77/60
            obs.horizon = str(-dip)
            obs.pressure = 1013.25
            # obs.pressure = 0
        elif mode == 'extended':
            # 3. 深い水平線: 屈折で見える限界距離に基づく、より深い角度
            # 地心からの距離を考慮した実効的な深さ
            dip = 0.0353 * h_sqrt
            obs.horizon = str(-dip)
            obs.pressure = 1013.25
            # obs.pressure = 0

        obs.date = target_date - jst_offset
        try:
            r = obs.next_rising(sun).datetime() + jst_offset
            s = obs.next_setting(sun).datetime() + jst_offset
            rise_times.append(r.hour + r.minute / 60.0 + r.second / 3600.0)
            set_times.append(s.hour + s.minute / 60.0 + s.second / 3600.0)
        except BaseException:
            rise_times.append(np.nan)
            set_times.append(np.nan)

    return rise_times, set_times


def format_hour_to_hms(hour_float: float) -> str:
    """時間(float)を HH:MM:SS に変換。"""
    if np.isnan(hour_float):
        return "--:--:--"
    ts = int(round(hour_float * 3600))
    return f"{ts//3600:02d}:{(ts%3600)//60:02d}:{ts%60:02d}"


def plot_advanced(lat, lon, date, elevs, results):
    """3モードの比較グラフを描画。"""
    plt.rcParams['font.family'] = 'MS Gothic'
    fig, (ax_r, ax_s) = plt.subplots(2, 1, figsize=(11, 12))

    styles = {'none': ('k--', '無効(幾何学)'), 'standard': ('g-', '標準屈折'), 'extended': ('r-', '深い水平線')}

    for mode, (style, label) in styles.items():
        ax_r.plot(results[mode]['rise'], elevs, style, label=label)
        ax_s.plot(results[mode]['set'], elevs, style, label=label)

    time_fmt = FuncFormatter(lambda y, p: f"{int(y):02d}:{int((y%1)*60):02d}")
    for ax, title in zip([ax_r, ax_s], ["日の出 (JST)", "日の入り (JST)"]):
        ax.set_title(title)
        ax.set_ylabel("標高 (m)")
        ax.set_xlabel("時刻")
        ax.xaxis.set_major_formatter(time_fmt)
        ax.grid(True, alpha=0.3)
        ax.legend()

    plt.tight_layout()
    plt.show()


def main():
    lat, lon, date = get_user_inputs_for_single_day()
    ans = input("出力方法: グラフ(g) / テキスト(t): ").lower()

    elevs = np.linspace(0, MAX_HEIGHT, 101) if ans == 'g' else np.arange(0, MAX_HEIGHT + 1, 500)

    res = {}
    for m in ['none', 'standard', 'extended']:
        r, s = calculate_sun_times_advanced(lat, lon, elevs, date, m)
        res[m] = {'rise': r, 'set': s}

    date_str = date.strftime('%Y/%m/%d')
    print(f" 計算結果: {date_str} (緯度:{lat}, 経度:{lon})")

    if ans == 'g':
        plot_advanced(lat, lon, date, elevs, res)
    else:
        print(f"\n標高   | 幾何学的(無) | 標準屈折     | 深い水平線")
        print("-------+--------------+--------------+--------------")
        for i, e in enumerate(elevs):
            t_n = format_hour_to_hms(res['none']['rise'][i])
            t_s = format_hour_to_hms(res['standard']['rise'][i])
            t_e = format_hour_to_hms(res['extended']['rise'][i])
            print(f"{int(e):5d}m | {t_n}     | {t_s}     | {t_e}")


if __name__ == "__main__":
    main()
