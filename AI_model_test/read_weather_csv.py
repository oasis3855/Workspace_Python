#!/bin/env python3

import os

# スクリプトファイルの絶対パスを取得する
script_path = os.path.abspath(__file__)
base_dir = os.path.dirname(script_path)
# このスクリプトと同一ディレクトリのCSVファイルのフルパス名
csv_filename = os.path.join(base_dir, 'weather_data.csv')

# 気象データCSVファイルを読み込み、リストに格納して返す関数
def read_csv(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
        data_list = []
        for line in lines:
            data_list.append(line.strip().split(','))
        return data_list

# tkinterのウインドウに、気象データのグラフを描画する関数

import tkinter as tk


def main()->None:
    # CSVファイルの読み込みとデータ整形
    data_list = read_csv(csv_filename)
    # リストの全行を画面出力する
    for row in data_list: 
        print(row)




if __name__ == "__main__":
    main()

