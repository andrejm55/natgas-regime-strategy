from __future__ import annotations
import pandas as pd

def align_storage_to_daily(daily: pd.DataFrame, storage: pd.DataFrame) -> pd.DataFrame:
    """Attach latest known storage to daily bars using release_date availability."""
    d = daily.sort_values("date").copy()
    s = storage.sort_values("release_date").copy()
    d["date"] = pd.to_datetime(d["date"])
    s["release_date"] = pd.to_datetime(s["release_date"])
    return pd.merge_asof(
        d,
        s,
        left_on="date",
        right_on="release_date",
        direction="backward",
    )


def add_storage_zscore(storage: pd.DataFrame, baseline_years: int = 5) -> pd.DataFrame:
    """Compute storage z-score on the full weekly history before daily alignment."""
    out = storage.sort_values("release_date").copy()
    out["release_date"] = pd.to_datetime(out["release_date"])
    week_source = out["week_ending_date"] if "week_ending_date" in out.columns else out["release_date"]
    week_source = pd.to_datetime(week_source)
    out["weekofyear"] = week_source.dt.isocalendar().week.astype(int)
    out["year"] = week_source.dt.year
    out["weekly_storage_change"] = out["storage_bcf"].diff()

    z_values: list[float | None] = []
    normal_change_values: list[float | None] = []
    change_surprise_values: list[float | None] = []
    percentile_values: list[float | None] = []
    for _, row in out.iterrows():
        prior_mask = (
            (out["weekofyear"] == row["weekofyear"])
            & (out["year"] < row["year"])
            & (out["year"] >= row["year"] - baseline_years)
        )
        prior_storage = out[prior_mask]["storage_bcf"].dropna()
        if len(prior_storage) < 2 or prior_storage.std(ddof=0) == 0:
            z_values.append(None)
        else:
            z_values.append(
                (row["storage_bcf"] - prior_storage.mean()) / prior_storage.std(ddof=0)
            )

        prior_changes = out[prior_mask]["weekly_storage_change"].dropna()
        if len(prior_changes) < 2 or pd.isna(row["weekly_storage_change"]):
            normal_change_values.append(None)
            change_surprise_values.append(None)
        else:
            normal_change = prior_changes.mean()
            normal_change_values.append(normal_change)
            change_surprise_values.append(row["weekly_storage_change"] - normal_change)

        if len(prior_storage) < 2:
            percentile_values.append(None)
        else:
            percentile_values.append(float((prior_storage <= row["storage_bcf"]).mean()))

    out["storage_z"] = z_values
    out["normal_weekly_storage_change"] = normal_change_values
    out["storage_change_vs_normal"] = change_surprise_values
    out["weekly_change_vs_5yr_normal"] = change_surprise_values
    out["injection_withdrawal_surprise_vs_normal"] = change_surprise_values
    out["storage_percentile_by_week"] = percentile_values
    return out
