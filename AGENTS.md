# AGENTS.md

## Setup commands
- python -m venv .venv
- pip install -r requirements.txt
- python -m pytest tests -q

## Code style
-Python 3.12
-関数と変数はsnake_case
-公開関数に型ヒントとdocstringを付ける
-docstringは日本語

## Testing instructions
- 変更箇所のテストを先に実行する
- 新しい公開関数にはテストを追加する
- 最後にpython -m pytestを実行する

## PR & Commit guidelines
- commitは type: summary 形式
- PR前に全テストの結果を報告する