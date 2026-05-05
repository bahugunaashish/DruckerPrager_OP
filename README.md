# 🪨 Drucker-Prager Autonomous Triaxial Optimizer

A desktop application for automated calibration of **Drucker-Prager elastoplastic constitutive model** parameters using 3D finite element simulation via **OpenSeesPy**. The tool iteratively adjusts hardening parameters until the simulated deviatoric stress peak matches the Mohr-Coulomb theoretical failure criterion.

---

## 📸 Overview

The application simulates a **Consolidated Drained (CD) Triaxial Compression Test** on a single 3D `SSPbrick` finite element and autonomously drives the peak deviatoric stress to match the theoretical Mohr-Coulomb failure envelope — all within an interactive GUI.

---

## ✨ Features

- **Autonomous optimization loop** — iteratively calibrates Drucker-Prager hardening parameters with no manual intervention
- **Live interactive plot** — deviatoric stress vs. axial strain curve updates in real time each iteration, with a Matplotlib navigation toolbar for zoom and pan
- **Mohr-Coulomb reference line** — theoretical failure stress `qf` displayed as a dashed red benchmark line
- **Convergence criteria** — stops when simulated peak stress is within ±1 kPa of `qf` *and* peak strain falls between 2% and 6%
- **Native Tkinter GUI** — no browser or external UI framework required; runs on Windows, macOS, and Linux
- **Hover tooltips** — parameter hints on every input field
- **Live parameter updates** — GUI entry fields update in real time as the optimizer adjusts values
- **Scrollable parameter panel** — clean layout with mouse-wheel support
- **Output logging** — per-iteration diagnostics logged to an in-app console

---

## 🧱 Model Details

| Property | Value |
|---|---|
| FE Software | OpenSeesPy |
| Element Type | `SSPbrick` (3D stabilized single-point) |
| Constitutive Model | `DruckerPrager` nDMaterial |
| Test Type | Consolidated Drained Triaxial Compression |
| Geometry | 1×1×1 m single-element cube |
| Loading | Displacement-controlled axial compression |
| Confining Pressure | Applied as nodal loads on all faces |

### Coordinate System & BCs

- **Z-axis**: axial loading direction (vertical)
- Bottom face: fully fixed in Z; edge and corner nodes fixed in X or Y for symmetry
- Lateral faces: confining pressure applied as nodal loads via a `Plain` load pattern
- Top nodes: displacement-controlled via `DisplacementControl` integrator

### Drucker-Prager Conversion from Mohr-Coulomb

The material parameters `rho`, `sigY`, and `rhoBar` are derived analytically from the Mohr-Coulomb `c` and `φ`:

```
sin_phi  = sin(φ)
cos_phi  = cos(φ)
rho      = 2·sin_phi / (√3 · (3 − sin_phi))
sigY     = 6·c·cos_phi / (√2 · (3 − sin_phi))
rhoBar   = rho / 3
```

### Theoretical Peak Stress (Mohr-Coulomb)

```
qf = (c·cot(φ) + p₀) · 2·sin(φ) / (1 − sin(φ))
```

where `p₀` is the confining pressure.

---

## ⚙️ Parameters

| Label | Key | Default | Description |
|---|---|---|---|
| Young's Modulus E [kPa] | `E` | 50000 | Elastic modulus |
| Poisson's Ratio ν | `nu` | 0.3 | Range: 0 – 0.49 |
| Cohesion c [kPa] | `c` | 4.5 | Effective cohesion |
| Friction Angle φ [°] | `phi` | 35 | Internal friction angle |
| Isotropic Hard. Kinf [kPa] | `Kinf` | 222 | Maximum isotropic hardening (max 1000) |
| Isotropic Hard. Ko [kPa] | `Ko` | 20 | Initial isotropic hardening (max 1000) |
| δ₁ (hardening rate) | `delta1` | 200 | Isotropic hardening rate (max 1000) |
| Kinematic Hard. H [kPa] | `H` | 500 | Kinematic hardening modulus ≥ 0 |
| θ (hardening mix) | `theta` | 0.2 | 0 = pure kinematic, 1 = pure isotropic |
| δ₂ (tension softening) | `delta2` | 0 | Tension softening parameter |
| Mass Density ρ [Mg/m³] | `mDen` | 1.964 | Bulk mass density |
| Confining Pressure p [kPa] | `patm` | 100 | Hydrostatic confining pressure |
| Max Axial Strain [%] | `max_eps` | 15 | Target axial strain |
| Analysis Steps | `steps` | 1000 | Displacement-control steps |

