import csv
from collections import defaultdict
import pandas as pd
import numpy as np

input_file_path = "./qwen25-coder1.5_data.csv"

def filter_and_aggregate_data_from_csv(input_file_path):
    """
    1. CSVファイルからデータを読み込み、特定の条件でデータをフィルタリング・集計する。
    2. 集計結果を新しいExcelファイルとして出力する。

    Parameters:
        input_file_path (str): クロス引用表のパス

    Returns:
        None
    """

    # 準備：CSVファイルからデータを読み込む
    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            data_list = [row for row in reader]
    except FileNotFoundError:
        print(f"エラー: CSV ファイル {input_file_path} が見つかりません。")
        return

# 準備：データをフィルタリング・集計するための関数
def filter_and_aggregate_data(data_list):
    result = defaultdict(lambda: {"count": 0, "total_age": 0})
    
    for row in data_list:
        # 特定の条件でデータをフィルタリング・集計
        if int(row["age"]) >= 25 and row["gender"] == "Male":
            result[row["name"]] = {"count": 1, "total_age": int(row["age"])}
    
    return dict(result)

# 準備：集計結果を新しいExcelファイルとして出力する関数
def save_aggregated_data_to_excel(aggregated_data):
    df = pd.DataFrame(list(aggregated_data.values()))
    df.to_excel("aggregated_data.xlsx", index=False)
    
    print("集計結果を新しいExcelファイルとして保存しました。")

# 準備：実行する関数
def main():
    # CSVファイルからデータを読み込み、特定の条件でデータをフィルタリング・集計する
    aggregated_data = filter_and_aggregate_data(data_list)
    
    # 集計結果を新しいExcelファイルとして出力する
    save_aggregated_data_to_excel(aggregated_data)

if __name__ == "__main__":
    main()
