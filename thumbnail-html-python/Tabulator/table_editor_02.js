/**
 * @file table_editor.js
 * @description 画像管理HTMLファイル内でTabulatorを呼び出し、テーブルの編集およびHTML保存を行うスクリプト
 */

// Tabulator の CSS / JS を動的に読み込む関数
(function load_tabulator_assets() {
  const css_link = document.createElement("link");
  css_link.rel = "stylesheet";
  css_link.href = "https://unpkg.com/tabulator-tables@5.5.0/dist/css/tabulator.min.css";
  document.head.appendChild(css_link);

  const js_script = document.createElement("script");
  js_script.src = "https://unpkg.com/tabulator-tables@5.5.0/dist/js/tabulator.min.js";
  document.head.appendChild(js_script);

  // カスタムスタイルの注入（編集済みセルの強調表示＆Tabulator内での改行表示許可）
  const custom_style = document.createElement("style");
  custom_style.textContent = `
    .tabulator-cell.edited-cell-highlight {
      background-color: #ffcccc !important;
    }
    .tabulator-cell img {
      max-width: 100%;
      height: auto;
      object-fit: contain;
    }
    /* textareaフォーマッタ・エディタ表示時の改行を正常に反映させる設定 */
    .tabulator-cell {
      white-space: pre-wrap !important;
    }
  `;
  document.head.appendChild(custom_style);
})();

let global_tabulator_instance = null;
let original_headers = [];

/**
 * 現在表示中の HTML DOM から <table> データを解析・取得する関数
 *
 * @returns {{ custom_headers: Array<string>, table_body_data: Array<Array<string>> }}
 */
function parse_current_dom_table() {
  const target_table = document.querySelector("table");
  if (!target_table) {
    return { custom_headers: [], table_body_data: [] };
  }

  const table_rows = target_table.querySelectorAll("tr");
  const custom_headers = [];
  const table_body_data = [];

  table_rows.forEach((row_element, row_index) => {
    const header_elements = row_element.querySelectorAll("th");
    const cell_elements = row_element.querySelectorAll("td");

    if (row_index === 0 && header_elements.length > 0) {
      header_elements.forEach((header_element) => {
        custom_headers.push(header_element.textContent.trim());
      });
    } else if (cell_elements.length > 0) {
      const row_data = [];
      cell_elements.forEach((cell_element) => {
        // img タグが含まれる場合は innerHTML をそのまま維持
        if (cell_element.querySelector("img")) {
          row_data.push(cell_element.innerHTML.trim());
        } else {
          // <br> や <br/> タグを改行コード (\n) に置換してからプレーンテキストを取得
          let html_content = cell_element.innerHTML;
          html_content = html_content.replace(/<br\s*[\/]?>/gi, "\n");
          
          // 一時的な DOM 要素を作成して HTML エンテティ等をデコード
          const temp_div = document.createElement("div");
          temp_div.innerHTML = html_content;
          row_data.push(temp_div.textContent.trim());
        }
      });
      table_body_data.push(row_data);
    }
  });

  return { custom_headers, table_body_data };
}

/**
 * 編集モード（Tabulator 表示）を起動する関数
 *
 * @returns {void}
 */
