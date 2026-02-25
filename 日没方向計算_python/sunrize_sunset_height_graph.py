#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定された地点・年月日において、標高の変化が日出・日入時刻に与える影響を可視化するスクリプト。

このモジュールは、特定の1日における標高0mから3000mまでの日の出・日没時刻を計算し、
縦軸に標高、横軸に時刻をとったグラフを作成します。
大気屈折の影響の有無を比較できるように2本の線を描画します。

Attributes:
    TARGET_LATITUDE_DEG (float): 観測地点のデフォルト緯度（度）。
    TARGET_LONGITUDE_DEG (float): 観測地点のデフォルト経度（度）。
    MAX_HEIGHT (float): 計算を行う最大標高（m）。

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

import sys
import ephem
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
MAX_HEIGHT = 4000.0
# =================================================================


def get_user_inputs_for_single_day() -> Tuple[float, float, datetime]:
    """計算対象の地点と年月日をユーザから取得する。

    Returns:
        Tuple[float, float, datetime]: 以下の要素を含むタプル。
            - lat (float): 緯度（度）。
            - lon (float): 経度（度）。
            - target_date (datetime): 計算対象日のdatetimeオブジェクト。
    """
    # 1. 緯度・経度
    loc_prompt = f"緯度,経度 を入力してください (例: 35.68,139.76) [デフォルト: {TARGET_LATITUDE_DEG},{TARGET_LONGITUDE_DEG}]: "
    loc_in = input(loc_prompt).strip()

    if not loc_in:
        lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG
    else:
        try:
            parts = [p.strip() for p in loc_in.split(',')]
            lat, lon = float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            print("入力形式エラー。デフォルト値を使用します。")
            lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG

    # 2. 対象日
    date_str = input("計算対象年月日を入力してください (yyyy/mm/dd): ")
    try:
        target_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        print("入力形式が正しくありません。本日を設定します。")
        target_date = datetime.now()

    return lat, lon, target_date


