import csv
import json
from datetime import date

import pandas as pd
import pytest

from ppi_tool import (
    AppConfig,
    PpiError,
    PpiRecord,
    deduplicate,
    load_config,
    parse_detail_page,
    parse_result_page,
    write_outputs,
)


RESULT_HTML = """
<html><body>
<table id="dgrSearchList">
  <tr class="dgrtitle">
    <th>No</th><th>発注機関／担当部・事務所</th><th>業務名</th>
    <th>入札契約方式</th><th>業務区分</th><th>公告日</th>
  </tr>
  <tr>
    <td>1</td><td>国土交通省東北地方整備局 ／ 仙台事務所</td>
    <td><a href="javascript:__doPostBack('dgrSearchList','$0')">河川調査業務</a></td>
    <td>一般競争入札</td><td>土木コンサル業務</td><td>2026/08/20</td>
  </tr>
  <tr><td colspan="6"><a href="javascript:__doPostBack('dgrSearchList','Page$2')">2</a></td></tr>
</table>
</body></html>
"""


DETAIL_HTML = """
<html><body>
<table>
  <tr><td>業務名称</td><td>河川調査業務</td></tr>
  <tr><td>業務対象地域</td><td>宮城県仙台市</td></tr>
  <tr><td>履行期間</td><td>2026/09/01 ～ 2027/03/31</td></tr>
</table>
<table><tr><td>公開文書</td><td><a href="https://example.go.jp/tender.pdf">公開中</a></td></tr></table>
</body></html>
"""


def make_record(**changes):
    values = {
        "公示日": "2026/08/20",
        "案件名": "河川調査業務",
        "発注機関": "国土交通省東北地方整備局",
        "業種区分": "土木コンサル業務",
        "地域": "宮城県",
        "履行期間": "2026/09/01 ～ 2027/03/31",
        "入札方式": "一般競争入札",
        "詳細URL": "https://example.go.jp/tender.pdf",
    }
    values.update(changes)
    return PpiRecord(**values)


def test_parse_result_page_extracts_list_fields():
    records = parse_result_page(RESULT_HTML)

    assert len(records) == 1
    assert records[0].案件名 == "河川調査業務"
    assert records[0].発注機関 == "国土交通省東北地方整備局"
    assert records[0].業種区分 == "土木コンサル業務"
    assert records[0].入札方式 == "一般競争入札"
    assert records[0].公示日 == "2026/08/20"
    assert records[0].detail_event == "$0"


def test_parse_result_page_returns_empty_for_zero_results():
    assert parse_result_page("<html><body>該当する案件が 0 件あります。</body></html>") == []


def test_parse_result_page_rejects_unknown_html():
    with pytest.raises(PpiError, match="dgrSearchList"):
        parse_result_page("<html><body>maintenance</body></html>")


def test_parse_detail_page_extracts_optional_fields_and_document_url():
    config = AppConfig()
    result = parse_detail_page(
        DETAIL_HTML,
        "https://www.i-ppi.jp/detail",
        config.field_labels,
    )

    assert result == {
        "地域": "宮城県仙台市",
        "履行期間": "2026/09/01 ～ 2027/03/31",
        "詳細URL": "https://example.go.jp/tender.pdf",
    }


def test_parse_detail_page_uses_detail_page_when_document_url_is_absent():
    config = AppConfig()
    result = parse_detail_page(
        "<html><table><tr><td>業務名称</td><td>案件</td></tr></table></html>",
        "https://www.i-ppi.jp/session-detail",
        config.field_labels,
    )

    assert result["地域"] == ""
    assert result["履行期間"] == ""
    assert result["詳細URL"] == "https://www.i-ppi.jp/session-detail"


def test_parse_detail_page_treats_empty_from_to_region_as_blank():
    config = AppConfig()
    html = "<table><tr><td>業務対象地域</td><td>自：<br>至：</td></tr></table>"

    result = parse_detail_page(
        html,
        "https://www.i-ppi.jp/session-detail",
        config.field_labels,
    )

    assert result["地域"] == ""


def test_deduplicate_uses_title_agency_and_notice_date():
    original = make_record()
    duplicate = make_record(地域="別の表記")
    other_agency = make_record(発注機関="別機関")

    assert deduplicate([original, duplicate, other_agency]) == [original, other_agency]


def test_write_outputs_writes_utf8_csv_with_required_columns(tmp_path):
    config = AppConfig(output_dir=str(tmp_path), output="csv")

    paths = write_outputs([make_record()], config, date(2026, 8, 20))

    assert paths == [tmp_path / "ppi_20260820.csv"]
    with paths[0].open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0]) == ["公示日", "案件名", "発注機関", "業種区分", "地域", "履行期間", "入札方式", "詳細URL"]
    assert rows[0]["案件名"] == "河川調査業務"


def test_write_outputs_writes_empty_csv_with_header(tmp_path):
    config = AppConfig(output_dir=str(tmp_path), output="csv")

    path = write_outputs([], config, date(2026, 8, 20))[0]

    with path.open(encoding="utf-8-sig", newline="") as file:
        assert list(csv.reader(file)) == [["公示日", "案件名", "発注機関", "業種区分", "地域", "履行期間", "入札方式", "詳細URL"]]


def test_write_outputs_writes_excel_sheet(tmp_path):
    config = AppConfig(output_dir=str(tmp_path), output="excel")

    path = write_outputs([make_record()], config, date(2026, 8, 20))[0]

    frame = pd.read_excel(path, sheet_name="業務一覧")
    assert list(frame.columns) == ["公示日", "案件名", "発注機関", "業種区分", "地域", "履行期間", "入札方式", "詳細URL"]
    assert frame.loc[0, "案件名"] == "河川調査業務"


def test_load_config_merges_default_selectors(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"selectors": {"search_button": "customSearch"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.selectors["search_button"] == "customSearch"
    assert config.selectors["result_table"] == "dgrSearchList"


@pytest.mark.parametrize(
    "values",
    [
        {"output": "pdf"},
        {"browser": "firefox"},
        {"max_retry": 0},
        {"max_records": 5001},
        {"search_type": "工事"},
    ],
)
def test_config_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        AppConfig(**values)