function switch_to_edit_mode() {
  const parsed_result = parse_current_dom_table();
  if (parsed_result.table_body_data.length === 0) {
    alert("編集可能なテーブル要素が見つかりませんでした。");
    return;
  }

  original_headers = parsed_result.custom_headers;
  const table_body_data = parsed_result.table_body_data;

  // カラム設定の構築
  const column_definitions = [];
  const read_only_columns = ["画像ディレクトリ名", "ファイル名（拡張子抜き）", "サムネイル画像", "撮影日時"];

  original_headers.forEach((header_title, column_index) => {
    const is_read_only = read_only_columns.includes(header_title);
    const is_image_column = header_title === "サムネイル画像";

    let column_width = undefined;
    if (header_title === "画像ディレクトリ名" || header_title === "ファイル名（拡張子抜き）") {
      column_width = 110;
    } else if (header_title === "撮影地") {
      column_width = 150;
    } else if (header_title === "flag") {
      column_width = 70;
    }

    column_definitions.push({
      title: header_title,
      field: "col_" + column_index,
      width: column_width,
      // 画像は html、その他は改行に対応する textarea を使用
      formatter: is_image_column ? "html" : "textarea",
      // 編集可能カラムには 複数行編集に対応した textarea エディタを設定
      editor: is_read_only ? false : "textarea",
      headerSort: false
    });
  });

  // データ構造の変換
  const formatted_table_data = table_body_data.map((data_row) => {
    const row_object = {};
    data_row.forEach((cell_value, column_index) => {
      row_object["col_" + column_index] = cell_value;
    });
    return row_object;
  });

  // 操作ボタン群の切り替え表示
  document.getElementById("editor_controls").style.display = "block";
  document.getElementById("start_edit_button").style.display = "none";

  // 既存の HTML テーブルを隠し、Tabulator 用のコンテナを表示
  const original_table = document.querySelector("table");
  if (original_table) {
    original_table.style.display = "none";
  }

  // Tabulator インスタンス生成
  global_tabulator_instance = new Tabulator("#editor_container", {
    data: formatted_table_data,
    columns: column_definitions,
    layout: "fitColumns"
  });

  // 編集済みセルの背景色変更イベント
  global_tabulator_instance.on("cellEdited", function (edited_cell) {
    if (edited_cell.getValue() !== edited_cell.getOldValue()) {
      edited_cell.getElement().classList.add("edited-cell-highlight");
    }
  });
}

/**
 * Tabulatorの編集結果を基に新しい HTML ドキュメントを生成し、ファイルとしてダウンロード保存する関数
 *
 * @returns {void}
 */
async function save_and_download_html() {
  if (!global_tabulator_instance) {
    return;
  }

  const table_data = global_tabulator_instance.getData();

  // HTML文字列の組み立て
  let new_html_content = `<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>サムネイル一覧</title>
  <style>
    body { font-size: 14px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    img { display: block; height: auto; }
  </style>
  <script src="table_editor.js" defer></script>
</head>
<body>
  <div style="margin-bottom: 15px;">
    <button id="start_edit_button" onclick="switch_to_edit_mode()">編集</button>
    <div id="editor_controls" style="display: none;">
      <button onclick="save_and_download_html()">保存 (HTML更新)</button>
    </div>
  </div>
  <div id="editor_container"></div>
  <table>
    <tr>\n`;

  // ヘッダー行 (th) の生成
  original_headers.forEach((header_title) => {
    new_html_content += `      <th>${header_title}</th>\n`;
  });
  new_html_content += `    </tr>\n`;

  // データ行 (td) の生成
  table_data.forEach((row_object) => {
    new_html_content += `    <tr>\n`;
    original_headers.forEach((header_title, column_index) => {
      let cell_value = row_object["col_" + column_index] || "";
      
      // 画像カラム以外は、テキスト中の改行コード (\n) を <br/> タグに戻す
      if (header_title !== "サムネイル画像") {
        cell_value = cell_value.replace(/\r?\n/g, "<br/>");
      }
      
      new_html_content += `      <td>${cell_value}</td>\n`;
    });
    new_html_content += `    </tr>\n`;
  });

  new_html_content += `  </table>
</body>
</html>`;

  // Blob を生成してダウンロードダイアログを起動
  const blob = new Blob([new_html_content], { type: "text/html;charset=utf-8;" });
  const download_link = document.createElement("a");
  const current_filename = location.pathname.split("/").pop() || "list.html";

  download_link.href = URL.createObjectURL(blob);
  download_link.download = current_filename;
  document.body.appendChild(download_link);
  download_link.click();
  document.body.removeChild(download_link);
}