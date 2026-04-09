from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from app.config import get_config


def load_and_prepare(filepath):
    df = pd.read_csv(filepath)

    summary = []

    for algo, group in df.groupby("algorithm_name"):
        total = len(group)
        success = group[group["failed"] == False]

        success_rate = len(success) / total * 100

        def mean(col):
            if success.empty:
                return None
            return success[col].mean()

        summary.append({
            "algorithm": algo,
            "success_rate": success_rate,
            "distance_increase_pct": mean("distance_increase_pct"),
            "total_time": mean("total_planning_time"),
        })

    return pd.DataFrame(summary)


def plot_bar(df, value_col, title, ylabel, filename):
    plt.figure()

    plt.bar(df["algorithm"], df[value_col])

    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("Algorithm")

    plt.tight_layout()
    plt.savefig(filename)
    plt.close()


def main():
    config = get_config()
    outputs = config.paths.outputs_dir

    remove_path = outputs / "results_remove.csv"
    cost_path = outputs / "results_increase_cost_3_0.csv"

    df_remove = load_and_prepare(remove_path)
    df_cost = load_and_prepare(cost_path)

    # --- SUCCESS RATE ---
    combined = pd.concat([
        df_remove.assign(scenario="remove"),
        df_cost.assign(scenario="increase_cost")
    ])

    for scenario in combined["scenario"].unique():
        subset = combined[combined["scenario"] == scenario]

        plot_bar(
            subset,
            "success_rate",
            f"Success Rate ({scenario})",
            "Success Rate (%)",
            outputs / f"success_rate_{scenario}.png"
        )

    # --- DISTANCE INCREASE ---
    for scenario in combined["scenario"].unique():
        subset = combined[combined["scenario"] == scenario]

        plot_bar(
            subset,
            "distance_increase_pct",
            f"Distance Increase % ({scenario})",
            "Increase (%)",
            outputs / f"distance_increase_{scenario}.png"
        )

    # --- TOTAL TIME ---
    for scenario in combined["scenario"].unique():
        subset = combined[combined["scenario"] == scenario]

        plot_bar(
            subset,
            "total_time",
            f"Total Planning Time ({scenario})",
            "Time (s)",
            outputs / f"time_{scenario}.png"
        )

    print("Kuvaajat tallennettu kansioon:", outputs)


if __name__ == "__main__":
    main()