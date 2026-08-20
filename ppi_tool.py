"""i-PPI から当日公告の業務案件を取得して CSV/Excel に出力する。"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup


OUTPUT_COLUMNS = (
    "公示日",
    "案件名",
    "発注機関",
    "業種区分",
    "地域",
    "履行期間",
    "入札方式",
    "詳細URL",
)


class PpiError(RuntimeError):
    """PPI取得処理を継続できない場合の例外。"""


@dataclass(slots=True)
class AppConfig:
    site_url: str = "https://www.i-ppi.jp/"
    search_url: str = (
        "https://www.i-ppi.jp/IPPI/SearchServices/Web/Search/Search/Search.aspx?tab=6"
    )
    search_type: str = "業務"
    output: str = "csv"
    browser: str = "auto"
    headless: bool = True
    use_webdriver_manager: bool = False
    max_retry: int = 3
    retry_wait_seconds: float = 5.0
    wait_timeout_seconds: float = 30.0
    page_load_timeout_seconds: float = 60.0
    detail_wait_seconds: float = 0.2
    max_records: int = 5000
    fetch_details: bool = True
    output_dir: str = "output"
    log_dir: str = "logs"
    csv_encoding: str = "utf-8-sig"
    excel_sheet_name: str = "業務一覧"
    selectors: dict[str, str] | None = None
    field_labels: dict[str, list[str]] | None = None

    def __post_init__(self) -> None:
        default_selectors = {
            "business_search_link": "lbtGyomuKokoku",
            "date_from": "dateKokokuFromKokoku",
            "date_to": "dateKokokuToKokoku",
            "date_hidden": "tbxKokokuDate",
            "page_size": "drpCount",
            "search_button": "btnSearch",
            "result_table": "dgrSearchList",
        }
        default_labels = {
            "地域": ["業務対象地域", "履行場所", "業務場所", "地域"],
            "履行期間": ["履行期間", "履行期限", "業務期間"],
        }
        self.selectors = {**default_selectors, **(self.selectors or {})}
        self.field_labels = {**default_labels, **(self.field_labels or {})}
        self.output = self.output.lower()
        self.browser = self.browser.lower()

        if self.search_type != "業務":
            raise ValueError("search_type は '業務' のみ指定できます")
        if self.output not in {"csv", "excel", "both"}:
            raise ValueError("output は csv、excel、both のいずれかです")
        if self.browser not in {"auto", "chrome", "edge"}:
            raise ValueError("browser は auto、chrome、edge のいずれかです")
        if self.max_retry < 1:
            raise ValueError("max_retry は1以上で指定してください")
        if self.max_records < 1 or self.max_records > 5000:
            raise ValueError("max_records は1～5000で指定してください")


@dataclass(slots=True)
class PpiRecord:
    公示日: str
    案件名: str
    発注機関: str
    業種区分: str
    地域: str
    履行期間: str
    入札方式: str
    詳細URL: str
    detail_event: str = ""

    @property
    def duplicate_key(self) -> tuple[str, str, str]:
        return (self.案件名, self.発注機関, self.公示日)

    def output_dict(self) -> dict[str, str]:
        values = asdict(self)
        values.pop("detail_event")
        return values


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PpiError(f"設定ファイルが見つかりません: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise PpiError(f"設定ファイルのJSONが不正です: {exc}") from exc
    try:
        return AppConfig(**data)
    except (TypeError, ValueError) as exc:
        raise PpiError(f"設定内容が不正です: {exc}") from exc


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def parse_result_page(html: str) -> list[PpiRecord]:
    """検索結果ページから一覧行を抽出する。ページャー行は無視する。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#dgrSearchList")
    if table is None:
        page_text = normalize_text(soup.get_text(" ", strip=True))
        if "該当する案件が 0 件" in page_text or "該当データはありません" in page_text:
            return []
        raise PpiError("検索結果テーブル dgrSearchList を解析できません")

    records: list[PpiRecord] = []
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 6 or not normalize_text(cells[0].get_text()).isdigit():
            continue

        agency_and_office = normalize_text(cells[1].get_text(" ", strip=True))
        agency = normalize_text(re.split(r"[／/]", agency_and_office, maxsplit=1)[0])
        title_link = cells[2].find("a")
        title = normalize_text(cells[2].get_text(" ", strip=True))
        href = title_link.get("href", "") if title_link else ""
        event_match = re.search(r"__doPostBack\('dgrSearchList','([^']+)'\)", href)

        records.append(
            PpiRecord(
                公示日=normalize_text(cells[5].get_text(" ", strip=True)),
                案件名=title,
                発注機関=agency,
                業種区分=normalize_text(cells[4].get_text(" ", strip=True)),
                地域="",
                履行期間="",
                入札方式=normalize_text(cells[3].get_text(" ", strip=True)),
                詳細URL="",
                detail_event=event_match.group(1) if event_match else "",
            )
        )
    return records


