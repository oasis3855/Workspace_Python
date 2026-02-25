#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定された緯度・経度に基づき太陽の軌道を計算・可視化するスクリプト。

このモジュールは、pyephemライブラリを使用して特定地点の日の出、日没、
日中時間、および方位角を計算し、その結果をコンソールに出力するとともに
Matplotlibを使用して4段のグラフで可視化します。

Attributes:
    TARGET_LATITUDE_DEG (float):    観測地点のデフォルト緯度（度）。
    TARGET_LONGITUDE_DEG (float):   観測地点のデフォルト経度（度）。
    TARGET_ELEVATION_M (float):     観測地点のデフォルト標高（m）。
    DIP_MODE_EPHEM(bool):           伏角の空気屈折効果をEphemの内部計算モードにするかどうか

Requires:
    - Python 3.x
    - ephem: 天文計算用ライブラリ (pip install pyephem)
    - numpy: 数値計算用ライブラリ (pip install numpy)
    - matplotlib: グラフ描画用ライブラリ (pip install matplotlib)

Author:
    Google Gemini3

Version:
    1.0.0 (2025/12/24)
    1.1.0 (2025/12/28), 標高計算の追加
"""
import csv
from datetime import datetime, timedelta
import ephem
import math
import matplotlib.pyplot as plt
import numpy as np
import sys
from typing import List, Dict, Tuple

# =================================================================
# グローバル設定変数 (デフォルト値を変えるには、ここを編集してください)
# =================================================================
TARGET_LATITUDE_DEG = 34.67
TARGET_LONGITUDE_DEG = 135.5
TARGET_ELEVATION_M = 0.0
DIP_MODE_EPHEM = True       # 伏角の空気屈折効果をEphemの内部計算モードにするかどうか
# =================================================================


def calculate_sun_data(
        lat: float,
        lon: float,
        elevation: float,
        start_date: datetime,
        days_count: int) -> List[Dict]:
    """
    指定された条件に基づき、太陽のデータ（日の出・日没等）を計算して辞書のリストで返す。

    Args:
        lat (float): 観測地点の緯度（度）。北緯は正、南緯は負の値。
        lon (float): 観測地点の経度（度）。東経は正、西経は負の値。
        elevation (float): 観測地点の標高（メートル）。
        start_date (datetime): 計算開始年月日。
        days_count (int): 計算を行う日数。

    Returns:
        List[Dict]: 各日の計算結果を格納した辞書のリスト。各辞書には以下のキーが含まれる。
            - date (str): 年月日 (YYYY/MM/DD)
            - rise_t (str): 日の出時刻 (JST, HH:MM:SS)
            - rise_az (float): 日の出方位角 (度)
            - set_t (str): 日没時刻 (JST, HH:MM:SS)
            - set_az (float): 日没方位角 (度)
            - duration_t (str): 日中時間 (HH:MM:SS)
            - duration_h (float): 日中時間の数値（時間単位）
            - rise_h_num (float): グラフ用の日の出時刻（時間単位）
            - set_h_num (float): グラフ用の日没時刻（時間単位）
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

    if (DIP_MODE_EPHEM):
        # obs.horizon = -math.radians(dip)    # floatで渡す場合の単位は radian
        obs.horizon = str(-dip_noair)             # stringで渡す場合の単位は degree

        # 伏角を真空中の値(dip_noair)で設定した場合、気圧・気温を設定するとEphemが自動的に空気補正を行ってくれる
        pressure_0m = 1013.25   # 標高 0mの気圧 [hPa]
        pressure = pressure_0m * (1 - 2.25577e-5 * elevation) ** 5.2559
        temperature_0m = 15.0   # 標高 0mの気温 [℃]
        temperature = temperature_0m - 0.6 * elevation / 100
        obs.pressure = pressure         # Ephemの標準値は 1010.0 [hPa]
        obs.temperature = temperature   # Ephemの標準値は 15.0 [℃]

    else:
        obs.horizon = str(-dip_ref)             # stringで渡す場合の単位は degree

        # 伏角を空気中の値(dip_ref)で設定した場合、Ephemの自動空気補正を無効化するために 気圧を 0 に設定する
        obs.pressure = 0.0              # Ephemの標準値は 1010.0 [hPa]

    print(f"伏角:{dip_ref}° (大気屈折あり{'' if DIP_MODE_EPHEM else ':採用'}), {dip_noair}° (大気屈折なし{':採用' if DIP_MODE_EPHEM else ''})")
    print(f"気圧:{obs.pressure:.0f} hPa{'(Ephem大気屈折計算)' if DIP_MODE_EPHEM else ''}, 気温:{obs.temperature:.1f} 度")

    results = []
    jst_offset = timedelta(hours=9)

    for i in range(days_count):
        current_date = start_date + timedelta(days=i)
        # その日の開始時刻（JST 00:00）をセット
        obs.date = current_date - jst_offset

        sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

        try:
            # --- 日の出 ---
            rise_time_ephem = obs.next_rising(sun)
            obs.date = rise_time_ephem
            sun.compute(obs)
            rise_az = np.degrees(sun.az)
            rise_jst = rise_time_ephem.datetime() + jst_offset

            # --- 日没 ---
            # 日没は日の出の後に来るように設定
            set_time_ephem = obs.next_setting(sun)
            obs.date = set_time_ephem
            sun.compute(obs)
            set_az = np.degrees(sun.az)
            set_jst = set_time_ephem.datetime() + jst_offset

            # --- 日中時間 (日没 - 日の出) ---
            duration_td = set_time_ephem.datetime() - rise_time_ephem.datetime()
            total_seconds = int(duration_td.total_seconds())
            d_h, rem = divmod(total_seconds, 3600)
            d_m, d_s = divmod(rem, 60)
            duration_str = f"{d_h:02d}:{d_m:02d}:{d_s:02d}"
            duration_hours = total_seconds / 3600.0

            results.append({
                "date": current_date.strftime('%Y/%m/%d'),
                "rise_t": rise_jst.strftime('%H:%M:%S'),
                "rise_az": rise_az,
                "set_t": set_jst.strftime('%H:%M:%S'),
                "set_az": set_az,
                "duration_t": duration_str,
                "duration_h": duration_hours,
                "rise_h_num": rise_jst.hour + rise_jst.minute / 60.0 + rise_jst.second / 3600.0,
                "set_h_num": set_jst.hour + set_jst.minute / 60.0 + set_jst.second / 3600.0
            })

        except (ephem.AlwaysUpError, ephem.NeverUpError):
            results.append({
                "date": current_date.strftime('%Y/%m/%d'),
                "rise_t": "--:--:--", "rise_az": np.nan,
                "set_t": "--:--:--", "set_az": np.nan,
                "duration_t": "--:--:--", "duration_h": np.nan,
                "rise_h_num": np.nan, "set_h_num": np.nan
            })

    return results


