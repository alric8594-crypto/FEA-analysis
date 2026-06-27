"""
Modal Analysis Parametric Sweep — FreeCAD 1.1 Macro
Run this via: Macro menu → Macros → modal_sweep.py → Execute
"""

import FreeCAD
import femmesh.gmshtools as gmshtools
from femtools import ccxtools
import os, csv, time

# ============================================================
# CONFIG
# ============================================================
WORK_DIR      = "C:/FEA_Modal"
CSV_FILE      = "C:/FEA_Modal/results.csv"
STEEL_DENSITY = 7.85e-9

EXCITATION_HZ = 50.0
SAFETY_MARGIN = 0.30
MIN_SAFE_HZ   = EXCITATION_HZ * (1 + SAFETY_MARGIN)  # 65 Hz

os.makedirs(WORK_DIR, exist_ok=True)

# ============================================================
# GET DOCUMENT OBJECTS
# ============================================================
doc      = FreeCAD.ActiveDocument
sheet    = doc.Spreadsheet
mesh_obj = doc.FEMMeshGmsh
analysis = doc.Analysis
solver   = doc.SolverCcxTools

# ============================================================
# PARAMETER RANGES
# TEST MODE (3 runs) — confirm pipeline works first
# ============================================================
plate_width_list        = [40, 50, 60]
upper_plate_height_list = [50]
lower_plate_slant_list  = [60]
thickness_list          = [6]

# FULL SWEEP (500 runs) — uncomment once test passes
# plate_width_list        = [40, 50, 60, 70]
# upper_plate_height_list = [50, 62, 75, 88, 100]
# lower_plate_slant_list  = [60, 70, 80, 90, 100]
# thickness_list          = [6, 8, 10, 12, 14]

# ============================================================
# HELPER: Set ALL parameters at once then recompute
# ============================================================
def set_all_params(pw, uph, lps, t):
    sheet.set("plate_width",       f"{pw} mm")
    sheet.set("upper_plate_hight", f"{uph} mm")
    sheet.set("lower_plate_slant", f"{lps} mm")
    sheet.set("thickness",         f"{t} mm")
    doc.recompute()
    doc.recompute()

    # Debug: read back actual values to confirm update
    print(f"  Spreadsheet check:")
    print(f"    plate_width       = {sheet.get('plate_width')}")
    print(f"    upper_plate_hight = {sheet.get('upper_plate_hight')}")
    print(f"    lower_plate_slant = {sheet.get('lower_plate_slant')}")
    print(f"    thickness         = {sheet.get('thickness')}")

# ============================================================
# HELPER: Parse .dat file for natural frequencies (Hz)
# ============================================================
def parse_frequencies(dat_file, num_modes=3):
    freqs = []
    if not os.path.exists(dat_file):
        print(f"  WARNING: .dat file not found: {dat_file}")
        return freqs

    with open(dat_file, "r") as f:
        lines = f.readlines()

    reading = False
    for line in lines:
        if "CYCLES/TIME" in line:
            reading = True
            continue
        if reading:
            parts = line.split()
            if len(parts) == 5:
                try:
                    int(parts[0])
                    freq_hz = float(parts[3])
                    freqs.append(freq_hz)
                    if len(freqs) >= num_modes:
                        break
                except:
                    pass
            elif len(parts) == 0:
                continue
            else:
                if len(freqs) > 0:
                    break

    return freqs

# ============================================================
# HELPER: Get mass from shape volume x steel density
# ============================================================
def get_mass_kg():
    try:
        body = doc.Body
        volume_mm3 = body.Shape.Volume
        mass_kg = volume_mm3 * STEEL_DENSITY
        return round(mass_kg, 6)
    except Exception as e:
        print(f"  WARNING: Could not get mass: {e}")
        return 0.0

# ============================================================
# HELPER: Remesh with Gmsh
# ============================================================
def remesh():
    gmsh_tool = gmshtools.GmshTools(mesh_obj)
    error = gmsh_tool.create_mesh()
    doc.recompute()
    return error

# ============================================================
# HELPER: Write .inp and run CalculiX
# ============================================================
def run_fea():
    try:
        fea = ccxtools.FemToolsCcx(analysis, solver)
        fea.update_objects()
        fea.setup_working_dir(WORK_DIR)
        fea.write_inp_file()
        fea.ccx_run()

        for name in ["FEMMeshGmsh.dat", "ccx_dat_file.dat", "ccx_dat_file"]:
            path = os.path.join(WORK_DIR, name)
            if os.path.exists(path):
                return path

        print("  WARNING: .dat file not found after run")
        return None
    except Exception as e:
        print(f"  ERROR in FEA run: {e}")
        return None

