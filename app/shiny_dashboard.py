"""Interactive Shiny dashboard over the same safe analytics dataset as the API."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from shiny import App, reactive, render, ui

from app.analytics.data import load_content_frame, trends

FRAME = load_content_frame()
PLATFORMS = sorted(FRAME["platform"].unique())
CATEGORIES = sorted(FRAME["category"].unique())


def filter_content(
    frame: pd.DataFrame,
    platforms: tuple[str, ...] | list[str],
    categories: tuple[str, ...] | list[str],
) -> pd.DataFrame:
    """Pure filtering function shared by the interactive UI and tests."""
    result = frame
    if platforms:
        result = result.loc[result["platform"].isin(platforms)]
    if categories:
        result = result.loc[result["category"].isin(categories)]
    return result.copy()


app_ui = ui.page_fluid(
    ui.h2("ContentOps: интерактивная аналитика"),
    ui.p("Демонстрационный дашборд использует синтетический набор без персональных данных."),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_checkbox_group("platforms", "Платформы", choices=PLATFORMS, selected=PLATFORMS),
            ui.input_checkbox_group("categories", "Категории", choices=CATEGORIES, selected=CATEGORIES),
        ),
        ui.layout_columns(
            ui.card(ui.card_header("Динамика trend score"), ui.output_plot("trend_plot")),
            ui.card(ui.card_header("Просмотры по категориям"), ui.output_plot("category_plot")),
            col_widths=(6, 6),
        ),
        ui.card(ui.card_header("Просмотры и вовлечение"), ui.output_plot("scatter_plot")),
    ),
)


def server(input, output, session):
    @reactive.calc
    def filtered_frame():
        return filter_content(FRAME, input.platforms(), input.categories())

    @render.plot
    def trend_plot():
        frame = filtered_frame()
        fig, ax = plt.subplots(figsize=(7, 4))
        data = pd.DataFrame(trends(frame)) if not frame.empty else pd.DataFrame()
        if data.empty:
            ax.text(0.5, 0.5, "Нет данных для выбранных фильтров", ha="center", va="center")
        else:
            ax.plot(data["date"], data["average_trend_score"], marker="o", color="#2563eb")
            ax.tick_params(axis="x", rotation=35)
        ax.set(xlabel="Дата", ylabel="Trend score")
        fig.tight_layout()
        return fig

    @render.plot
    def category_plot():
        frame = filtered_frame()
        fig, ax = plt.subplots(figsize=(7, 4))
        values = frame.groupby("category")["views"].sum().sort_values(ascending=False)
        values.plot.bar(ax=ax, color="#16a34a")
        ax.set(xlabel="Категория", ylabel="Просмотры")
        fig.tight_layout()
        return fig

    @render.plot
    def scatter_plot():
        frame = filtered_frame()
        fig, ax = plt.subplots(figsize=(9, 4))
        scatter = ax.scatter(
            frame["views"], frame["engagement_rate"], c=frame["trend_score"], cmap="viridis"
        )
        ax.set(xlabel="Просмотры", ylabel="Engagement rate")
        fig.colorbar(scatter, ax=ax, label="Trend score")
        fig.tight_layout()
        return fig


app = App(app_ui, server)
