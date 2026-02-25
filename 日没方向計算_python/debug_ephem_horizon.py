
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日の出時刻の計算法による検証

国立天文台 https://eco.mtk.nao.ac.jp/cgi-bin/koyomi/koyomix.cgi
    2026/01/01  SUNRISE 07:05, SUNSET 16:58
    2026/06/01  SUNRISE 04:46, SUNSET 19:06
    2026/01/01  SUNRISE 06:59, SUNSET 17:04 (h=1000m)
    2026/06/01  SUNRISE 04:40, SUNSET 19:12 (h=1000m)
    2026/01/01  SUNRISE 06:54, SUNSET 17:09 (h=3000m)
    2026/06/01  SUNRISE 04:35, SUNSET 19:16 (h=3000m)

NOAA(標高0mのみ)https://gml.noaa.gov/grad/solcalc/sunrise.html   https://gml.noaa.gov/grad/solcalc/
    2026/01/01  SUNRISE 07:05, SUNSET 16:58
    2026/06/01  SUNRISE 04:46, SUNSET 19:06
Canada(標高0mのみ) https://nrc.canada.ca/en/research-development/products-services/software-applications/sun-calculator/
    2026/01/01  SUNRISE 07:05, SUNSET 16:58
    2026/06/01  SUNRISE 04:46, SUNSET 19:06

"""

from datetime import datetime, timedelta
import ephem
import math

TARGET_YMD = "2025/06/01"
LATITUDE_DEG = 34.67
LONGITUDE_DEG = 135.50
HEIGHT = 3000.0
local_pressure = 1013.25 * (1 - 0.0065 * HEIGHT / 288.15)**5.257

DIP_COEFF_GEOMETRIC = 0.03211
DIP_COEFF_STANDARD = 0.02953
DIP_COEFF_EXTENDED = 0.0353

SUN_VISUAL_ANGLE = 0.533    # 32'  太陽の視直径


jst_offset = timedelta(hours=9)

obs = ephem.Observer()
obs.date = datetime.strptime(TARGET_YMD, "%Y/%m/%d") - jst_offset
obs.lat = str(LATITUDE_DEG)
obs.lon = str(LONGITUDE_DEG)
obs.elevation = float(HEIGHT)

sun = ephem.Sun()  # type: ignore[reportAttributeAccessIssue]

print("--- 地表面・真空 ---")
obs.pressure = 0
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

print("--- 地表面・1気圧 ---")
obs.pressure = 1013.25
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")


print(f"--- 標高h={HEIGHT}m・（幾何学的効果のみ θ={DIP_COEFF_GEOMETRIC} sqrt(h)） ---")
h_sqrt = math.sqrt(HEIGHT)
dip = DIP_COEFF_GEOMETRIC * h_sqrt

obs.pressure = 0
obs.horizon = str(-dip)
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

print(f"--- 標高h={HEIGHT}m・（幾何学的効果 θ={DIP_COEFF_GEOMETRIC} sqrt(h) + 太陽視直径{SUN_VISUAL_ANGLE}°） ---")
obs.pressure = 0.0
dip = DIP_COEFF_GEOMETRIC * h_sqrt + SUN_VISUAL_ANGLE
obs.horizon = str(-dip)
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")


print(f"--- 標高h={HEIGHT}m・（単純空気屈折のみ θ={DIP_COEFF_STANDARD} sqrt(h)） ---")
dip = DIP_COEFF_STANDARD * h_sqrt
obs.horizon = str(-dip)
obs.pressure = 0
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")


print(f"--- 標高h={HEIGHT}m・（単純空気屈折のみ θ={DIP_COEFF_STANDARD} sqrt(h)） + 太陽視直径{SUN_VISUAL_ANGLE}°） ---")
dip = DIP_COEFF_STANDARD * h_sqrt + SUN_VISUAL_ANGLE
obs.horizon = str(-dip)
obs.pressure = 0.0
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

print(f"--- 標高h={HEIGHT}m・（空気屈折・地平延長効果 θ={DIP_COEFF_EXTENDED} sqrt(h)） ---")
dip = DIP_COEFF_EXTENDED * h_sqrt
obs.pressure = 0.0
obs.horizon = str(-dip)
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

print(f"--- 標高h={HEIGHT}m・（空気屈折・地平延長効果 θ={DIP_COEFF_EXTENDED} sqrt(h)） + 太陽視直径{SUN_VISUAL_ANGLE}°） ---")
dip = DIP_COEFF_EXTENDED * h_sqrt + SUN_VISUAL_ANGLE
obs.pressure = 0.0
obs.horizon = str(-dip)
rise = obs.next_rising(sun)
set = obs.next_setting(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")
print(f"日入: {set.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")

obs.pressure = local_pressure
rise = obs.next_rising(sun)
print(f"日出: {rise.datetime() + jst_offset}, 気圧: {obs.pressure}, 仰角: {math.degrees(obs.horizon)}")
