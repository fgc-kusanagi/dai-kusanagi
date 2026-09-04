"""PPI案件を確認・選択するローカルWeb画面。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Flask, redirect, render_template, request, url_for

if TYPE_CHECKING:
    from ppi_tool import AppConfig, PpiRecord


CsvWriter = Callable[[Sequence["PpiRecord"], "AppConfig", date], Path]
RecordCollector = Callable[[date], Sequence["PpiRecord"]]


def create_selection_app(
    config: AppConfig,
    initial_date: date,
    record_collector: RecordCollector,
    csv_writer: CsvWriter,
) -> Flask:
    """日付検索、案件選択、CSV出力機能を持つFlaskアプリを生成する。"""
    app = Flask(__name__)
    app.config["PPI_RECORDS"] = []
    app.config["PPI_TARGET_DATE"] = initial_date
    app.config["SELECTED_CSV_PATH"] = None

    def render_selection(error: str | None = None, status: int = 200):
        available_records = app.config["PPI_RECORDS"]
        target_date = app.config["PPI_TARGET_DATE"]
        return (
            render_template(
                "selection.html",
                records=available_records,
                target_date=target_date,
                error=error,
            ),
            status,
        )

    @app.get("/")
    def index():
        return render_template(
            "search.html",
            default_date=app.config["PPI_TARGET_DATE"].isoformat(),
            error=None,
        )

    @app.post("/search")
    def search():
        raw_date = request.form.get("target_date", "").strip()
        try:
            target_date = date.fromisoformat(raw_date)
        except ValueError:
            return (
                render_template(
                    "search.html",
                    default_date=raw_date,
                    error="正しい日付を入力してください。",
                ),
                400,
            )

        try:
            records = list(record_collector(target_date))
        except Exception as exc:
            app.logger.exception("PPI案件の取得に失敗しました")
            return (
                render_template(
                    "search.html",
                    default_date=raw_date,
                    error=f"PPI案件を取得できませんでした: {exc}",
                ),
                502,
            )

        app.config["PPI_RECORDS"] = records
        app.config["PPI_TARGET_DATE"] = target_date
        return render_selection()

    @app.get("/selection")
    def selection():
        if not app.config["PPI_RECORDS"]:
            return redirect(url_for("index"))
        return render_selection()

    @app.post("/export")
    def export_selected():
        available_records = app.config["PPI_RECORDS"]
        target_date = app.config["PPI_TARGET_DATE"]
        raw_indices = request.form.getlist("selected")
        try:
            indices = [int(value) for value in raw_indices]
        except ValueError:
            return render_selection("選択内容が不正です。もう一度選択してください。", 400)

        if not indices:
            return render_selection("CSVに出力する業務を1件以上選択してください。", 400)
        if len(indices) != len(set(indices)) or any(
            index < 0 or index >= len(available_records) for index in indices
        ):
            return render_selection("選択内容が不正です。もう一度選択してください。", 400)

        selected = [available_records[index] for index in indices]
        csv_path = csv_writer(selected, config, target_date)
        app.config["SELECTED_CSV_PATH"] = csv_path
        shutdown = app.config.get("SELECTION_SHUTDOWN")
        if callable(shutdown):
            shutdown()
        return render_template(
            "complete.html",
            csv_path=csv_path.resolve(),
            selected_count=len(selected),
        )

    return app