def plot_data(lat: float, lon: float, elevation: float, data: List[Dict]) -> None:
    """
    計算結果のリストに基づき、4段のグラフを表示する。

    Args:
        lat (float): 観測地点の緯度（度）。
        lon (float): 観測地点の経度（度）。
        elevation (float): 観測地点の標高（m）。
        data (List[Dict]): calculate_sun_data 関数によって生成されたデータリスト。
    """
    dates = [d["date"][5:] for d in data]
    rise_times = [d["rise_h_num"] for d in data]
    set_times = [d["set_h_num"] for d in data]
    durations = [d["duration_h"] for d in data]
    rise_azs = [d["rise_az"] for d in data]
    set_azs = [d["set_az"] for d in data]

    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    fig.suptitle(f"太陽データ: 緯度 {lat}°, 経度 {lon}°, 標高 {elevation}m", fontsize=16)

    # 共通プロット設定: 点のみ、線なし
    plot_style = {'marker': '.', 'markersize': 4, 'linestyle': 'None'}
    # 余白設定 (%)
    margin = 0.05

    # 1. 日の出時刻
    axes[0].plot(rise_times, color='orange', **plot_style)
    axes[0].set_ylabel("日の出時刻 (JST)")
    axes[0].grid(True, linestyle='--', alpha=0.7)

    # 2. 日没時刻
    axes[1].plot(set_times, color='darkblue', **plot_style)
    axes[1].set_ylabel("日没時刻 (JST)")
    axes[1].grid(True, linestyle='--', alpha=0.7)

    # 3. 日中時間
    axes[2].plot(durations, color='green', **plot_style)
    axes[2].set_ylabel("日中時間 (時間)")
    axes[2].grid(True, linestyle='--', alpha=0.7)

    # 4. 方位角 (左軸:日の出, 右軸:日没)
    # 左軸 (日の出)
    ax4_left = axes[3]
    ax4_left.plot(rise_azs, color='orange', label='日の出方位角', **plot_style)
    ax4_left.set_ylabel("日の出方位角 (度/左軸)", color='orange')
    ax4_left.tick_params(axis='y', labelcolor='orange')

    # 日の出方位角の動的レンジ設定 (NaNを除外して計算)
    if not np.all(np.isnan(rise_azs)):
        r_min, r_max = np.nanmin(rise_azs), np.nanmax(rise_azs)
        ax4_left.set_ylim(r_min - abs(r_max - r_min) * margin, r_max + abs(r_max - r_min) * margin)

    ax4_left.grid(True, linestyle='--', alpha=0.7)

    # 右軸 (日没)
    ax4_right = ax4_left.twinx()
    ax4_right.plot(set_azs, color='darkblue', label='日没方位角', **plot_style)
    ax4_right.set_ylabel("日没方位角 (度/右軸)", color='darkblue')
    ax4_right.tick_params(axis='y', labelcolor='darkblue')

    # 日没方位角の動的レンジ設定
    if not np.all(np.isnan(set_azs)):
        s_min, s_max = np.nanmin(set_azs), np.nanmax(set_azs)
        ax4_right.set_ylim(s_min - abs(s_max - s_min) * margin, s_max + abs(s_max - s_min) * margin)

    # 凡例をまとめる
    h1, l1 = ax4_left.get_legend_handles_labels()
    h2, l2 = ax4_right.get_legend_handles_labels()
    ax4_left.legend(h1 + h2, l1 + l2, loc='upper center', ncol=2, fontsize='small')

    # フォーマッタ (時刻用)
    from matplotlib.ticker import FuncFormatter
    time_fmt = FuncFormatter(lambda y, p: f"{int(y):02d}:{int((y-int(y))*60):02d}")
    axes[0].yaxis.set_major_formatter(time_fmt)
    axes[1].yaxis.set_major_formatter(time_fmt)

    # X軸設定
    num_ticks = 12
    step = max(1, len(dates) // num_ticks)
    axes[3].set_xticks(np.arange(0, len(dates), step))
    axes[3].set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)
    axes[3].set_xlabel("月/日")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()


