"""Reproducible, privacy-safe analytics pipeline for ContentOps."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.analytics.scoring import calculate_trend_scores

PACKAGE_DIR = Path(__file__).parent
DEMO_DATASET = PACKAGE_DIR / "demo_content.csv"
DEFAULT_ARTIFACTS_DIR = Path("artifacts")


def load_content_frame(path: Path | str = DEMO_DATASET) -> pd.DataFrame:
    """Loads and cleans the checked-in synthetic dataset using Pandas."""
    frame = pd.read_csv(path)
    numeric = ["views", "likes", "comments", "shares"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).clip(lower=0)
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["created_at", "platform", "category"]).drop_duplicates("external_id")
    frame["platform"] = frame["platform"].str.strip().str.lower()
    frame["category"] = frame["category"].str.strip().str.lower()

    # Demonstrates a merge with a small platform dimension table.
    platform_dimension = pd.DataFrame(
        {"platform": ["tiktok", "telegram", "youtube"], "platform_group": ["short_video", "community", "video"]}
    )
    frame = frame.merge(platform_dimension, on="platform", how="left", validate="many_to_one")
    now = pd.Timestamp.now(tz="UTC")
    age_hours = (now - frame["created_at"]).dt.total_seconds().clip(lower=3600) / 3600
    frame["trend_score"] = calculate_trend_scores(
        frame["views"].to_numpy(),
        frame["likes"].to_numpy(),
        frame["comments"].to_numpy(),
        frame["shares"].to_numpy(),
        age_hours.to_numpy(),
    )
    frame["engagement_rate"] = (
        (frame["likes"] + frame["comments"] + frame["shares"]) / frame["views"].clip(lower=1)
    )
    view_range = np.ptp(frame["views"].to_numpy())
    frame["normalized_views"] = (
        (frame["views"] - frame["views"].min()) / view_range if view_range else 0.0
    )
    return frame


def summary(frame: pd.DataFrame) -> dict:
    """Uses filtering, grouping, aggregation and a pivot table for the API."""
    recent = frame.loc[frame["created_at"] >= frame["created_at"].max() - pd.Timedelta(days=30)]
    category_pivot = pd.pivot_table(
        recent,
        index="category",
        columns="platform",
        values="views",
        aggfunc="sum",
        fill_value=0,
    )
    category_totals = category_pivot.sum(axis=1).astype(int).to_dict()
    grouped = recent.groupby("platform", as_index=False).agg(views=("views", "sum"))
    top_platform = grouped.sort_values("views", ascending=False).iloc[0]["platform"] if not grouped.empty else None
    return {
        "total_items": int(len(recent)),
        "total_views": int(recent["views"].sum()),
        "average_engagement_rate": round(float(recent["engagement_rate"].mean()), 6),
        "top_platform": top_platform,
        "category_totals": category_totals,
    }


def trends(frame: pd.DataFrame) -> list[dict]:
    by_date = (
        frame.assign(date=frame["created_at"].dt.date.astype(str))
        .groupby("date", as_index=False)
        .agg(average_trend_score=("trend_score", "mean"), normalized_views=("normalized_views", "mean"))
        .sort_values("date")
    )
    return [
        {
            "date": row.date,
            "average_trend_score": round(float(row.average_trend_score), 4),
            "normalized_views": round(float(row.normalized_views), 4),
        }
        for row in by_date.itertuples(index=False)
    ]


def create_charts(frame: pd.DataFrame, output_dir: Path | str = DEFAULT_ARTIFACTS_DIR) -> dict[str, str]:
    """Creates the three report charts and returns their relative artifact paths."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    daily = pd.DataFrame(trends(frame))
    line_path = output / "trend_dynamics.png"
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(daily["date"], daily["average_trend_score"], marker="o", color="#2563eb")
    ax.set(title="Динамика среднего trend score", xlabel="Дата", ylabel="Trend score")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(line_path, dpi=140)
    plt.close(fig)

    category = frame.groupby("category", as_index=False)["views"].sum().sort_values("views", ascending=False)
    bar_path = output / "category_views.png"
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(category["category"], category["views"], color="#16a34a")
    ax.set(title="Просмотры по категориям", xlabel="Категория", ylabel="Просмотры")
    fig.tight_layout()
    fig.savefig(bar_path, dpi=140)
    plt.close(fig)

    scatter_path = output / "engagement_scatter.png"
    fig, ax = plt.subplots(figsize=(7, 4))
    scatter = ax.scatter(frame["views"], frame["engagement_rate"], c=frame["trend_score"], cmap="viridis")
    ax.set(title="Связь просмотров и вовлечения", xlabel="Просмотры", ylabel="Engagement rate")
    fig.colorbar(scatter, ax=ax, label="Trend score")
    fig.tight_layout()
    fig.savefig(scatter_path, dpi=140)
    plt.close(fig)

    return {"line": str(line_path), "categories": str(bar_path), "scatter": str(scatter_path)}