def _table_label_values(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        label = normalize_text(cells[0].get_text(" ", strip=True)).rstrip("：:")
        value = normalize_text(" ".join(cell.get_text(" ", strip=True) for cell in cells[1:]))
        if label and value and len(label) <= 30:
            values.setdefault(label, value)
    return values


def _find_labeled_value(
    values: dict[str, str], aliases: Sequence[str]
) -> str:
    for alias in aliases:
        for label, value in values.items():
            if alias == label or alias in label:
                # i-PPIは未設定の地域を「自： 至：」のように表示する。
                placeholder_removed = re.sub(r"(?:自|至)\s*[：:]", "", value).strip()
                return value if placeholder_removed else ""
    return ""


def _find_document_url(soup: BeautifulSoup, detail_url: str) -> str:
    ignored_hosts = {"www.i-ppi.jp", "i-ppi.jp", "www.jacic.or.jp", "reg18.smp.ne.jp"}
    candidates: list[str] = []
    for link in soup.select("a[href]"):
        href = urljoin(detail_url, str(link.get("href", "")))
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or parsed.netloc in ignored_hosts:
            continue
        text = normalize_text(link.get_text(" ", strip=True))
        if "問い合わせ" in text:
            continue
        candidates.append(href)
    return candidates[0] if candidates else detail_url


def parse_detail_page(
    html: str,
    detail_url: str,
    field_labels: dict[str, list[str]],
) -> dict[str, str]:
    """案件概要から一覧にない項目と公開文書URLを抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    values = _table_label_values(soup)
    return {
        "地域": _find_labeled_value(values, field_labels["地域"]),
        "履行期間": _find_labeled_value(values, field_labels["履行期間"]),
        "詳細URL": _find_document_url(soup, detail_url),
    }


def deduplicate(records: Iterable[PpiRecord]) -> list[PpiRecord]:
    unique: list[PpiRecord] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        if record.duplicate_key in seen:
            continue
        seen.add(record.duplicate_key)
        unique.append(record)
    return unique


def write_outputs(
    records: Sequence[PpiRecord],
    config: AppConfig,
    target_date: date,
) -> list[Path]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_text = target_date.strftime("%Y%m%d")
    frame = pd.DataFrame(
        [record.output_dict() for record in records], columns=OUTPUT_COLUMNS
    )
    written: list[Path] = []

    if config.output in {"csv", "both"}:
        csv_path = output_dir / f"ppi_{date_text}.csv"
        frame.to_csv(csv_path, index=False, encoding=config.csv_encoding)
        written.append(csv_path)

    if config.output in {"excel", "both"}:
        excel_path = output_dir / f"ppi_{date_text}.xlsx"
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name=config.excel_sheet_name, index=False)
        written.append(excel_path)

    return written


def configure_logger(log_dir: str | Path, target_date: date) -> logging.Logger:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ppi_tool")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(
        directory / f"ppi_{target_date:%Y%m%d}.log", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def _browser_installed(browser: str) -> bool:
    if shutil.which(browser):
        return True
    candidates = {
        "chrome": (
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        ),
        "edge": (
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ),
    }
    return any(path.exists() for path in candidates[browser])


def create_webdriver(config: AppConfig) -> Any:
    """設定に従ってChromeまたはEdgeのWebDriverを生成する。"""
    from selenium import webdriver

    browser = config.browser
    if browser == "auto":
        if _browser_installed("chrome"):
            browser = "chrome"
        elif _browser_installed("edge"):
            browser = "edge"
        else:
            raise PpiError("ChromeまたはEdgeがインストールされていません")

    if browser == "chrome":
        from selenium.webdriver.chrome.service import Service

        options = webdriver.ChromeOptions()
        if config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        if config.use_webdriver_manager:
            from webdriver_manager.chrome import ChromeDriverManager

            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=options
            )
        else:
            driver = webdriver.Chrome(options=options)
    else:
        from selenium.webdriver.edge.service import Service

        options = webdriver.EdgeOptions()
        if config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        if config.use_webdriver_manager:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager

            driver = webdriver.Edge(
                service=Service(EdgeChromiumDriverManager().install()), options=options
            )
        else:
            driver = webdriver.Edge(options=options)

    driver.set_page_load_timeout(config.page_load_timeout_seconds)
    return driver


class PpiScraper:
    def __init__(
        self,
        config: AppConfig,
        logger: logging.Logger,
        driver_factory: Callable[[AppConfig], Any] = create_webdriver,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.logger = logger
        self.driver_factory = driver_factory
        self.sleep = sleep
        self.error_count = 0

    def collect(self, target_date: date) -> list[PpiRecord]:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retry + 1):
            driver = None
            try:
                self.logger.info("PPI接続を開始します（試行 %d/%d）", attempt, self.config.max_retry)
                driver = self.driver_factory(self.config)
                return self._collect_with_driver(driver, target_date)
            except Exception as exc:  # Selenium例外は環境により派生型が異なる
                last_error = exc
                self.error_count += 1
                self.logger.exception("取得処理に失敗しました（試行 %d）", attempt)
                if attempt < self.config.max_retry:
                    self.sleep(self.config.retry_wait_seconds)
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        self.logger.warning("ブラウザ終了処理に失敗しました", exc_info=True)
        raise PpiError(f"{self.config.max_retry}回の試行後も取得できませんでした: {last_error}")

    def _collect_with_driver(self, driver: Any, target_date: date) -> list[PpiRecord]:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import Select, WebDriverWait

        selectors = self.config.selectors
        assert selectors is not None
        wait = WebDriverWait(driver, self.config.wait_timeout_seconds)

        # トップ画面経由で「業務検索 > 入札公告等」を開く。
        driver.get(self.config.site_url)
        wait.until(ec.frame_to_be_available_and_switch_to_it((By.NAME, "contents")))
        wait.until(
            ec.element_to_be_clickable((By.ID, selectors["business_search_link"]))
        ).click()
        driver.switch_to.default_content()
        wait.until(ec.presence_of_element_located((By.ID, selectors["date_from"])))

        date_value = target_date.isoformat()
        for element_id in (selectors["date_from"], selectors["date_to"]):
            driver.execute_script(
                "const e=document.getElementById(arguments[0]);"
                "e.value=arguments[1];"
                "e.dispatchEvent(new Event('change',{bubbles:true}));",
                element_id,
                date_value,
            )
        hidden_value = target_date.strftime("%Y,%m,%d,%Y,%m,%d")
        driver.execute_script(
            "const e=document.getElementById(arguments[0]); if(e){e.value=arguments[1];}",
            selectors["date_hidden"],
            hidden_value,
        )
        Select(driver.find_element(By.ID, selectors["page_size"])).select_by_value("100")
        self.logger.info("検索条件: 公告日=%s、種別=%s", date_value, self.config.search_type)
        driver.find_element(By.ID, selectors["search_button"]).click()
        wait.until(ec.presence_of_element_located((By.ID, selectors["result_table"])))

        all_records: list[PpiRecord] = []
        page_number = 1
        while len(all_records) < self.config.max_records:
            page_records = parse_result_page(driver.page_source)
            self.logger.info("%dページ目: %d件を取得", page_number, len(page_records))
            if self.config.fetch_details:
                self._fill_details(driver, wait, page_records)
            remaining = self.config.max_records - len(all_records)
            all_records.extend(page_records[:remaining])
            if len(all_records) >= self.config.max_records:
                self.logger.warning("最大取得件数 %d 件で打ち切ります", self.config.max_records)
                break
            if not self._go_to_next_page(driver, wait, page_number):
                break
            page_number += 1
        return deduplicate(all_records)

    def _fill_details(self, driver: Any, wait: Any, records: list[PpiRecord]) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as ec

        selectors = self.config.selectors
        labels = self.config.field_labels
        assert selectors is not None and labels is not None

        for index, record in enumerate(records):
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, f"#{selectors['result_table']} tr")
                data_rows = [
                    row
                    for row in rows
                    if len(row.find_elements(By.CSS_SELECTOR, "td")) >= 6
                    and row.find_elements(By.CSS_SELECTOR, "td")[0].text.strip().isdigit()
                ]
                link = data_rows[index].find_element(By.CSS_SELECTOR, "td:nth-child(3) a")
                result_table = driver.find_element(By.ID, selectors["result_table"])
                link.click()
                wait.until(ec.staleness_of(result_table))
                wait.until(lambda current: "案件概要" in current.title)
                details = parse_detail_page(driver.page_source, driver.current_url, labels)
                record.地域 = details["地域"]
                record.履行期間 = details["履行期間"]
                record.詳細URL = details["詳細URL"]
            except Exception:
                self.error_count += 1
                self.logger.exception("詳細解析失敗: %s", record.案件名)
            finally:
                if "検索結果" not in driver.title:
                    driver.back()
                    wait.until(
                        ec.presence_of_element_located(
                            (By.ID, selectors["result_table"])
                        )
                    )
                if self.config.detail_wait_seconds:
                    self.sleep(self.config.detail_wait_seconds)

    def _go_to_next_page(self, driver: Any, wait: Any, page_number: int) -> bool:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as ec

        selectors = self.config.selectors
        assert selectors is not None
        table = driver.find_element(By.ID, selectors["result_table"])
        next_page = page_number + 1
        candidates = table.find_elements(By.TAG_NAME, "a")
        next_link = None
        for link in candidates:
            href = link.get_attribute("href") or ""
            match = re.search(r"Page\$([^']+)", href)
            if not match:
                continue
            argument = match.group(1)
            if argument == str(next_page) or normalize_text(link.text) in {"次へ", ">", "次"}:
                next_link = link
                break
        if next_link is None:
            return False
        next_link.click()
        wait.until(ec.staleness_of(table))
        wait.until(ec.presence_of_element_located((By.ID, selectors["result_table"])))
        return True


def run(config: AppConfig, target_date: date | None = None) -> tuple[list[PpiRecord], list[Path]]:
    run_date = target_date or date.today()
    logger = configure_logger(config.log_dir, run_date)
    started = datetime.now()
    logger.info("PPI公示業務取得ツールを開始します")
    scraper = PpiScraper(config, logger)
    records: list[PpiRecord] = []
    try:
        records = scraper.collect(run_date)
        paths = write_outputs(records, config, run_date)
        logger.info("取得件数=%d、異常件数=%d", len(records), scraper.error_count)
        for path in paths:
            logger.info("出力ファイル: %s", path.resolve())
        return records, paths
    finally:
        elapsed = (datetime.now() - started).total_seconds()
        logger.info("終了日時=%s、処理時間=%.2f秒", datetime.now().isoformat(timespec="seconds"), elapsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json", help="設定JSONのパス")
    parser.add_argument("--browser", choices=("auto", "chrome", "edge"))
    parser.add_argument("--headed", action="store_true", help="ブラウザ画面を表示する")
    parser.add_argument("--output", choices=("csv", "excel", "both"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.browser:
            config.browser = args.browser
        if args.headed:
            config.headless = False
        if args.output:
            config.output = args.output
        run(config)
        return 0
    except Exception as exc:
        logging.getLogger("ppi_tool").exception("処理を終了します: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