def get_user_inputs() -> Tuple[float, float, float, datetime, int]:
    """計算開始日と処理期間をユーザから取得する。

    入力が不適切な場合は、開始日は「30日前」、期間は「60日」をデフォルト値として設定する。

    Returns:
        Tuple[float, float, float, datetime, int]:
            - lat(float): 緯度(度)
            - lon(float): 経度(度)
            - elev(float): 標高(m)
            - start_date(datetime): 開始日のdatetimeオブジェクト
            - num_days(int): 処理期間の日数
    """

    # 1. 緯度・経度のカンマ区切り入力
    loc_prompt = f"緯度,経度 を入力してください (例: 35.68,139.76) [デフォルト: {TARGET_LATITUDE_DEG},{TARGET_LONGITUDE_DEG}]: "
    loc_in = input(loc_prompt).strip()

    if not loc_in:
        lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG
    else:
        try:
            # カンマで分割し、前後の空白を削除してfloat型に変換
            parts = [p.strip() for p in loc_in.split(',')]
            if len(parts) == 2:
                lat, lon = float(parts[0]), float(parts[1])
            else:
                raise ValueError("入力が2項目ではありません")
        except ValueError:
            print("入力形式エラー。デフォルト値を使用します。")
            lat, lon = TARGET_LATITUDE_DEG, TARGET_LONGITUDE_DEG

    # 2. 標高
    elev_in = input(f"標高(m)を入力してください [デフォルト: {TARGET_ELEVATION_M}]: ").strip()
    elev = float(elev_in) if elev_in else TARGET_ELEVATION_M

    # 3. 開始日の取得
    date_str = input("計算開始 年月日を入力してください (yyyy/mm/dd): ")
    try:
        start_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        print("入力形式が正しくありません。デフォルト値（30日前）を設定します。")
        start_date = datetime.now() - timedelta(days=30)

    # 4. 処理期間の取得
    num_days_str = input("処理期間（日数）を入力してください (デフォルト: 60): ")
    try:
        num_days = int(num_days_str)
    except ValueError:
        print("入力が正しくありません。期間を 60 日に設定しました。")
        num_days = 60

    return lat, lon, elev, start_date, num_days


