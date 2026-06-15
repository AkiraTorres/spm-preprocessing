import os
import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import sys

# Config centralizada (antes duplicada no topo de cada script).
sys.path.insert(0, "src")
from spm.config import SCENERIES_NAMES as sceneries_names

SOURCE = "mining"  # "mining" usa mining_results_; "sceneries" usa sceneries_results_

# Pares (COURSE, activity) a comparar — adicione ou remova conforme necessário
SERIES = [
    (2060, 2),
    (2065, 1),
]



def count_patterns(filepath):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    total = 0
    for key, value in data.items():
        if key.endswith("_sequences"):
            seqs = value.get("sequences", [])
            total += len(seqs)
    return total


def build_paths(source, course, act, names):
    paths = []
    for name in names:
        if source == "mining":
            path = os.path.join(
                f"outputs/mining_results/{course}", str(act), f"{name}_mining.json"
            )
        else:
            path = os.path.join(
                f"outputs/results/{course}", str(act), "json", f"{name}.json"
            )
        paths.append(path)
    return paths


def main():
    n_series = len(SERIES)
    n_sceneries = len(sceneries_names)

    all_counts = []
    for course, act in SERIES:
        paths = build_paths(SOURCE, course, act, sceneries_names)
        counts = []
        for name, path in zip(sceneries_names, paths):
            if not os.path.exists(path):
                print(f"[aviso] arquivo não encontrado: {path}")
                counts.append(0)
            else:
                counts.append(count_patterns(path))
        all_counts.append(counts)

    x = np.arange(n_sceneries)
    bar_width = 0.8 / n_series
    colors = [plt.get_cmap("tab10")(i) for i in range(10)]

    fig_height = max(10, n_sceneries * 0.45 * n_series)
    fig, ax = plt.subplots(figsize=(8, fig_height))

    for i, ((course, act), counts) in enumerate(zip(SERIES, all_counts)):
        label = f"Course {course} - Assignment {act}"
        label = label.replace("Course 2060", "Jobs and Salaries")
        label = label.replace("Course 2065", "Databases")

        offset = (i - n_series / 2 + 0.5) * bar_width
        bars = ax.barh(
            x + offset,
            counts,
            bar_width,
            label=label,
            color=colors[i % len(colors)],
            edgecolor="white",
        )
        max_count = max(max(c) for c in all_counts) if all_counts else 1
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(
                    bar.get_width() + max_count * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    str(count),
                    ha="left",
                    va="center",
                    fontsize=7,
                )

    ax.set_yticks(x)
    ax.set_yticklabels([str(i) for i in range(n_sceneries)], fontsize=9)
    ax.set_ylabel("Scenario", fontsize=11)
    ax.set_xlabel("Number of patterns", fontsize=11)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    ax.legend(fontsize=10)

    plt.tight_layout()

    series_str = "_".join(f"{c}a{a}" for c, a in SERIES)
    out_file = f"outputs/figures/patterns_per_scenario_{series_str}.png"
    os.makedirs("outputs/figures", exist_ok=True)
    plt.savefig(out_file, dpi=150)
    print(f"Gráfico salvo em: {out_file}")
    plt.show()


if __name__ == "__main__":
    main()
