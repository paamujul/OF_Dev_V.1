"""
cluster level backtesting and analysis script.
loads the 6 synthetic cluster CSVs, computes statistical distributions,
and generates sub-plots for each cluster's key metrics.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings

warnings.filterwarnings("ignore")

csv_dir = "data/generated"
out_dir = "outputs/plots/clusters"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def plot_cluster(filename, title, cols_to_plot, output_name):
    path = os.path.join(csv_dir, filename)
    if not os.path.exists(path):
        print(f"Skipping {filename} - not found.")
        return

    df = pd.read_csv(path)
    
    # Calculate grid size based on number of columns
    n_cols = len(cols_to_plot)
    grid_cols = min(3, n_cols)
    grid_rows = (n_cols + grid_cols - 1) // grid_cols
    
    fig, axes = plt.subplots(grid_rows, grid_cols, figsize=(5 * grid_cols, 4 * grid_rows))
    fig.suptitle(title, fontsize=16, y=1.02)
    
    # Flatten axes for easy iteration
    if n_cols == 1:
        axes_flat = [axes]
    else:
        axes_flat = axes.flatten()
        
    for i, col in enumerate(cols_to_plot):
        if col in df.columns:
            ax = axes_flat[i]
            sns.histplot(df[col].dropna(), kde=True, ax=ax, color='steelblue', stat="density")
            ax.set_title(col.replace("_", " ").title())
            ax.set_xlabel("")
            ax.set_ylabel("Density")
            
            # Add mean line
            mean_val = df[col].mean()
            ax.axvline(mean_val, color='red', linestyle='--', label=f'Mean: {mean_val:.1f}')
            ax.legend()
            
    # Hide unused subplots
    for j in range(i + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)
        
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, output_name), bbox_inches='tight')
    plt.close()
    print(f"Saved {output_name}")

def run():
    print("Running Cluster-Level Backtesting Analysis...")
    ensure_dir(out_dir)

    clusters = [
        {
            "file": "cluster_1_autonomic_sleep.csv",
            "title": "Cluster 1: Autonomic & Sleep",
            "cols": ["hrv_rmssd", "resting_hr", "sleep_efficiency", "total_sleep_time", "deep_sleep_percent"],
            "out": "cluster_1_autonomic.png"
        },
        {
            "file": "cluster_2_hematology_iron.csv",
            "title": "Cluster 2: Hematology & Iron",
            "cols": ["rbc_count", "serum_ferritin", "tibc", "epo"],
            "out": "cluster_2_hematology.png"
        },
        {
            "file": "cluster_3_hormonal_metabolic.csv",
            "title": "Cluster 3: Hormonal & Metabolic",
            "cols": ["cortisol", "free_testosterone", "fasting_glucose", "fasting_insulin", "hba1c"],
            "out": "cluster_3_hormonal.png"
        },
        {
            "file": "cluster_4_inflammation.csv",
            "title": "Cluster 4: Inflammation",
            "cols": ["hscrp", "creatine_kinase"],
            "out": "cluster_4_inflammation.png"
        },
        {
            "file": "cluster_5_nutritional.csv",
            "title": "Cluster 5: Nutritional",
            "cols": ["vitamin_d"],
            "out": "cluster_5_nutritional.png"
        },
        {
            "file": "cluster_6_travel_env.csv",
            "title": "Cluster 6: Travel & Environment",
            "cols": ["tz_shift", "flight_duration", "dest_temp", "spo2_flight"],
            "out": "cluster_6_travel.png"
        }
    ]

    for c in clusters:
        plot_cluster(c["file"], c["title"], c["cols"], c["out"])

if __name__ == "__main__":
    run()
