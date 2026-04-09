from __future__ import annotations

from pathlib import Path
import pandas as pd

from app.config import get_config


def load_csv(filepath: Path) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    return df


def print_basic_overview(df: pd.DataFrame, title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    print(f"Rivejä yhteensä: {len(df)}")
    print(f"Skenaarioita yhteensä: {df['scenario_id'].nunique()}")
    print(f"Algoritmeja: {', '.join(sorted(df['algorithm_name'].unique()))}")


def summarize_by_algorithm(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for algorithm_name, group in df.groupby("algorithm_name"):
        all_count = len(group)
        success_group = group[group["failed"] == False]
        success_count = len(success_group)
        failed_count = all_count - success_count
        success_rate = (success_count / all_count * 100.0) if all_count > 0 else 0.0

        def mean_or_none(frame: pd.DataFrame, column: str):
            if frame.empty:
                return None
            values = frame[column].dropna()
            if values.empty:
                return None
            return values.mean()

        rows.append({
            "algorithm_name": algorithm_name,

            "scenario_count_all": all_count,
            "successful_count": success_count,
            "failed_count": failed_count,
            "success_rate_pct": success_rate,

            # Vain onnistuneista tapauksista
            "avg_original_route_length_success": mean_or_none(success_group, "original_route_length"),
            "avg_total_distance_travelled_success": mean_or_none(success_group, "total_distance_travelled"),
            "avg_distance_increase_success": mean_or_none(success_group, "distance_increase"),
            "avg_distance_increase_pct_success": mean_or_none(success_group, "distance_increase_pct"),

            "avg_original_planning_time_success": mean_or_none(success_group, "original_planning_time"),
            "avg_replanning_time_total_success": mean_or_none(success_group, "replanning_time_total"),
            "avg_total_planning_time_success": mean_or_none(success_group, "total_planning_time"),

            "avg_replanning_count_success": mean_or_none(success_group, "replanning_count"),
            "avg_route_change_ratio_success": mean_or_none(success_group, "route_change_ratio"),
        })

    return pd.DataFrame(rows)


def print_summary_table(summary_df: pd.DataFrame, title: str) -> None:
    print()
    print(title)
    print(summary_df.to_string(index=False))


def compare_two_files(df_a: pd.DataFrame, name_a: str, df_b: pd.DataFrame, name_b: str) -> None:
    print()
    print("=" * 80)
    print("SKENAARIOIDEN VÄLINEN VERTAILU")
    print("=" * 80)

    summary_a = summarize_by_algorithm(df_a).set_index("algorithm_name")
    summary_b = summarize_by_algorithm(df_b).set_index("algorithm_name")

    common_algorithms = sorted(set(summary_a.index) & set(summary_b.index))

    for algorithm in common_algorithms:
        print()
        print(f"{algorithm}")

        a_success = summary_a.loc[algorithm, "success_rate_pct"]
        b_success = summary_b.loc[algorithm, "success_rate_pct"]

        a_dist = summary_a.loc[algorithm, "avg_distance_increase_pct_success"]
        b_dist = summary_b.loc[algorithm, "avg_distance_increase_pct_success"]

        a_time = summary_a.loc[algorithm, "avg_total_planning_time_success"]
        b_time = summary_b.loc[algorithm, "avg_total_planning_time_success"]

        def fmt_pct(value):
            return "N/A" if pd.isna(value) else f"{value:.2f} %"

        def fmt_time(value):
            return "N/A" if pd.isna(value) else f"{value:.6f} s"

        print(f"  Onnistumisaste {name_a}: {a_success:.2f} %")
        print(f"  Onnistumisaste {name_b}: {b_success:.2f} %")

        print(f"  Keskimääräinen matkan piteneminen onnistuneissa tapauksissa {name_a}: {fmt_pct(a_dist)}")
        print(f"  Keskimääräinen matkan piteneminen onnistuneissa tapauksissa {name_b}: {fmt_pct(b_dist)}")

        print(f"  Keskimääräinen kokonaislaskenta-aika onnistuneissa tapauksissa {name_a}: {fmt_time(a_time)}")
        print(f"  Keskimääräinen kokonaislaskenta-aika onnistuneissa tapauksissa {name_b}: {fmt_time(b_time)}")


def print_failed_case_counts(df: pd.DataFrame, title: str) -> None:
    print()
    print(title)

    failed_only = df[df["failed"] == True]

    if failed_only.empty:
        print("Ei epäonnistuneita tapauksia.")
        return

    counts = (
        failed_only.groupby(["algorithm_name", "failure_reason"])
        .size()
        .reset_index(name="count")
        .sort_values(["algorithm_name", "count"], ascending=[True, False])
    )

    print(counts.to_string(index=False))


def main() -> None:
    config = get_config()
    outputs_dir = config.paths.outputs_dir

    remove_file = outputs_dir / "results_remove.csv"
    increase_cost_file = outputs_dir / "results_increase_cost_3_0.csv"

    if not remove_file.exists():
        print(f"Tiedostoa ei löytynyt: {remove_file}")
        return

    if not increase_cost_file.exists():
        print(f"Tiedostoa ei löytynyt: {increase_cost_file}")
        return

    df_remove = load_csv(remove_file)
    df_increase = load_csv(increase_cost_file)

    print_basic_overview(df_remove, "REMOVE-SKENAARIO")
    remove_summary = summarize_by_algorithm(df_remove)
    print_summary_table(remove_summary, "Yhteenveto algoritmeittain (remove)")
    print_failed_case_counts(df_remove, "Epäonnistuneet tapaukset (remove)")

    print_basic_overview(df_increase, "INCREASE_COST-SKENAARIO")
    increase_summary = summarize_by_algorithm(df_increase)
    print_summary_table(increase_summary, "Yhteenveto algoritmeittain (increase_cost)")
    print_failed_case_counts(df_increase, "Epäonnistuneet tapaukset (increase_cost)")

    compare_two_files(df_remove, "remove", df_increase, "increase_cost")


if __name__ == "__main__":
    main()