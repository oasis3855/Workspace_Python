#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定された緯度・経度・標高に基づき日出・日没時刻を検証するスクリプト。

このモジュールは、pyephemライブラリを使用して特定地点の日の出、日没、
を計算し、その結果をテキスト出力およびグラフ描画します。

Attributes:
    TARGET_LATITUDE_DEG (float): 観測地点のデフォルト緯度（度）。
    TARGET_LONGITUDE_DEG (float): 観測地点のデフォルト経度（度）。
    HEIGHT (float): 観測地点のデフォルト標高（m）。
    REFRACTION_FACTOR (float): 大気屈折を考慮した地平線伏角と真空状態での地平線伏角の比。

Requires:
    - Python 3.x
    - ephem: 天文計算用ライブラリ (pip install pyephem)
    - numpy: 数値計算用ライブラリ (pip install numpy)
    - matplotlib: グラフ描画用ライブラリ (pip install matplotlib)

Author:
    Google Gemini3

Version:
    1.0.0 (2026/01/21)
"""

from typing import Dict, List, Optional, Tuple
import ephem
from datetime import datetime, timedelta
import math
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

LATITUDE_DEG = 34.67
LONGITUDE_DEG = 135.50
HEIGHT = 1000.0
REFRACTION_FACTOR = 1.4907


def calc_dip_angle(
        height_m: float,
        refraction_factor: float = REFRACTION_FACTOR,
        vacuum: bool = False) -> float:
    """観測者の標高から伏角 θ（地平線の落ち込み角）を計算する関数。

    vacuum=True の場合は屈折を考慮せず、純粋な幾何学的伏角を返す。
    vacuum=False の場合は有効地球半径モデルで屈折補正を行う。

    Args:
        height_m (float): 観測者の標高（m）。
        refraction_factor (float): 大気屈折係数（国立天文台Webサイトでの値で検証した結果 1.491 程度）。
        vacuum (bool): 真空中として屈折を無視するかどうか。

    Returns:
        float: 伏角（度）。
    """
    R = 6371000.0  # 地球半径 [m]

    if height_m <= 0:
        return 0.0

    # 幾何学的伏角（ラジアン）
    theta_geom = math.sqrt(2 * height_m / R)

    if vacuum:
        # 真空 → 幾何学的伏角のみ
        return math.degrees(theta_geom)

    # 大気屈折を考慮した伏角
    theta_refr = refraction_factor * theta_geom
    return math.degrees(theta_refr)


def calc_pressure(height_m: float) -> float:
    """標高から観測地点の気圧を推定する関数。

    国際標準大気（ISA）の簡易モデルを使用して気圧を計算する:

        p = p0 * (1 - 2.25577e-5 * h)^5.2559

    Args:
        height_m (float): 標高（m）。

    Returns:
        float: 観測地点の気圧（hPa）。
    """

    p0 = 1013.25  # hPa
    return p0 * (1 - 2.25577e-5 * height_m) ** 5.2559


def compute_sun_times(
    target_ymd: str,
    lat_deg: float,
    lon_deg: float,
    height_m: float,
    use_refraction: bool = True,
    use_pressure: bool = True,
    use_sun_radius: bool = False,
    refraction_factor: float = REFRACTION_FACTOR,
    flag_print: bool = True
) -> Tuple[datetime, datetime, float, float]:
    """日の出・日の入り時刻、伏角、気圧を計算する関数。

    伏角（dip）に加えて、必要に応じて太陽視半径（約 0.266°）を
    horizon に反映することができる。

    Args:
        target_ymd (str): 計算対象日（"YYYY/MM/DD"）。
        lat_deg (float): 観測地点の緯度（度）。
        lon_deg (float): 観測地点の経度（度）。
        height_m (float): 標高（m）。
        use_refraction (bool): 伏角に大気屈折を反映するか。
        use_pressure (bool): 標高に応じた気圧を反映するか。
        use_sun_radius (bool): 太陽視半径（約 0.266°）を horizon に加えるか。
        refraction_factor (float): 大気屈折係数。
        flag_print(bool): 結果をテキスト出力する

    Returns:
        tuple:
            datetime: 日の出時刻（JST）
            datetime: 日の入り時刻（JST）
            float: 伏角（度）
            float: 観測地点気圧（hPa）
    """
    # JST → UTC
    jst_offset = timedelta(hours=9)

    # 観測者設定
    obs = ephem.Observer()
    obs.date = datetime.strptime(target_ymd, "%Y/%m/%d") - jst_offset
    obs.lat = str(lat_deg)
    obs.lon = str(lon_deg)
    obs.elevation = float(height_m)

    # 気圧設定 (ephemのデフォルト気圧は1010.0 hPa)
    # pressure = calc_pressure(height_m) if use_pressure else 0.0
    pressure = calc_pressure(height_m) if use_pressure else 1013.25

    # 気温設定 (ephemのデフォルト気温は15.0 ℃)
    if use_refraction:
        obs.temperature = 15.0 - 0.6 * height_m / 100

    # 伏角（dip）
    if use_refraction:
        dip_deg = calc_dip_angle(height_m, refraction_factor, vacuum=False)
        pressure = 0.0      # 空気屈折を含んだ伏角θを用いる場合は、obs.pressureを0にしてEphem内の計算で空気屈折を重複加算するのを防ぐ
    else:
        dip_deg = calc_dip_angle(height_m, refraction_factor, vacuum=True)

    obs.pressure = pressure

    # 太陽視半径（約 0.266°）
    sun_radius_deg = 0.266 if use_sun_radius else 0.0

    # horizon = -(伏角 + 太陽視半径)
    horizon_deg = -(dip_deg + sun_radius_deg)
    obs.horizon = f"{horizon_deg}"

    # 太陽オブジェクト
    sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

    # 日の出・日の入り（UTC → JST）
    sunrise = obs.next_rising(sun).datetime() + jst_offset
    sunset = obs.next_setting(sun).datetime() + jst_offset

    if flag_print:
        print_result(
            sunrise,
            sunset,
            obs.elevation,
            obs.horizon * 360 / 2 / math.pi,
            obs.pressure,
            obs.temperature,
            use_refraction,
            use_sun_radius)

    return sunrise, sunset, dip_deg, pressure


def print_result(
    sunrise: datetime,
    sunset: datetime,
    height_m: float,
    dip_deg: float,
    pressure_hpa: float,
    temperature: float,
    use_refraction: bool,
    use_sun_radius: bool
) -> None:
    """compute_sun_times() の結果を指定フォーマットで画面表示する関数。

    Args:
        sunrise (datetime): 日の出時刻（JST）。
        sunset (datetime): 日の入り時刻（JST）。
        height_m (float): 標高（m）。
        dip_deg (float): 伏角（度）。
        pressure_hpa (float): 観測地点気圧 (hPa） 正の値の場合はephemが大気屈折効果を自動計算する。
        temperature (float): 観測地点気温 (℃) ephemが大気屈折効果を計算する場合に必要。
        use_refraction (bool): 大気屈折を考慮したかどうか。
        use_sun_radius (bool): 太陽視半径を考慮したかどうか。

    表示形式:
        日出      | 日没      | 標高 | 気温 | 伏角 | 気圧 | 屈折 | Sun視半径
        06:35:20 | 17:40:15 | 2500 | 15.0 | 0.225 | 760 | YES | NO
    """
    # YES/NO の文字列化
    refr = "YES" if use_refraction else "NO"
    sunr = "YES" if use_sun_radius else "NO"

    # 表示
    print(
        f"{sunrise.strftime('%H:%M:%S')} | "
        f"{sunset.strftime('%H:%M:%S')} | "
        f"{height_m:6.0f} | "
        f"{temperature:5.1f} | "
        f"{dip_deg:5.3f} | "
        f"{pressure_hpa:4.0f} | "
        f"{refr:3} | "
        f"{sunr}"
    )


def plot_sunrise_sunset(
    heights: List[int],
    sunrise_dict: Dict[Tuple[bool, bool, bool], List[datetime]],
    sunset_dict: Dict[Tuple[bool, bool, bool], List[datetime]],
    debug_heights: Optional[List[int]] = None,
    debug_sunrise: Optional[List[datetime]] = None,
    debug_sunset: Optional[List[datetime]] = None,
    target_ymd: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> None:
    """標高ごとの日の出・日の入り時刻をグラフ表示する。

    Args:
        heights (list[int]): 標高のリスト
        sunrise_dict (dict): param_set → 日の出時刻リスト
        sunset_dict (dict): param_set → 日の入り時刻リスト
    """

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=False)

    # グラフ全体タイトルを追加
    if target_ymd and lat is not None and lon is not None:
        fig.suptitle(
            f"標高と日出・日入時刻の関係 ({target_ymd} 緯度 {lat:.2f}° 経度 {lon:.2f}°)",
            fontsize=14
        )

    # 時刻フォーマット
    time_fmt = mdates.DateFormatter('%H:%M')

    # 色設定
    colors = {
        (False, True, False): "red",
        (True, False, False): "blue",
    }
    label_map = {
        (False, True, False): "真空伏角 + Ephem空気屈折補正",
        (True, False, False): "空気屈折 手動計算",
    }

    # ------------------------------------------------------------
    # 日の出グラフ
    # ------------------------------------------------------------
    for param, times in sunrise_dict.items():
        ax1.plot(times, heights, label=label_map[param], color=colors[param])

    ax1.set_ylabel("標高 (m)")
    ax1.set_title("日の出時刻")
    # ax1.invert_yaxis()
    ax1.xaxis.set_major_formatter(time_fmt)
    ax1.grid(True)
    ax1.legend(loc="best")

    # 横軸レンジをデータに合わせて最適化
    sunrise_all = []
    for times in sunrise_dict.values():
        sunrise_all.extend(times)
    ax1.set_xlim(min(sunrise_all), max(sunrise_all))

    # ------------------------------------------------------------
    # 日の入りグラフ
    # ------------------------------------------------------------
    for param, times in sunset_dict.items():
        ax2.plot(times, heights, label=label_map[param], color=colors[param])

    ax2.set_ylabel("標高 (m)")
    ax2.set_title("日の入り時刻")
    # ax2.invert_yaxis()
    ax2.xaxis.set_major_formatter(time_fmt)
    ax2.grid(True)
    ax2.legend(loc="best")

    # ★ 横軸レンジをデータに合わせて最適化
    sunset_all = []
    for times in sunset_dict.values():
        sunset_all.extend(times)
    ax2.set_xlim(min(sunset_all), max(sunset_all))

    if debug_heights:
        ax1.scatter(debug_sunrise, debug_heights, s=20, color="black", zorder=5)
        ax2.scatter(debug_sunset, debug_heights, s=20, color="black", zorder=5)

    plt.xlabel("時刻")
    plt.tight_layout()
    plt.show()


def get_user_inputs(
    default_ymd: str,
    default_lat: float,
    default_lon: float,
    default_height: float
) -> Tuple[str, float, float, float]:
    """ユーザ入力を受け取り、緯度・経度・日付・標高を返す関数。

    標高(height)については次の仕様とする:
        ・ユーザが数値を入力した場合 → その値（0以上）
        ・改行のみの場合 → -10000 を返す（複数計算モード用）

    Args:
        default_ymd (str): デフォルト日付（YYYY/MM/DD）
        default_lat (float): デフォルト緯度
        default_lon (float): デフォルト経度
        default_height (float): デフォルト標高

    Returns:
        tuple:
            str: 日付（YYYY/MM/DD）
            float: 緯度
            float: 経度
            float: 標高（または -10000）
    """

    # --- 日付入力 ---
    ymd_in = input(f"日付を入力してください（YYYY/MM/DD, デフォルト {default_ymd}）: ").strip()
    if ymd_in == "":
        target_ymd = default_ymd
    else:
        try:
            datetime.strptime(ymd_in, "%Y/%m/%d")
            target_ymd = ymd_in
        except ValueError:
            today = datetime.now().strftime("%Y/%m/%d")
            print(f"不正な日付のため、今日の日付 {today} を使用します")
            target_ymd = today

    # --- 緯度入力 ---
    lat_in = input(f"緯度を入力してください（デフォルト {default_lat}）: ").strip()
    lat = float(lat_in) if lat_in else default_lat

    # --- 経度入力 ---
    lon_in = input(f"経度を入力してください（デフォルト {default_lon}）: ").strip()
    lon = float(lon_in) if lon_in else default_lon

    # --- 標高入力（特殊仕様） ---
    height_in = input(f"標高を入力してください（m, 改行のみで複数計算モード）: ").strip()

    if height_in == "":
        # 複数計算モードを示す特別値
        height = -10000
    else:
        try:
            height = float(height_in)
            if height < 0:
                print("標高は0以上である必要があるため、デフォルト値を使用します")
                height = default_height
        except ValueError:
            print(f"不正な値のため、標高はデフォルト値 {default_height} m を使用します")
            height = default_height

    return target_ymd, lat, lon, height


def debug_input_mode() -> Optional[
    Tuple[
        str,                # target_ymd
        float,              # lat
        float,              # lon
        List[int],          # debug_heights
        List[datetime],     # debug_sunrise
        List[datetime]      # debug_sunset
    ]
]:
    """デバッグ用データ連続入力モード。

    1行目: YYYY/MM/DD, lat, lon
    2行目以降: height, sunrise(HH:MM[:SS]), sunset(HH:MM[:SS])
    空行で終了。

    Returns:
        tuple:
            target_ymd (str)
            lat (float)
            lon (float)
            debug_heights (list[int])
            debug_sunrise (list[datetime])
            debug_sunset (list[datetime])
    """

    print("デバッグ用データ連続入力モードです。空行で終了します。")

    # --- 1行目：年月日, 緯度, 経度 ---
    while True:
        line = input().strip()
        if line == "":
            print("1行目が空行のため終了します。")
            return None

        try:
            ymd_str, lat_str, lon_str = [x.strip() for x in line.split(",")]
            datetime.strptime(ymd_str, "%Y/%m/%d")
            lat = float(lat_str)
            lon = float(lon_str)
            target_ymd = ymd_str
            break
        except Exception:
            print("形式: YYYY/MM/DD, 緯度, 経度 で入力してください。再入力してください。")

    # --- 2行目以降：標高, 日出, 日没 ---

    debug_heights = []
    debug_sunrise = []
    debug_sunset = []

    while True:
        line = input().strip()
        if line == "":
            break

        try:
            h_str, sr_str, ss_str = [x.strip() for x in line.split(",")]
            h = int(h_str)

            # 時刻パース（秒があってもなくてもOK）
            def parse_time(tstr):
                if len(tstr.split(":")) == 2:
                    tstr += ":00"
                return datetime.strptime(ymd_str + " " + tstr, "%Y/%m/%d %H:%M:%S")

            sr = parse_time(sr_str)
            ss = parse_time(ss_str)

            debug_heights.append(h)
            debug_sunrise.append(sr)
            debug_sunset.append(ss)

        except Exception:
            print("形式: 標高, 日出(HH:MM[:SS]), 日没(HH:MM[:SS]) で入力してください。")

    return target_ymd, lat, lon, debug_heights, debug_sunrise, debug_sunset


# ------------------------------------------------------------
# main
# ------------------------------------------------------------
def main():

    dbg = input("デバッグ用データ連続入力モードにしますか Y/N (デフォルト N): ").strip().upper()
    if dbg == "Y":
        result = debug_input_mode()
        if result is None:
            return

        target_ymd, lat, lon, dbg_heights, dbg_sunrise, dbg_sunset = result
        height = -10000  # 複数計算モードを示す特別値
    else:
        target_ymd, lat, lon, height = get_user_inputs(
            datetime.now().strftime("%Y/%m/%d"), LATITUDE_DEG, LONGITUDE_DEG, HEIGHT)
        dbg_heights = []
        dbg_sunrise = []
        dbg_sunset = []

    R = 6371000.0  # 地球半径 [m]
    theta_geom_par = math.sqrt(2.0 / R) * 360 / 2 / math.pi
    theta_refrect_par = REFRACTION_FACTOR * theta_geom_par

    print(f"date:{target_ymd}, 緯度{lat} 経度{lon}, 光学 θgeo = {theta_geom_par:1.5f}*sqrt(h), 大気屈折 θref = {theta_refrect_par:1.5f}*sqrt(h)")
    # 表ヘッダ
    print("日出     | 日没     | 標高   | 気温 | 伏角   | 気圧 | 屈折| Sun視半径")

    if height < 0:
        # ------------------------------------------------------------
        # ① 空入力 → 0〜4000 を 自動計算し、テキスト出力＆グラフ出力
        # ------------------------------------------------------------
        # テキスト表示用：500m ピッチ
        text_heights = list(range(0, 4001, 500))

        # グラフ用：10m ピッチ
        graph_heights = list(range(0, 4001, 10))

        # 使用する引数の組み合わせ（2通り）
        param_sets = [
            (False, True, False),   # 真空伏角 + Ephem空気屈折補正（赤）
            (True, False, False),   # 空気屈折 手動計算（青）
        ]

        # グラフ用データ格納
        sunrise_dict = {p: [] for p in param_sets}
        sunset_dict = {p: [] for p in param_sets}

        # ① テキスト表示（500m ピッチ）
        for h in text_heights:
            for use_refraction, use_pressure, use_sun_radius in param_sets:
                sunrise, sunset, dip, pressure = compute_sun_times(
                    target_ymd, lat, lon, h,
                    use_refraction=use_refraction,
                    use_pressure=use_pressure,
                    use_sun_radius=use_sun_radius,
                    refraction_factor=REFRACTION_FACTOR
                )
                # print_result は compute_sun_times 内で呼ばれている

        # ② グラフ用データ計算（10m ピッチ）
        for h in graph_heights:
            for use_refraction, use_pressure, use_sun_radius in param_sets:
                sunrise, sunset, dip, pressure = compute_sun_times(
                    target_ymd, lat, lon, h,
                    use_refraction=use_refraction,
                    use_pressure=use_pressure,
                    use_sun_radius=use_sun_radius,
                    refraction_factor=REFRACTION_FACTOR,
                    flag_print=False
                )

                sunrise_dict[(use_refraction, use_pressure, use_sun_radius)].append(sunrise)
                sunset_dict[(use_refraction, use_pressure, use_sun_radius)].append(sunset)

        # ③ グラフ描画（デバッグ点付き）
        plot_sunrise_sunset(
            graph_heights,
            sunrise_dict,
            sunset_dict,
            debug_heights=dbg_heights if dbg == "Y" else None,
            debug_sunrise=dbg_sunrise if dbg == "Y" else None,
            debug_sunset=dbg_sunset if dbg == "Y" else None,
            target_ymd=target_ymd,
            lat=lat,
            lon=lon
        )

    else:
        # ------------------------------------------------------------
        # ② 数値が入力された場合 → その値を使う
        # ------------------------------------------------------------
        # チェックする標高のリスト
        heights = [0, height]

        # 各フラグの組み合わせ
        refraction_options = [False, True]
        pressure_options = [False, True]
        sun_radius_options = [False, True]

        for h in heights:
            for use_refraction in refraction_options:
                for use_pressure in pressure_options:
                    for use_sun_radius in sun_radius_options:

                        sunrise, sunset, dip, pressure = compute_sun_times(
                            target_ymd, lat, lon, h,
                            use_refraction=use_refraction,
                            use_pressure=use_pressure,
                            use_sun_radius=use_sun_radius,
                            refraction_factor=REFRACTION_FACTOR
                        )

    return


if __name__ == "__main__":
    main()