def calculate_sun_times_by_elevation(
    lat: float,
    lon: float,
    elevations: np.ndarray,
    target_date: datetime,
    with_refraction: bool
) -> Tuple[List[float], List[float]]:
    """標高の配列に基づき、それぞれの日の出・日の入り時刻を計算する。

    Args:
        lat (float): 観測地点の緯度（度）。
        lon (float): 観測地点の経度（度）。
        elevations (np.ndarray): 計算対象の標高（m）の配列。
        target_date (datetime): 計算対象日。
        with_refraction (bool): 大気屈折を考慮する場合はTrue。

    Returns:
        Tuple[List[float], List[float]]:
            - rise_times: 標高ごとの日の出時刻リスト（時間単位float）。
            - set_times: 標高ごとの日の入り時刻リスト（時間単位float）。
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)

    rise_times = []
    set_times = []
    jst_offset = timedelta(hours=9)

    for elev in elevations:
        obs.elevation = float(elev)
        # 標高補正（伏角の計算）
        # https://www.nao.ac.jp/contents/about/reports/report-naoj/p91.pdf
        # 幾何学的眼高差: dip = (1.926/60)*sqrt(elevation)    ... (6)
        # 大気中の屈折を考慮した補正: dip = (1.77/60)*sqrt(elevation)    ... (15)
        if with_refraction:
            dip = 0.0293 * math.sqrt(elev)
        else:
            dip = 0.032 * math.sqrt(elev)

        # obs.horizon = -math.radians(dip)    # floatで渡す場合の単位は radian
        obs.horizon = str(-dip)             # stringで渡す場合の単位は degree
        obs.date = target_date - jst_offset
        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        try:
            # 日の出
            rise_t = obs.next_rising(sun).datetime() + jst_offset
            rise_times.append(rise_t.hour + rise_t.minute / 60.0 + rise_t.second / 3600.0)
            # 日没
            set_t = obs.next_setting(sun).datetime() + jst_offset
            set_times.append(set_t.hour + set_t.minute / 60.0 + set_t.second / 3600.0)
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            rise_times.append(np.nan)
            set_times.append(np.nan)

    return rise_times, set_times


def plot_elevation_vs_time(
    lat: float,
    lon: float,
    target_date: datetime,
    elevations: np.ndarray,
    results: Dict
) -> None:
    """縦軸を標高、横軸を時刻とした日出・日入グラフを描画する。

    Args:
        lat (float): 緯度。
        lon (float): 経度。
        target_date (datetime): 対象年月日。
        elevations (np.ndarray): 標高データの配列。
        results (Dict): 大気屈折の有無をキーとした計算結果。
    """
    fig, (ax_rise, ax_set) = plt.subplots(2, 1, figsize=(10, 12))
    date_str = target_date.strftime('%Y/%m/%d')
    fig.suptitle(f"標高別 日出・日入時刻の変化\n({date_str}, 緯度:{lat}°, 経度:{lon}°)", fontsize=14)

    # 時刻用フォーマッタ (HH:MM)
    time_fmt = FuncFormatter(lambda y, p: f"{int(y):02d}:{int(round((y - int(y)) * 60)) % 60:02d}")

    # プロット実行
    # 日出 (上段)
    ax_rise.plot(results['with_ref']['rise'], elevations, 'b-', label='大気屈折あり')
    ax_rise.plot(results['without_ref']['rise'], elevations, 'b--', label='大気屈折なし')
    ax_rise.set_title("日の出時刻 (JST)")

    # 日入 (下段)
    ax_set.plot(results['with_ref']['set'], elevations, 'r-', label='大気屈折あり')
    ax_set.plot(results['without_ref']['set'], elevations, 'r--', label='大気屈折なし')
    ax_set.set_title("日の入り時刻 (JST)")

    # グラフの共通設定
    for ax, key in zip([ax_rise, ax_set], ['rise', 'set']):
        ax.set_ylabel("標高 (m)")
        ax.set_xlabel("時刻")
        ax.xaxis.set_major_formatter(time_fmt)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()

        # 横軸レンジの自動調整（データの最小最大±5%）
        all_vals = results['with_ref'][key] + results['without_ref'][key]
        clean_vals = [v for v in all_vals if not np.isnan(v)]
        if clean_vals:
            v_min, v_max = min(clean_vals), max(clean_vals)
            margin = max((v_max - v_min) * 0.05, 0.02)  # 最小でも1分程度の幅
            ax.set_xlim(v_min - margin, v_max + margin)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    print("グラフを表示します...")
    plt.show()


def format_hour_to_hms(hour_float: float) -> str:
    """時間（float形式）を HH:MM:SS 形式の文字列に変換する。

    0.5 を入力すると "00:30:00"、14.75 を入力すると "14:45:00" のように、
    小数部分を分・秒に換算して整形した文字列を返す。数値が NaN の場合は、
    時刻が定義できないものとして "--:--:--" を返す。

    Args:
        hour_float (float): 時間単位の数値（例: 12.5 は 12時30分）。

    Returns:
        str: HH:MM:SS 形式の時刻文字列。計算不能な場合は "--:--:--"。
    """
    if np.isnan(hour_float):
        return "--:--:--"
    total_seconds = int(round(hour_float * 3600))
    h, remainder = divmod(total_seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def print_text_results(
        lat: float,
        lon: float,
        target_date: datetime,
        elevations: np.ndarray,
        results: Dict) -> None:
    """計算結果をコンソールに表形式で出力する。

    指定された地点、日付における標高ごとの日の出・日の入り時刻を、
    大気屈折の影響の有無を並べて比較しやすいテーブル形式で表示する。

    Args:
        lat (float): 観測地点の緯度。
        lon (float): 観測地点の経度。
        target_date (datetime): 計算対象日。
        elevations (np.ndarray): 計算を行った標高（m）の配列。
        results (Dict): 以下の構造を持つ計算結果の辞書。
            - 'with_ref': {'rise': List[float], 'set': List[float]}
            - 'without_ref': {'rise': List[float], 'set': List[float]}

    Returns:
        None: 結果を直接標準出力（コンソール）に表示する。
    """
    date_str = target_date.strftime('%Y/%m/%d')
    header = "  標高  | 日出(屈折有) | 日出(屈折無) | 日入(屈折有) | 日入(屈折無)"
    line = "--------------------------------------------------------------------"
    print(line)
    print(f" 計算結果: {date_str} (緯度:{lat}, 経度:{lon})")
    print(line)
    print(header)
    print(line)
    for i, elev in enumerate(elevations):
        r_w = format_hour_to_hms(results['with_ref']['rise'][i])
        r_wo = format_hour_to_hms(results['without_ref']['rise'][i])
        s_w = format_hour_to_hms(results['with_ref']['set'][i])
        s_wo = format_hour_to_hms(results['without_ref']['set'][i])
        print(f"{int(elev):5d}m  | {r_w:10}   | {r_wo:10}   | {s_w:10}   | {s_wo:10}")
    print(line)


def main() -> None:
    """スクリプトのメイン処理。"""
    lat, lon, target_date = get_user_inputs_for_single_day()

    ans = input("計算結果の出力方法を、 グラフを表示 (g), テキスト表示 (t) のいずれにしますか？ (g / t): ")

    if ans.lower() == 'g':
        # 標高 0m から MAX_HEIGHT までを100分割して計算（曲線用）
        elevations = np.linspace(0, MAX_HEIGHT, 101)
    elif ans.lower() == 't':
        # 0からMAX_HEIGHTまで100mごとの値を入れる
        elevations = np.arange(0, MAX_HEIGHT + 1, 500)
    else:
        print("無効な選択です。プログラムを終了します。")
        sys.exit()

    print(f"{target_date.strftime('%Y/%m/%d')} のデータを標高 {int(MAX_HEIGHT)}m まで計算中...")

    # 計算実行
    r_w, s_w = calculate_sun_times_by_elevation(lat, lon, elevations, target_date, True)
    r_wo, s_wo = calculate_sun_times_by_elevation(lat, lon, elevations, target_date, False)

    results = {
        'with_ref': {'rise': r_w, 'set': s_w},
        'without_ref': {'rise': r_wo, 'set': s_wo}
    }

    if ans.lower() == 'g':
        # グラフを表示
        plot_elevation_vs_time(lat, lon, target_date, elevations, results)
    elif ans.lower() == 't':
        # テキスト表示
        print_text_results(lat, lon, target_date, elevations, results)


if __name__ == "__main__":
    main()
