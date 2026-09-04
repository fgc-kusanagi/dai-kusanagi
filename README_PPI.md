# PPI公示業務取得ツール

i-PPIの「業務検索 > 入札公告等」から公示案件を取得し、ローカルのWeb画面で内容を確認・選択して、必要な案件だけをCSVへ出力します。

処理の流れは次のとおりです。

1. ブラウザで公示日を指定する
2. i-PPIから指定日の公示業務を取得する
3. 案件名・発注機関・地域などで絞り込み、必要な業務をチェックする
4. 「選択した案件をCSV出力」を押す

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

## 起動方法

`PPI公示業務Web起動.vbs` をダブルクリックしてください。PowerShellや黒いコンソール画面は表示されず、Web画面だけが既定ブラウザに開きます。

Web画面で公示日を指定して「PPI公示業務を検索」を押します。取得完了後、必要な業務を選択してCSVを出力してください。

### コマンドから起動する場合

```powershell
python ppi_tool.py
```

ブラウザ自動判定を使わずChromeを指定する場合:

```powershell
python ppi_tool.py --browser chrome
```

初期表示する公示日を指定する場合（通常はWeb画面で指定できます）:

```powershell
python ppi_tool.py --date 2026-08-20
```

画面を表示して動きを確認する場合:

```powershell
python ppi_tool.py --headed
```

案件選択画面を自動で開かず、表示されたURLを手動で開く場合:

```powershell
python ppi_tool.py --no-open
```

起動すると通常は `http://127.0.0.1:8765/` に日付指定画面が開きます。前回の画面が残っている場合は、空いている別ポートを自動的に使用します。CSV出力後、プログラムは自動終了します。

## 出力

- 選択済みCSV: `output/ppi_selected_yyyyMMdd.csv`（UTF-8 BOM付き）
- ログ: `logs/ppi_yyyyMMdd.log`

検索結果が0件の場合、CSVは作成しません。選択画面では1件以上の選択が必要です。

## 設定

`config.json` でリトライ、待機時間、最大取得件数、ブラウザ、選択画面のポート、HTML要素ID、詳細画面の項目名を変更できます。

主な設定:

| 設定 | 内容 |
|---|---|
| `browser` | `auto`、`chrome`、`edge` |
| `max_retry` | 通信・タイムアウト時の最大試行回数 |
| `retry_wait_seconds` | 再試行までの待機秒数 |
| `fetch_details` | 地域、履行期間、詳細URLを案件概要から補完するか |
| `max_records` | 最大取得件数（上限5,000） |
| `selection_port` | ローカル選択画面のポート（既定: `8765`） |
| `open_selection_browser` | 選択画面を既定ブラウザで自動的に開くか |

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
