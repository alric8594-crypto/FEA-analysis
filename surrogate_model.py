"""
Surrogate Model + Optimization
Modal Analysis Bracket Design Study

Steps:
1. Load and clean the FEA results
2. Train a Random Forest surrogate model
3. Evaluate model accuracy
4. Find the optimal design (lowest mass, mode1 > 65 Hz)
5. Generate plots for portfolio
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# STEP 1 — LOAD AND CLEAN DATA
# ============================================================
df = pd.read_csv("C:/FEA_Modal/results.csv")
print(f"Total rows loaded: {len(df)}")

# Remove duplicate rows — caused by FreeCAD parameter lag
# A duplicate row has identical frequencies to the previous row
df = df.drop_duplicates(subset=["mode1_hz", "mode2_hz", "mode3_hz"])
print(f"Rows after removing duplicates: {len(df)}")

# Remove rows where mass didn't update (all same mass as prev group)
# These are rows where frequencies are clearly wrong for the given params
# Simple filter: remove rows where mode1_hz seems unreasonably high
# given mass (ratio check)
df = df[df["mass_kg"] > 0.0001]  # remove near-zero mass rows if any
print(f"Rows after mass filter: {len(df)}")

# Features and targets
features = ["plate_width_mm", "upper_plate_height_mm",
            "lower_plate_slant_mm", "thickness_mm"]
X = df[features].values
y_mode1 = df["mode1_hz"].values
y_mass  = df["mass_kg"].values

print(f"\nFeature ranges:")
for i, f in enumerate(features):
    print(f"  {f}: {X[:,i].min():.1f} — {X[:,i].max():.1f}")
print(f"\nMode1 range: {y_mode1.min():.1f} — {y_mode1.max():.1f} Hz")
print(f"Mass range:  {y_mass.min():.6f} — {y_mass.max():.6f} kg")

# ============================================================
# STEP 2 — TRAIN SURROGATE MODEL
# ============================================================
X_train, X_test, \
y_mode1_train, y_mode1_test, \
y_mass_train, y_mass_test = train_test_split(
    X, y_mode1, y_mass, test_size=0.2, random_state=42)

# Random Forest — better than linear regression for this nonlinear problem
model_mode1 = RandomForestRegressor(n_estimators=100, random_state=42)
model_mass  = RandomForestRegressor(n_estimators=100, random_state=42)

model_mode1.fit(X_train, y_mode1_train)
model_mass.fit(X_train, y_mass_train)

# ============================================================
# STEP 3 — EVALUATE MODEL ACCURACY
# ============================================================
pred_mode1 = model_mode1.predict(X_test)
pred_mass  = model_mass.predict(X_test)

mae_mode1 = mean_absolute_error(y_mode1_test, pred_mode1)
r2_mode1  = r2_score(y_mode1_test, pred_mode1)
mae_mass  = mean_absolute_error(y_mass_test, pred_mass)
r2_mass   = r2_score(y_mass_test, pred_mass)

print(f"\n{'='*50}")
print(f"  Surrogate Model Accuracy")
print(f"{'='*50}")
print(f"  Mode1 frequency:")
print(f"    MAE : {mae_mode1:.1f} Hz")
print(f"    R²  : {r2_mode1:.4f}")
print(f"  Mass:")
print(f"    MAE : {mae_mass:.8f} kg")
print(f"    R²  : {r2_mass:.4f}")

# Feature importance
print(f"\n  Feature importance (mode1 frequency):")
for name, imp in zip(features, model_mode1.feature_importances_):
    print(f"    {name}: {imp*100:.1f}%")

# ============================================================
# STEP 4 — FIND OPTIMAL DESIGN
# Use surrogate to search a large design space (10000 candidates)
# Then pick the lowest mass design that stays above 65 Hz
# ============================================================
EXCITATION_HZ = 50.0
SAFETY_MARGIN = 0.30
MIN_SAFE_HZ   = EXCITATION_HZ * (1 + SAFETY_MARGIN)  # 65 Hz

# Generate 10000 random candidate designs within parameter bounds
np.random.seed(42)
n_candidates = 10000
candidates = np.column_stack([
    np.random.uniform(40, 70,   n_candidates),  # plate_width
    np.random.uniform(50, 100,  n_candidates),  # upper_plate_height
    np.random.uniform(60, 100,  n_candidates),  # lower_plate_slant
    np.random.uniform(6,  14,   n_candidates),  # thickness
])

# Predict mode1 and mass for all candidates
pred_mode1_cands = model_mode1.predict(candidates)
pred_mass_cands  = model_mass.predict(candidates)

# Filter: keep only safe designs (mode1 > MIN_SAFE_HZ)
safe_mask = pred_mode1_cands > MIN_SAFE_HZ
safe_candidates  = candidates[safe_mask]
safe_mode1       = pred_mode1_cands[safe_mask]
safe_mass        = pred_mass_cands[safe_mask]

print(f"\n{'='*50}")
print(f"  Optimization Results")
print(f"{'='*50}")
print(f"  Total candidates:  {n_candidates}")
print(f"  Safe candidates:   {safe_mask.sum()} ({safe_mask.mean()*100:.1f}%)")

if len(safe_candidates) > 0:
    # Pick lowest mass among safe designs
    best_idx  = np.argmin(safe_mass)
    best_params = safe_candidates[best_idx]
    best_mode1  = safe_mode1[best_idx]
    best_mass   = safe_mass[best_idx]

    print(f"\n  OPTIMAL DESIGN (surrogate prediction):")
    print(f"  plate_width        = {best_params[0]:.1f} mm")
    print(f"  upper_plate_height = {best_params[1]:.1f} mm")
    print(f"  lower_plate_slant  = {best_params[2]:.1f} mm")
    print(f"  thickness          = {best_params[3]:.1f} mm")
    print(f"  predicted mass     = {best_mass:.6f} kg")
    print(f"  predicted mode1    = {best_mode1:.1f} Hz")
    print(f"  safety margin      = {(best_mode1/EXCITATION_HZ - 1)*100:.1f}% above excitation")
else:
    print("  No safe designs found in candidate space.")

# ============================================================
# STEP 5 — PLOTS
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Modal Analysis Surrogate Model — Bracket Design Study",
             fontsize=14, fontweight='bold')

# --- Plot 1: Predicted vs Actual (mode1 frequency) ---
ax1 = axes[0, 0]
ax1.scatter(y_mode1_test, pred_mode1, alpha=0.6, color='steelblue', s=20)
lims = [min(y_mode1_test.min(), pred_mode1.min()),
        max(y_mode1_test.max(), pred_mode1.max())]
ax1.plot(lims, lims, 'r--', linewidth=1.5, label='Perfect prediction')
ax1.set_xlabel("Actual Mode 1 Frequency (Hz)")
ax1.set_ylabel("Predicted Mode 1 Frequency (Hz)")
ax1.set_title(f"Surrogate Accuracy — Mode 1\nR² = {r2_mode1:.3f}, MAE = {mae_mode1:.1f} Hz")
ax1.legend()
ax1.grid(True, alpha=0.3)

# --- Plot 2: Mass vs Mode1 (all data, colored by safe/unsafe) ---
ax2 = axes[0, 1]
safe_data   = df[df["safe"] == 1]
unsafe_data = df[df["safe"] == 0]
ax2.scatter(safe_data["mass_kg"]*1000, safe_data["mode1_hz"],
            alpha=0.5, color='green', s=15, label='Safe ✓')
ax2.scatter(unsafe_data["mass_kg"]*1000, unsafe_data["mode1_hz"],
            alpha=0.5, color='red', s=15, label='Unsafe ✗')
ax2.axhline(y=MIN_SAFE_HZ, color='orange', linestyle='--',
            linewidth=2, label=f'Min safe freq ({MIN_SAFE_HZ:.0f} Hz)')
# Mark excitation zone
ax2.axhspan(EXCITATION_HZ*0.7, EXCITATION_HZ*1.3,
            alpha=0.1, color='red', label='Danger zone ±30%')
if len(safe_candidates) > 0:
    ax2.scatter(best_mass*1000, best_mode1, color='gold', s=200,
                zorder=5, marker='*', label='Optimal design')
ax2.set_xlabel("Mass (grams)")
ax2.set_ylabel("Mode 1 Frequency (Hz)")
ax2.set_title("Mass vs Natural Frequency\n(Design Space Overview)")
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

# --- Plot 3: Feature importance ---
ax3 = axes[1, 0]
importances = model_mode1.feature_importances_
feat_labels = ["Plate\nWidth", "Plate\nHeight", "Slant\nLength", "Thickness"]
colors = ['steelblue', 'coral', 'mediumseagreen', 'mediumpurple']
bars = ax3.bar(feat_labels, importances * 100, color=colors, edgecolor='white')
ax3.set_ylabel("Importance (%)")
ax3.set_title("Parameter Importance\n(Effect on Mode 1 Frequency)")
ax3.grid(True, alpha=0.3, axis='y')
for bar, val in zip(bars, importances):
    ax3.text(bar.get_x() + bar.get_width()/2,
             bar.get_height() + 0.5,
             f'{val*100:.1f}%', ha='center', fontsize=10)

# --- Plot 4: Thickness vs Mode1 for different plate widths ---
ax4 = axes[1, 1]
colors_pw = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
for i, pw in enumerate([40, 50, 60, 70]):
    subset = df[df["plate_width_mm"] == pw]
    if len(subset) > 0:
        ax4.scatter(subset["thickness_mm"], subset["mode1_hz"],
                    alpha=0.6, color=colors_pw[i], s=20,
                    label=f'Width={pw}mm')
ax4.axhline(y=MIN_SAFE_HZ, color='orange', linestyle='--',
            linewidth=2, label=f'Min safe ({MIN_SAFE_HZ:.0f} Hz)')
ax4.set_xlabel("Thickness (mm)")
ax4.set_ylabel("Mode 1 Frequency (Hz)")
ax4.set_title("Thickness vs Mode 1 Frequency\nby Plate Width")
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("C:/FEA_Modal/surrogate_analysis.png", dpi=150, bbox_inches='tight')
plt.show()
print("\nPlot saved to C:/FEA_Modal/surrogate_analysis.png")
print("\nDone!")