def main() -> None:
    """メイン実行処理。

    太陽軌道データの計算を実行し、結果をCSVまたはグラフ出力する。
    また、ユーザーの入力に応じてグラフ表示を起動する。
    """
    print("太陽軌道データの計算を実行し、結果をCSVまたはグラフ出力します")

    lat, lon, elevation, start_date, num_days = get_user_inputs()

    print(
        f"--- 太陽データリスト (北緯:{lat},東経:{lon},標高:{elevation}m, 計算開始: {start_date.year}/{start_date.month}/{start_date.day}, {num_days}日間) ---")

    ans = input("計算結果の出力方法を、 グラフを表示 (g), テキスト表示 (t), CSVファイル出力 (c) のいずれにしますか？ (g / t / c): ")

    sun_results = calculate_sun_data(lat, lon, elevation, start_date, num_days)

    if ans.lower() == 'g':
        plot_data(lat, lon, elevation, sun_results)
    elif ans.lower() == 't':
        print("年月日,日の出時刻,日の出方角,日没時刻,日没方角(度),日中時間")
        print("----------------------------------------------------------------")
        for r in sun_results:
            r_az = f"{r['rise_az']:.1f}" if not np.isnan(r['rise_az']) else "N/A"
            s_az = f"{r['set_az']:.1f}" if not np.isnan(r['set_az']) else "N/A"
            print(f"{r['date']},{r['rise_t']},{r_az},{r['set_t']},{s_az},{r['duration_t']}")
    elif ans.lower() == 'c':
        # CSVファイル出力
        filename = f"sun_data_{start_date.year}{start_date.month:02d}{start_date.day:02d}.csv"
        try:
            # utf_8_sig を指定することで、Excelで開いた際の文字化けを防ぎます
            with open(filename, 'w', encoding='utf_8_sig', newline='') as f:
                writer = csv.writer(f)
                # ヘッダーの書き込み
                writer.writerow(["年月日", "日の出時刻", "日の出方角", "日没時刻", "日没方角(度)", "日中時間"])
                # データの書き込み
                for r in sun_results:
                    r_az = f"{r['rise_az']:.1f}" if not np.isnan(r['rise_az']) else "N/A"
                    s_az = f"{r['set_az']:.1f}" if not np.isnan(r['set_az']) else "N/A"
                    writer.writerow([r['date'], r['rise_t'], r_az,
                                    r['set_t'], s_az, r['duration_t']])
            print(f"CSVファイルをカレントディレクトリに保存しました: {filename}")
        except Exception as e:
            print(f"CSV保存中にエラーが発生しました: {e}", file=sys.stderr)
    else:
        print("無効な選択です。プログラムを終了します。")


# --- エントリーポイント ---
if __name__ == "__main__":
    main()
