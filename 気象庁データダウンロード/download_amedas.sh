#!/bin/bash

# https://www.jma.go.jp/bosai/amedas/data/point/{station}/{yyyymmdd}_{h3}.json
# {station}は気象庁Webでアメダス地点データを表示したときのURLパラメータamdno
# {h3}は3時間毎の数値で00,03,06,09,12,15,18,21
# 3時間分の10分ごとデータがダウンロードされる
curl -s https://www.jma.go.jp/bosai/amedas/data/point/62078/20250405_18.json