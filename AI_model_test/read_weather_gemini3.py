# Gemini3で作成

import csv
from pathlib import Path
from typing import List, Tuple
import matplotlib.pyplot as plt


def load_weather_data(file_path: Path) -> Tuple[List[str], List[float], List[float], List[float]]:
    """weather_data.csvから気象データを読み込む

    Args:
        file_path (Path): 読み込むCSVファイルのパス

    Returns:
        Tuple[List[str], List[float], List[float], List[float]]:
            (日付のリスト, 最高気温のリスト, 最低気温のリスト, 降水量のリスト)
    """
    dates: List[str] = []
    max_temps: List[float] = []
    min_temps: List[float] = []
    precipitations: List[float] = []

    with open(file_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.append(row["date"])
            max_temps.append(float(row["temp-max"]))
            min_temps.append(float(row["temp-min"]))
            precipitations.append(float(row["precip"]))

    return dates, max_temps, min_temps, precipitations


def plot_weather_data(
    dates: List[str],
    max_temps: List[float],
    min_temps: List[float],
    precipitations: List[float],
) -> None:
    """気象データ（気温と降水量）のグラフを描画する

    最高気温を赤線、最低気温を青線、降水量を水色の棒グラフでプロットする。
    降水量と気温は単位が異なるため、左右のY軸を分けて表示する。

    Args:
        dates (List[str]): 日付のリスト
        max_temps (List[float]): 最高気温のリスト
        min_temps (List[float]): 最低気温のリスト
        precipitations (List[float]): 降水量のリスト

    Returns:
        None
    """
    # 日本語フォントの設定（文字化け防止）
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Meiryo",
        "Yu Gothic",
        "Hiragino Sans",
        "Arial",
    ]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # 左側のY軸：気温（最高気温・最低気温）
    ax1.plot(dates, max_temps, color="red", label="最高気温 (℃)", marker="o")
    ax1.plot(dates, min_temps, color="blue", label="最低気温 (℃)", marker="o")
    ax1.set_xlabel("日付")
    ax1.set_ylabel("気温 (℃)")
    ax1.grid(True, linestyle="--", alpha=0.6)

    # 右側のY軸：降水量（棒グラフ）
    ax2 = ax1.twinx()
    ax2.bar(
        dates,
        precipitations,
        color="deepskyblue",
        alpha=0.4,
        label="降水量 (mm)",
    )
    ax2.set_ylabel("降水量 (mm)")
    ax2.grid(False)  # 棒グラフのグリッドは非表示にするか、重ね合わせる

    # 凡例を一つにまとめる
    handler1, label1 = ax1.get_legend_handles_labels()
    handler2, label2 = ax2.get_legend_handles_labels()
    ax1.legend(handler1 + handler2, label1 + label2, loc="upper left")

    plt.title("日別気象データ推移", fontsize=14)
    fig.tight_layout()

    # グラフの表示
    plt.show()


def main() -> None:
    """メイン処理"""
    # スクリプトと同一ディレクトリのCSVファイルパスを指定
    script_dir = Path(__file__).resolve().parent
    csv_file = script_dir / "weather_data.csv"

    if not csv_file.exists():
        print(f"エラー: {csv_file} が見つかりません。")
        return

    # データの読み込み
    dates, max_temps, min_temps, precips = load_weather_data(csv_file)

    # グラフの描画
    plot_weather_data(dates, max_temps, min_temps, precips)


if __name__ == "__main__":
    main()