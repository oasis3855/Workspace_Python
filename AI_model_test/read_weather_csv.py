#!/bin/env python3

import os

import requests

# スクリプトファイルの絶対パスを取得する
script_path = os.path.abspath(__file__)
base_dir = os.path.dirname(script_path)
# このスクリプトと同一ディレクトリのCSVファイルのフルパス名
csv_filename = os.path.join(base_dir, 'weather_data.csv')

# 気象データCSVファイルを読み込み、リストに格納して返す関数
def read_csv(filename:str) ->list[str]:
    with open(filename, 'r') as f:
        lines = f.readlines()
        data_list = []
        for line in lines:
            data_list.append(line.strip().split(','))
        return data_list

# 与えられたURLからCSVファイルを読み込み、データをリストに格納して返す関数


#def calculate_average(data_list: list[list[str]]) -> float:


def sort_list(data_list: list[list[str]]) -> list[str]:
    """
    与えられたデータリストの最初の要素を抽出し、その要素を昇順にソートして返す。

    Args:
        data_list (list[list[str]]): 処理対象のデータリスト。各要素は行を表すリストであり、最初の要素がソート対象。

    Returns:
        list[str]: 最初の列の要素が昇順にソートされたリスト。
    """
    # データリストから各行の最初の要素（列0）を抽出する
    first_elements = [row[0] for row in data_list]
    # 抽出した要素のリストを昇順にソートする
    first_elements.sort()

    # ソートされた結果を返す
    return first_elements


def main()->None:
    # CSVファイルの読み込みとデータ整形
    data_list = read_csv(csv_filename)
    # リストの全行を画面出力する
    for row in data_list: 
        print(row)




if __name__ == "__main__":
    main()


