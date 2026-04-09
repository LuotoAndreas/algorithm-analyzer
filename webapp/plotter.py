import os
import matplotlib.pyplot as plt

OUTPUT_DIR = "webapp/static/plots"

ALGORITHM_ORDER = ["Dijkstra", "A*", "D* Lite"]


def ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _ordered_grouped_mean(df, column_name):
    grouped = df.groupby("algorithm_name")[column_name].mean()
    grouped = grouped.reindex([name for name in ALGORITHM_ORDER if name in grouped.index])
    return grouped


def _add_value_labels(ax, decimals=2, suffix=""):
    max_height = max([bar.get_height() for bar in ax.patches if bar.get_height() is not None], default=0)

    for bar in ax.patches:
        height = bar.get_height()
        if height is None:
            continue

        ax.annotate(
            f"{height:.{decimals}f}{suffix}",
            (bar.get_x() + bar.get_width() / 2, height),
            ha="center",
            va="bottom",
            xytext=(0, max_height * 0.03),  # 🔥 dynaaminen offset
            textcoords="offset points",
            fontsize=10,
        )

    # 🔥 lisätään ylätilaa ettei teksti mene rajaan
    ax.set_ylim(0, max_height * 1.15 if max_height > 0 else 1)

def plot_distance_increase(df, filename):
    ensure_dir()

    grouped = _ordered_grouped_mean(df, "distance_increase_pct")

    fig, ax = plt.subplots(figsize=(8, 5))
    grouped.plot(kind="bar", ax=ax)

    ax.set_title("Keskimääräinen matkan piteneminen (%)")
    ax.set_ylabel("Prosenttia (%)")
    ax.set_xlabel("Algoritmi")
    ax.tick_params(axis="x", rotation=0)

    _add_value_labels(ax, decimals=2, suffix=" %")

    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return path

def plot_total_time(df, filename):
    ensure_dir()

    grouped = _ordered_grouped_mean(df, "total_planning_time")

    # 🔥 muutetaan millisekunneiksi
    grouped = grouped * 1000

    fig, ax = plt.subplots(figsize=(8, 5))
    grouped.plot(kind="bar", ax=ax)

    ax.set_title("Keskimääräinen kokonaislaskenta-aika (ms)")
    ax.set_ylabel("Millisekuntia (ms)")
    ax.set_xlabel("Algoritmi")
    ax.tick_params(axis="x", rotation=0)

    _add_value_labels(ax, decimals=3, suffix=" ms")

    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return path