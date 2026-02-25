import matplotlib.font_manager as fm


def list_all_matplotlib_fonts():
    """Matplotlibが認識しているすべてのフォント名を出力する"""

    # Matplotlibが読み込んだすべてのフォントファイルをリストとして取得
    all_fonts = fm.fontManager.ttflist

    # フォント名 (name属性) だけを抽出してソート
    font_names = sorted(list(set([f.name for f in all_fonts])))

    print("--- Matplotlibが認識しているすべてのフォント名 ---")

    # 出力が長くなりすぎるのを防ぐため、30個ずつ区切って表示
    count = 0
    for name in font_names:
        print(f"  {name}")
        count += 1
        if count % 30 == 0:
            # 30個表示ごとに区切りを入れる
            print("-" * 20)

    print(f"\n合計 {len(font_names)} 個のフォントを認識しています。")


if __name__ == "__main__":
    list_all_matplotlib_fonts()
