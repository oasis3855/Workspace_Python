"""指定された場所と日付における太陽と月の天球上の軌跡をシミュレーションするスクリプト。

月の軌道計算期間を約1周期分（25時間）に最適化し、軌跡の重複を防ぎつつ
0時時点での連続性を確保したシミュレーションを行います。
"""

from datetime import datetime, timedelta
import ephem
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
from typing import Tuple

# =================================================================
# グローバル設定変数
# =================================================================
TARGET_LATITUDE_DEG = 34.67
TARGET_LONGITUDE_DEG = 135.5
TIMEZONE_OFFSET = 9    # JST

# =================================================================


def get_user_inputs() -> Tuple[float, float, datetime]:
    """緯度・経度および計算開始日をユーザから取得する。"""
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

    date_str = input("計算開始 年月日を入力してください (yyyy/mm/dd): ")
    try:
        simulate_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        print("入力形式が正しくありません。本日を設定します。")
        simulate_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    return lat, lon, simulate_date


def get_az_alt(body, observer, time):
    """指定時刻における方位角と高度を取得する。"""
    observer.date = ephem.Date(time - timedelta(hours=TIMEZONE_OFFSET))
    body.compute(observer)
    return np.degrees(body.az), np.degrees(body.alt)


def calculate_celestial_data(lat: float, lon: float, simulate_date: datetime):
    """軌跡と出没統計を計算。計算期間を25時間に最適化。"""
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)

    sun = ephem.Sun()   # type: ignore
    moon = ephem.Moon()  # type: ignore

    # 1日＋月の遅れ分(約50分)を考慮し、25時間分(150ステップ)計算
    times = [simulate_date + timedelta(minutes=10 * i) for i in range(151)]

    sun_path = [get_az_alt(sun, obs, t) for t in times]
    moon_path = [get_az_alt(moon, obs, t) for t in times]

    def get_body_stats(body, base_d):
        obs.date = ephem.Date(base_d - timedelta(hours=TIMEZONE_OFFSET))
        try:
            stats = {}
            # 基準日における次回のイベントを取得
            events = [("rise_az", obs.next_rising(body)),
                      ("transit_alt", obs.next_transit(body)),
                      ("set_az", obs.next_setting(body))]

            for key, event_t in events:
                obs.date = event_t
                body.compute(obs)
                stats[key] = np.degrees(body.az) if "az" in key else np.degrees(body.alt)
            return stats
        except BaseException:
            return {"rise_az": 0.0, "transit_alt": 0.0, "set_az": 0.0}

    return {
        "sun_path": sun_path, "moon_path": moon_path,
        "sun_stats": get_body_stats(sun, simulate_date),
        "moon_stats": get_body_stats(moon, simulate_date)
    }


def draw_celestial_sphere(data, lat, lon, simulate_date):
    """天球図を描画。高度0以下をプロット対象外とする。"""
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_box_aspect((1, 1, 0.5))

    # 天球ドームの表面
    u, v = np.linspace(0, 2 * np.pi, 100), np.linspace(0, np.pi / 2, 50)
    ax.plot_surface(np.outer(np.cos(u), np.sin(v)), np.outer(np.sin(u), np.sin(v)),
                    np.outer(np.ones(np.size(u)), np.cos(v)), color='skyblue', alpha=0.05)

    # ガイドライン（水平・垂直）
    for alt in range(15, 90, 15):
        r, z = np.cos(np.radians(alt)), np.sin(np.radians(alt))
        theta = np.linspace(0, 2 * np.pi, 100)
        ax.plot(r * np.sin(theta), r * np.cos(theta), z, color='gray', lw=0.8, alpha=0.7)
    for az in range(0, 360, 45):
        phi = np.linspace(0, np.pi / 2, 50)
        ax.plot(np.cos(phi) * np.sin(np.radians(az)), np.cos(phi) * np.cos(np.radians(az)),
                np.sin(phi), color='gray', lw=0.8, alpha=0.7)

    def plot_trajectory(coords, color, label):
        """高度が0以上の部分のみを抽出し、座標変換して描画する。"""
        # np.nanを使用して地平線下のデータによる直線を防ぐ
        px, py, pz = [], [], []
        for az, alt in coords:
            if alt >= 0:
                az_r, alt_r = np.radians(az), np.radians(alt)
                px.append(np.cos(alt_r) * np.sin(az_r))
                py.append(np.cos(alt_r) * np.cos(az_r))
                pz.append(np.sin(alt_r))
            else:
                # 地平線下に潜ったら一旦切断(Noneを挟む)
                px.append(np.nan)
                py.append(np.nan)
                pz.append(np.nan)

        ax.plot(px, py, pz, color=color, lw=3, label=label)

    plot_trajectory(data["sun_path"], 'orange', '太陽')
    plot_trajectory(data["moon_path"], 'navy', '月')

    # 方位ラベルの配置
    dirs = {0: '北', 45: '北東', 90: '東', 135: '南東', 180: '南', 225: '南西', 270: '西', 315: '北西'}
    for ang, txt in dirs.items():
        r = np.radians(ang)
        ax.text(1.2 * np.sin(r), 1.2 * np.cos(r), 0, txt, ha='center', va='center')

    # 情報パネルの表示
    s, m = data["sun_stats"], data["moon_stats"]
    info = (f"【太陽】 {simulate_date.strftime('%Y/%m/%d')}\n"
            f" 出方位:{s['rise_az']:.1f}° / 南中高度:{s['transit_alt']:.1f}° / 没方位:{s['set_az']:.1f}°\n\n"
            f"【月】\n"
            f" 出方位:{m['rise_az']:.1f}° / 南中高度:{m['transit_alt']:.1f}° / 没方位:{m['set_az']:.1f}°")
    ax.text2D(
        0.02,
        0.8,
        info,
        transform=ax.transAxes,
        bbox=dict(
            facecolor='white',
            alpha=0.8,
            edgecolor='gray'))

    ax.set_axis_off()
    ax.set_title(f"天球図 (緯度:{lat}, 経度:{lon})")
    ax.legend(loc='upper right')
    plt.show()


def main():
    """メインエントリポイント。"""
    lat, lon, sim_date = get_user_inputs()
    data = calculate_celestial_data(lat, lon, sim_date)
    draw_celestial_sphere(data, lat, lon, sim_date)


if __name__ == "__main__":
    main()