# ============================================================
# HELPER: Delete result objects after each run
# ============================================================
def cleanup_results():
    to_delete = []
    for obj in doc.Objects:
        if any(x in obj.Name for x in ["Results", "Pipeline", "EigenMode"]):
            to_delete.append(obj.Name)
    for name in to_delete:
        try:
            doc.removeObject(name)
        except:
            pass
    doc.recompute()

# ============================================================
# WRITE CSV HEADER
# ============================================================
with open(CSV_FILE, "w", newline="") as f:
    writer_csv = csv.writer(f)
    writer_csv.writerow([
        "plate_width_mm",
        "upper_plate_height_mm",
        "lower_plate_slant_mm",
        "thickness_mm",
        "mass_kg",
        "mode1_hz",
        "mode2_hz",
        "mode3_hz",
        "safe"
    ])

# ============================================================
# MAIN SWEEP LOOP
# ============================================================
run_count  = 0
pass_count = 0
fail_count = 0
total = (len(plate_width_list) * len(upper_plate_height_list) *
         len(lower_plate_slant_list) * len(thickness_list))

print(f"\n{'='*55}")
print(f"  Modal Sweep Starting — {total} total runs")
print(f"  Excitation freq : {EXCITATION_HZ} Hz")
print(f"  Min safe mode-1 : {MIN_SAFE_HZ:.1f} Hz")
print(f"{'='*55}\n")

start_time = time.time()

for pw in plate_width_list:
    for uph in upper_plate_height_list:
        for lps in lower_plate_slant_list:
            for t in thickness_list:

                run_count += 1
                print(f"\nRun {run_count}/{total} | "
                      f"width={pw} height={uph} slant={lps} thick={t}")

                # --- Step 1: Set all params ---
                try:
                    set_all_params(pw, uph, lps, t)
                except Exception as e:
                    print(f"  ERROR setting params: {e} — skipping")
                    fail_count += 1
                    continue

                # --- Step 2: Get mass ---
                mass = get_mass_kg()
                print(f"  Mass = {mass:.6f} kg")

                # --- Step 3: Remesh ---
                mesh_error = remesh()
                if mesh_error:
                    print(f"  WARNING: Mesh issue — {mesh_error}")

                # --- Step 4: Run FEA ---
                dat_file = run_fea()
                if dat_file is None:
                    print(f"  ERROR: FEA failed — skipping")
                    cleanup_results()
                    fail_count += 1
                    continue

                # --- Step 5: Parse frequencies ---
                freqs = parse_frequencies(dat_file, num_modes=3)
                if len(freqs) < 1:
                    print(f"  ERROR: No frequencies parsed")
                    print(f"  dat path: {dat_file}")
                    cleanup_results()
                    fail_count += 1
                    continue

                mode1 = freqs[0]
                mode2 = freqs[1] if len(freqs) > 1 else 0.0
                mode3 = freqs[2] if len(freqs) > 2 else 0.0
                safe  = 1 if mode1 > MIN_SAFE_HZ else 0

                print(f"  Mode1={mode1:.1f} Hz | "
                      f"Mode2={mode2:.1f} Hz | "
                      f"{'SAFE ✓' if safe else 'UNSAFE ✗'}")

                # --- Step 6: Write to CSV immediately ---
                with open(CSV_FILE, "a", newline="") as f:
                    writer_csv = csv.writer(f)
                    writer_csv.writerow([
                        pw, uph, lps, t,
                        mass,
                        round(mode1, 2),
                        round(mode2, 2),
                        round(mode3, 2),
                        safe
                    ])

                # --- Step 7: Cleanup ---
                cleanup_results()

                pass_count += 1

# ============================================================
# SUMMARY
# ============================================================
elapsed = time.time() - start_time
print(f"\n{'='*55}")
print(f"  Sweep complete!")
print(f"  Total runs     : {run_count}")
print(f"  Successful     : {pass_count}")
print(f"  Failed/skipped : {fail_count}")
print(f"  Time elapsed   : {elapsed/60:.1f} minutes")
print(f"  Results saved  : {CSV_FILE}")
print(f"{'='*55}\n")

# ============================================================
# BEST CANDIDATE PREVIEW
# ============================================================
try:
    results = []
    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["safe"]) == 1:
                results.append(row)

    if results:
        best = min(results, key=lambda r: float(r["mass_kg"]))
        print(f"  BEST DESIGN (lowest mass + safe):")
        print(f"  plate_width        = {best['plate_width_mm']} mm")
        print(f"  upper_plate_height = {best['upper_plate_height_mm']} mm")
        print(f"  lower_plate_slant  = {best['lower_plate_slant_mm']} mm")
        print(f"  thickness          = {best['thickness_mm']} mm")
        print(f"  mass               = {best['mass_kg']} kg")
        print(f"  mode1 frequency    = {best['mode1_hz']} Hz")
    else:
        print("  No safe designs found — consider relaxing safety margin.")
except Exception as e:
    print(f"  Could not preview results: {e}")
