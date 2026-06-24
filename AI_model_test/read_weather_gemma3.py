# Gemma3.e2bで作成

import os

import pandas as pd
import matplotlib.pyplot as plt
from typing import Tuple

def load_weather_data(file_path: str) -> pd.DataFrame:
    """
    指定されたCSVファイルから気象データを読み込み、Pandas DataFrameとして返します。

    Args:
        file_path (str): 読み込むCSVファイルのパス。
            このスクリプトでは、同一ディレクトリ内の 'weather_data.csv' を想定します。

    Returns:
        pd.DataFrame: 読み込まれた気象データを含むDataFrame。

    Raises:
        FileNotFoundError: 指定されたファイルが見つからない場合。
        Exception: ファイル読み込み中に予期せぬエラーが発生した場合。
    """
    try:
        data_frame = pd.read_csv(file_path)
        return data_frame
    except FileNotFoundError:
        raise FileNotFoundError(f"エラー: ファイルが見つかりません。パスを確認してください: {file_path}")
    except Exception as e:
        raise Exception(f"データ読み込み中にエラーが発生しました: {e}")

def plot_weather_data(data: pd.DataFrame, output_filename: str = "weather_plot.png") -> None:
    """
    気象データを基に、最高気温、最低気温、降水量をグラフとして描画します。

    最高気温と最低気温は折れ線グラフで、降水量は棒グラフで表現されます。

    Args:
        data (pd.DataFrame): グラフ化する気象データを含むDataFrame。
                                   カラムには 'date', 'temp-max', 'temp-min', 'precip' が必要。
        output_filename (str): グラフを保存するファイル名。デフォルトは "weather_plot.png"。

    Returns:
        None: グラフはファイルに直接保存されます。

    Raises:
        KeyError: 必要なカラム（'date', 'temp-max', 'temp-min', 'precip'）がDataFrameに存在しない場合。
    """
    required_columns = ['date', 'temp-max', 'temp-min', 'precip']
    if not all(col in data.columns for col in required_columns):
        raise KeyError(f"DataFrameに以下の必須カラムが含まれていません: {required_columns}")

    # グラフの描画設定
    plt.figure(figsize=(12, 6))

    # 1. 最高気温 (赤線) のプロット
    plt.plot(data['date'], data['temp-max'], label='最高気温 (Max Temp)', color='red', marker='o', linestyle='-')

    # 2. 最低気温 (青線) のプロット
    plt.plot(data['date'], data['temp-min'], label='最低気温 (Min Temp)', color='blue', marker='o', linestyle='-')

    # 3. 降水量 (水色棒) のプロット
    plt.bar(data['date'], data['precip'], label='降水量 (Precip)', color='skyblue')

    # グラフの装飾
    plt.title('日ごとの気温と降水量の推移', fontsize=16)
    plt.xlabel('日付 (Date)', fontsize=12)
    plt.ylabel('値', fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45, ha='right')  # 日付ラベルが見やすいように回転
    plt.tight_layout()

    # グラフの保存
    plt.savefig(output_filename)
    print(f"\n✅ グラフが正常に生成され、'{output_filename}'として保存されました。")
    print("--------------------------------------------------")


def main() -> None:
    """
    メイン実行関数。データの読み込みとグラフ描画を実行します。
    """
    CSV_FILE = "weather_data.csv"

    print(f"--- ステップ 1: データ読み込み ({CSV_FILE}) ---")
    try:
        # 0. CSV_FILEのフルパスを作成 (ファイルはスクリプトと同一ディレクトリ)
        CSV_FILE = os.path.join(os.getcwd(), CSV_FILE)
        # 1. データの読み込み
        data_df = load_weather_data(CSV_FILE)
        print("✅ データ読み込み完了。")
        print("\n--- 読み込んだデータ (先頭5行) ---")
        print(data_df.head())

        print("\n--- ステップ 2: グラフ描画 ---")
        # 2. グラフの描画
        plot_weather_data(data_df)

    except (FileNotFoundError, KeyError, Exception) as e:
        print(f"\n❌ 処理中に致命的なエラーが発生しました: {e}")

if __name__ == "__main__":
    main()