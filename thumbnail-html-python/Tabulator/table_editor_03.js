/**
 * @file tableEditor.js
 * @description 画像管理HTMLファイル内でTabulatorを呼び出し、テーブルの編集およびHTML保存を行うスクリプト
 * @author Google Gemini 3.6 Flash Collaborating Coding
 * @version 1.0.0 (2026/09/05)
 */

// Tabulator の CSS / JS を動的に読み込む関数
(function loadTabulatorAssets() {
  // ── [ステップ1] スタイルシート (CSS) の読み込み ──
  const cssLink = document.createElement("link");
  cssLink.rel = "stylesheet";
  cssLink.href = "https://unpkg.com/tabulator-tables@5.5.0/dist/css/tabulator.min.css";
  document.head.appendChild(cssLink);

  // ── [ステップ2] スクリプト (JS) の読み込み ──
  const jsScript = document.createElement("script");
  jsScript.src = "https://unpkg.com/tabulator-tables@5.5.0/dist/js/tabulator.min.js";
  document.head.appendChild(jsScript);

  // ── [ステップ3] カスタムスタイルの注入 ──
  // 編集済みセルの強調表示およびTabulator内での改行表示許可
  const customStyle = document.createElement("style");
  customStyle.textContent = `
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
  document.head.appendChild(customStyle);
})();

// グローバル変数の定義（camelCase）
let globalTabulatorInstance = null;
let originalHeaders = [];

/**
 * 現在表示中の HTML DOM から <table> データを解析・取得する。
 *
 * @returns {{ customHeaders: Array<string>, tableBodyData: Array<Array<string>> }} 解析されたヘッダー配列とテーブルボディデータのオブジェクト
 */
function parseCurrentDomTable() {
  // ── [ステップ1] 対象テーブル要素の取得と存在確認 ──
  const targetTable = document.querySelector("table");
  if (!targetTable) {
    return { customHeaders: [], tableBodyData: [] };
  }

  const tableRows = targetTable.querySelectorAll("tr");
  const customHeaders = [];
  const tableBodyData = [];

  // ── [ステップ2] 行データのループ処理とデータ抽出 ──
  tableRows.forEach((rowElement, rowIndex) => {
    const headerElements = rowElement.querySelectorAll("th");
    const cellElements = rowElement.querySelectorAll("td");

    // ヘッダー行 (th) の解析
    if (rowIndex === 0 && headerElements.length > 0) {
      headerElements.forEach((headerElement) => {
        customHeaders.push(headerElement.textContent.trim());
      });
    } 
    // データ行 (td) の解析
    else if (cellElements.length > 0) {
      const rowData = [];
      cellElements.forEach((cellElement) => {
        // img タグが含まれる場合は innerHTML をそのまま維持
        if (cellElement.querySelector("img")) {
          rowData.push(cellElement.innerHTML.trim());
        } else {
          // <br> や <br/> タグを改行コード (\n) に置換してからプレーンテキストを取得
          let htmlContent = cellElement.innerHTML;
          htmlContent = htmlContent.replace(/<br\s*[\/]?>/gi, "\n");
          
          // 一時的な DOM 要素を作成して HTML エンテティ等をデコード
          const tempDiv = document.createElement("div");
          tempDiv.innerHTML = htmlContent;
          rowData.push(tempDiv.textContent.trim());
        }
      });
      tableBodyData.push(rowData);
    }
  });

  return { customHeaders, tableBodyData };
}

/**
 * 編集モード（Tabulator 表示）を起動する。
 *
 * @returns {void}
 */
function switchToEditMode() {
  // ── [ステップ1] DOM テーブルの解析結果の取得 ──
  const parsedResult = parseCurrentDomTable();
  if (parsedResult.tableBodyData.length === 0) {
    alert("編集可能なテーブル要素が見つかりませんでした。");
    return;
  }

  originalHeaders = parsedResult.customHeaders;
  const tableBodyData = parsedResult.tableBodyData;

  // ── [ステップ2] Tabulator用カラム定義の構築 ──
  const columnDefinitions = [];
  const readOnlyColumns = ["画像ディレクトリ名", "ファイル名（拡張子抜き）", "サムネイル画像", "撮影日時"];

  originalHeaders.forEach((headerTitle, columnIndex) => {
    const isReadOnly = readOnlyColumns.includes(headerTitle);
    const isImageColumn = headerTitle === "サムネイル画像";

    let columnWidth = undefined;
    if (headerTitle === "画像ディレクトリ名" || headerTitle === "ファイル名（拡張子抜き）") {
      columnWidth = 110;
    } else if (headerTitle === "撮影地") {
      columnWidth = 150;
    } else if (headerTitle === "flag") {
      columnWidth = 70;
    }

    columnDefinitions.push({
      title: headerTitle,
      field: "col_" + columnIndex,
      width: columnWidth,
      // 画像は html、その他は改行に対応する textarea フォーマッタを使用
      formatter: isImageColumn ? "html" : "textarea",
      // 編集可能カラムには複数行編集に対応した textarea エディタを設定
      editor: isReadOnly ? false : "textarea",
      // textarea エディタで、Shift+Enter押下を確定(コミット)キーとする
      editorParams: isReadOnly ? {} : {
        shiftEnterSubmit: true,
      },
      headerSort: false
    });
  });

  // ── [ステップ3] データ構造の変換 ──
  const formattedTableData = tableBodyData.map((dataRow) => {
    const rowObject = {};
    dataRow.forEach((cellValue, columnIndex) => {
      rowObject["col_" + columnIndex] = cellValue;
    });
    return rowObject;
  });

  // ── [ステップ4] 操作UI（ボタン・表示領域）の切り替え ──
  document.getElementById("editor_controls").style.display = "block";
  document.getElementById("start_edit_button").style.display = "none";

  // 既存の HTML テーブルを隠し、Tabulator 用のコンテナを表示
  const originalTable = document.querySelector("table");
  if (originalTable) {
    originalTable.style.display = "none";
  }

  // ── [ステップ5] Tabulator インスタンスの生成とイベント登録 ──
  globalTabulatorInstance = new Tabulator("#editor_container", {
    data: formattedTableData,
    columns: columnDefinitions,
    layout: "fitColumns"
  });

  // 編集済みセルの背景色変更イベントの登録
  globalTabulatorInstance.on("cellEdited", function (editedCell) {
    if (editedCell.getValue() !== editedCell.getOldValue()) {
      editedCell.getElement().classList.add("edited-cell-highlight");
    }
  });
}

/**
 * Tabulatorの編集結果を基に新しい HTML ドキュメントを生成し、ファイルとしてダウンロード保存する。
 *
 * @returns {Promise<void>}
 */
async function saveAndDownloadHtml() {
  if (!globalTabulatorInstance) {
    return;
  }

  // ── [ステップ1] 編集後のテーブルデータの取得 ──
  const tableData = globalTabulatorInstance.getData();

  // ── [ステップ2] 新しい HTML 文字列の構築（ヘッダー部） ──
  let newHtmlContent = `<!DOCTYPE html>
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
    <button id="start_edit_button" onclick="switchToEditMode()">編集</button>
    <div id="editor_controls" style="display: none;">
      <button onclick="saveAndDownloadHtml()">保存 (HTML更新)</button>
    </div>
  </div>
  <div id="editor_container"></div>
  <table>
    <tr>\n`;

  // ヘッダー行 (th) の生成
  originalHeaders.forEach((headerTitle) => {
    newHtmlContent += `      <th>${headerTitle}</th>\n`;
  });
  newHtmlContent += `    </tr>\n`;

  // ── [ステップ3] 新しい HTML 文字列の構築（データ行部） ──
  tableData.forEach((rowObject) => {
    newHtmlContent += `    <tr>\n`;
    originalHeaders.forEach((headerTitle, columnIndex) => {
      let cellValue = rowObject["col_" + columnIndex] || "";
      
      // 画像カラム以外は、テキスト中の改行コード (\n) を <br/> タグに戻す
      if (headerTitle !== "サムネイル画像") {
        cellValue = cellValue.replace(/\r?\n/g, "<br/>");
      }
      
      newHtmlContent += `      <td>${cellValue}</td>\n`;
    });
    newHtmlContent += `    </tr>\n`;
  });

  newHtmlContent += `  </table>
</body>
</html>`;

  // ── [ステップ4] Blobの生成とファイルダウンロード処理 ──
  const blob = new Blob([newHtmlContent], { type: "text/html;charset=utf-8;" });
  const downloadLink = document.createElement("a");
  const currentFilename = location.pathname.split("/").pop() || "list.html";

  downloadLink.href = URL.createObjectURL(blob);
  downloadLink.download = currentFilename;
  document.body.appendChild(downloadLink);
  downloadLink.click();
  document.body.removeChild(downloadLink);
}