# 必要なライブラリのインポート
# pandasはデータ操作と分析のための主要なライブラリです。
try:
    import pandas as pd
except ImportError:
    print("エラー: pandasライブラリが見つかりません。")
    print("インストールするには: pip install pandas を実行してください。")
    exit()

import os

def process_data_to_excel(input_csv_path: str, output_excel_path: str, filter_column: str, filter_value: str):
    """
    CSVファイルからデータを読み込み、特定の条件でフィルタリング・集計し、
    その結果を新しいExcelファイルとして出力する関数。

    Args:
        input_csv_path (str): 入力となるCSVファイルのパス。
        output_excel_path (str): 集計結果を出力するExcelファイルのパス。
        filter_column (str): フィルタリングに使用するカラム名。
        filter_value (str): フィルタリングに使用する条件の値。
    """
    print(f"--- 処理開始 ---")
    print(f"入力ファイル: {input_csv_path}")
    print(f"フィルタ条件: {filter_column} == '{filter_value}'")

    try:
        # 1. CSVファイルからデータを読み込む
        print("\n[Step 1/3] CSVファイルの読み込み中...")
        df = pd.read_csv(input_csv_path, encoding='utf-8')
        print(f"データ読み込み成功。総行数: {len(df)}")

        # 2. 特定の条件でデータをフィルタリングする
        print("\n[Step 2/3] データのフィルタリング中...")
        # 指定されたカラムの値がフィルタ条件と一致する行のみを抽出する
        filtered_df = df[df[filter_column] == filter_value]
        print(f"フィルタリング完了。一致した行数: {len(filtered_df)}")

        if filtered_df.empty:
            print("警告: フィルタリング結果が0件でした。集計処理をスキップします。")
            return

        # 3. 集計処理を行う
        print("\n[Step 3/3] データの集計処理中...")
        # フィルタリングされたデータに基づき、指定カラムでグループ化し、合計値を計算する
        aggregation = filtered_df.groupby(filter_column).sum().reset_index()
        aggregation.rename(columns={filter_column: f'Total_{filter_column}'}, inplace=True)
        
        print("集計処理完了。結果の概要:")
        print(aggregation)


        # 4. 集計結果を新しいExcelファイルとして出力する
        print(f"\n[Step 4/4] 結果をExcelファイルとして出力中: {output_excel_path}")
        # 集計結果をExcelファイルとして保存する (index=Falseでインデックスを出力しない)
        aggregation.to_excel(output_excel_path, index=False, sheet_name='Aggregation_Result')
        print("\n========================================")
        print("✅ 処理が正常に完了しました。")
        print(f"結果は {output_excel_path} に保存されました。")
        print("========================================")

    except FileNotFoundError:
        print("\n❌ エラー: 入力ファイルが見つかりません。ファイルパスを確認してください。")
    except KeyError as e:
        print(f"\n❌ エラー: カラム名 '{e}' がCSVファイルに見つかりません。カラム名の設定を確認してください。")
    except pd.errors.EmptyDataError:
        print("\n❌ エラー: CSVファイルが空です。")
    except Exception as e:
        print(f"\n❌ 予期せぬエラーが発生しました: {e}")


# --- 実行部分 ---
if __name__ == "__main__":
    # 【設定】処理対象のファイルパスとパラメータを設定してください
    INPUT_FILE = "sales_data.csv"
    OUTPUT_FILE = "regional_sales_summary.xlsx"
    
    # フィルタリング条件の設定
    COLUMN_TO_FILTER = "Region"
    VALUE_TO_FILTER = "East"

    # --- テスト用のダミーファイル作成 (実行可能にするための準備) ---
    if not os.path.exists(INPUT_FILE):
        print("--- 準備中 ---")
        print(f"テスト用入力ファイル '{INPUT_FILE}' を作成します。")
        dummy_data = {
            'Date': ['2023-01-01', '2023-01-05', '2023-01-10', '2023-02-01', '2023-02-15'],
            'Region': ['East', 'West', 'East', 'West', 'East'],
            'Sales': [100, 150, 200, 120, 250]
        }
        dummy_df = pd.DataFrame(dummy_data)
        dummy_df.to_csv(INPUT_FILE, index=False, encoding='utf-8')
        print(f"'{INPUT_FILE}' の作成が完了しました。")
    
    # 実際のデータ処理関数の実行
    process_data_to_excel(
        input_csv_path=INPUT_FILE,
        output_excel_path=OUTPUT_FILE,
        filter_column=COLUMN_TO_FILTER,
        filter_value=VALUE_TO_FILTER
    )