### Optimization Target Parameters

The loop autonomously adjusts **`Kinf`**, **`Ko`**, and **`δ₁`** only. All other parameters are user-controlled and held fixed during calibration.

---

## 🔄 Optimization Algorithm

The optimizer runs a feedback loop comparing the simulated peak deviatoric stress `q_peak` to the Mohr-Coulomb theoretical value `qf`:

```
diff = q_peak − qf
```

**Adjustment logic per iteration:**

| Condition | Action |
|---|---|
| `diff < 0` (undershoot) | Increase `Kinf` (+40), `Ko` (+2), `δ₁` (+10) |
| `diff > tolerance` (overshoot) | Decrease `Kinf` (−20), `δ₁` (−10) |
| Stress OK, strain < 2% | Decrease `δ₁` (−25), `Ko` (−2); increase `Kinf` (+5) |
| Stress OK, strain > 6% | Increase `δ₁` (+25), `Ko` (+2); decrease `Kinf` (−5) |
| Simulation failure | Increase `Ko` (+5), `Kinf` (+10) for stability |

All three parameters are clamped to `[0, 1000]` after every update. The plot is cleared every 25 iterations to maintain readability.

**Convergence** is declared when:
- `|q_peak − qf| ≤ 1.0 kPa`, **AND**
- `2.0% ≤ peak_strain ≤ 6.0%`

---

## 🗂️ Output Files

All simulation outputs are written to `CTC_GUI_Output/` in the working directory:

| File | Contents |
|---|---|
| `stress1.out` | Element stress tensor per step (time + 6 components) |
| `strain1.out` | Element strain tensor per step (time + 6 components) |
| `displacements1.out` | Node 5 Z-displacement vs time |
| `displacements2.out` | Node 1 Z-displacement vs time |
| `MultiCTCsim-2.pvd/` | ParaView-compatible PVD folder for 3D visualization |

---

## 🚀 Getting Started

### Prerequisites

```bash
pip install openseespy numpy matplotlib
```

Python 3.8+ is recommended. Tkinter is included with most Python distributions.

### Running the App

```bash
python drucker_prager_optimizer.py
```

### Typical Workflow

1. Set your soil's elastic and strength parameters (`E`, `ν`, `c`, `φ`)
2. Set the confining pressure (`patm`) matching your lab test
3. Leave hardening parameters at defaults or provide an initial estimate
4. Click **Run Autonomous Loop**
5. Watch the optimizer iterate — the plot and log update live
6. When convergence is reached, read the calibrated `Kinf`, `Ko`, `δ₁` values from the input panel

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `openseespy` | 3D finite element solver |
| `numpy` | Numerical operations and output parsing |
| `matplotlib` | Interactive stress-strain plot |
| `tkinter` | Native GUI (stdlib) |

---

## 📁 Project Structure

```
drucker-prager-optimizer/
│
├── drucker_prager_optimizer.py   # Main application (single file)
├── README.md
│
└── CTC_GUI_Output/               # Auto-created at runtime
    ├── stress1.out
    ├── strain1.out
    ├── displacements1.out
    ├── displacements2.out
    └── MultiCTCsim-2.pvd/
```

---

## 🧪 Validation

The tool targets the **Mohr-Coulomb failure surface** as the theoretical benchmark. For a triaxial test under confining pressure `p₀`:

```
qf = (c·cot(φ) + p₀) · 2·sin(φ) / (1 − sin(φ))
```

The Drucker-Prager model's yield surface is matched to the Mohr-Coulomb surface at triaxial compression using the standard inscribed-circle conversion.

---

## ⚠️ Known Limitations

- Optimization parameters (`Kinf`, `Ko`, `δ₁`) are clamped at 1000 kPa — soils requiring values above this need manual adjustment
- The algorithm uses a simple rule-based heuristic, not gradient-based optimization; convergence is not mathematically guaranteed for all input combinations
- Each iteration runs a full FE simulation; runtime depends on the number of steps (default 1000)
- PVD recorder output may silently fail on some systems but does not affect results

---

## 📄 License

MIT License — free to use, modify, and distribute with attribution.

---

## 🙏 Acknowledgements

- [OpenSeesPy](https://openseespydoc.readthedocs.io/) — open-source finite element framework
- Drucker-Prager `nDMaterial` implementation in OpenSees — UC Berkeley PEER
- `SSPbrick` element — Stabilized Single-Point brick for improved volumetric response
