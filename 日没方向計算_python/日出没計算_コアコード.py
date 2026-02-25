#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""指定された緯度・経度・標高に基づき日出・日没時刻を検証するスクリプト。

スクリプト単純実装のテスト用

"""
from datetime import datetime, timedelta
import math
import ephem

target_ymd = "2025/1/1"
R = 6371000.0           # 地球半径 [m]
lat_deg = 34.67         # 緯度
lon_deg = 135.50        # 経度
height_m = 3000         # 標高
refraction_factor = 1.4902      # dip_ref = refraction_factor * dip_geom


def calc_dipgeom_ephemrefraction() -> None:

    pressure_0m = 1013.25   # 標高 0mの気圧 [hPa]
    pressure = pressure_0m * (1 - 2.25577e-5 * height_m) ** 5.2559
    temperature_0m = 15.0   # 標高 0mの気温 [℃]
    temperature = temperature_0m - 0.6 * height_m / 100

    jst_offset = timedelta(hours=9)     # JST → UTC

    # 光学伏角（真空中）
    dip_geom = math.sqrt(2 * height_m / R) * 180.0 / math.pi

    obs = ephem.Observer()
    obs.date = datetime.strptime(target_ymd, "%Y/%m/%d") - jst_offset
    obs.lat = str(lat_deg)
    obs.lon = str(lon_deg)
    obs.elevation = float(height_m)
    obs.pressure = pressure
    obs.temperature = temperature
    obs.horizon = f"-{dip_geom}"

    sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

    # 日の出・日の入り（UTC → JST）
    sunrise = obs.next_rising(sun).datetime() + jst_offset
    sunset = obs.next_setting(sun).datetime() + jst_offset

    print(f"日の出 : {sunrise.strftime('%H:%M:%S')}\n"
          f"日の入 : {sunset.strftime('%H:%M:%S')}\n"
          f"標高 : {height_m} m\n"
          f"補正気圧 : {pressure:5.1f} hPa\n"
          f"補正気温 : {temperature:3.1f} 度\n"
          f"伏角 : {dip_geom:4.3f} °")


def calc_dipref() -> None:

    pressure = 0.0          # Ephemでの空気屈折計算を無効化
    # temperature = 11.0      # Ephemのデフォルト値

    jst_offset = timedelta(hours=9)     # JST → UTC

    # 光学伏角（真空中）
    dip_geom = math.sqrt(2 * height_m / R) * 180.0 / math.pi
    # 実効伏角
    dip_ref = refraction_factor * dip_geom

    obs = ephem.Observer()
    obs.date = datetime.strptime(target_ymd, "%Y/%m/%d") - jst_offset
    obs.lat = str(lat_deg)
    obs.lon = str(lon_deg)
    obs.elevation = float(height_m)
    obs.pressure = pressure
    obs.horizon = f"-{dip_ref}"

    sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

    # 日の出・日の入り（UTC → JST）
    sunrise = obs.next_rising(sun).datetime() + jst_offset
    sunset = obs.next_setting(sun).datetime() + jst_offset

    print(f"日の出 : {sunrise.strftime('%H:%M:%S')}\n"
          f"日の入 : {sunset.strftime('%H:%M:%S')}\n"
          f"標高 : {height_m} m\n"
          f"補正気圧 : {obs.pressure:5.1f} hPa\n"
          f"補正気温 : {obs.temperature:3.1f} 度\n"
          f"伏角 : {dip_ref:4.3f} °")


print("=== 光学伏角 + Ephem空気屈折補正 ===")
calc_dipgeom_ephemrefraction()
print("=== 空気屈折伏角 ===")
calc_dipref()
