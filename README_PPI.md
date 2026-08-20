# PPI公示業務取得ツール

i-PPIの「業務検索 > 入札公告等」から、実行日に公告された案件を取得します。検索結果を全ページ巡回し、重複を除外してCSV、任意でExcelへ出力します。

## 動作環境

- Windows 11
- Python 3.11以上
- Google Chrome（推奨）またはMicrosoft Edge
- インターネット接続

## セットアップ

PowerShellでこのフォルダを開き、仮想環境を作成します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

ChromeDriver／EdgeDriverはSelenium Managerがブラウザに合う版を自動準備します。社内ネットワークなどでSelenium Managerを利用できない場合は、`config.json` の `use_webdriver_manager` を `true` にするとwebdriver-managerを使用します。

## 実行

```powershell
python ppi_tool.py
```

ブラウザ自動判定を使わずChromeを指定する場合:

```powershell
python ppi_tool.py --browser chrome
```

Excelも出力する場合:

```powershell
python ppi_tool.py --output both
```

画面を表示して動きを確認する場合:

```powershell
python ppi_tool.py --headed
```

## 出力

- CSV: `output/ppi_yyyyMMdd.csv`（UTF-8 BOM付き）
- Excel: `output/ppi_yyyyMMdd.xlsx`、シート名 `業務一覧`
- ログ: `logs/ppi_yyyyMMdd.log`

検索結果が0件でも、ヘッダーだけを含む空の出力ファイルを作成します。

## 設定

`config.json` で出力形式、リトライ、待機時間、最大取得件数、ブラウザ、HTML要素ID、詳細画面の項目名を変更できます。

主な設定:

| 設定 | 内容 |
|---|---|
| `output` | `csv`、`excel`、`both` |
| `browser` | `auto`、`chrome`、`edge` |
| `max_retry` | 通信・タイムアウト時の最大試行回数 |
| `retry_wait_seconds` | 再試行までの待機秒数 |
| `fetch_details` | 地域、履行期間、詳細URLを案件概要から補完するか |
| `max_records` | 最大取得件数（上限5,000） |

## i-PPI固有の注意点

- i-PPIの一覧画面で直接取得できるのは、発注機関、業務名、入札契約方式、業務区分、公告日です。
- 地域と履行期間は、案件概要に項目が存在するときだけ設定されます。サイトに値がない場合は空欄です。
- 案件概要のURLはASP.NETのセッションとPostBackに依存し、案件固有の恒久URLではありません。そのため、公開文書への外部リンクがあればそれを「詳細URL」として出力します。
- `fetch_details=true` は案件ごとに詳細画面を開くため、件数が多い日は処理時間が増えます。10分以内を優先するときは `false` にしてください。この場合、地域・履行期間・詳細URLは空欄になります。
- サイト構成が変更された場合は、`selectors` と `field_labels`、または解析処理の更新が必要です。

## テスト

```powershell
python -m pytest -q
```
