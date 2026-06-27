# Vibration-Aware Bracket Design — Automated FEA + ML Surrogate

## What this project does
Automated parametric modal analysis pipeline to find the 
minimum-mass bracket design that maintains safe natural 
frequency separation from a 50Hz motor excitation.

## Pipeline
FreeCAD parametric CAD → Python automation → 500x CalculiX 
FEA simulations → Random Forest surrogate model (R²=0.984) 
→ 10,000 candidate design space search → optimal design

## Key findings
- Slant length dominates natural frequency (73.5% importance)
- Thickness is secondary driver (24.2%)
- Optimal design: 41mm wide, 52mm tall, 65mm slant, 6.8mm thick

## Tools used
FreeCAD, CalculiX, Python, scikit-learn, matplotlib, pandas

## Files
- modal_sweep.py — FreeCAD macro for automated FEA sweep
- RamdomForestRegresor-optimizer.py — surrogate model + optimization
- results.csv — 500 FEA simulation results
- surrogate_analysis.png — results visualization
