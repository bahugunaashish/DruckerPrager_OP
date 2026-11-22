# Drucker–Prager Triaxial Optimizer

A Streamlit web application and a Tkinter desktop application for exploring Drucker–Prager hardening parameters using a single-element OpenSeesPy triaxial compression simulation. The calibration compares the simulated peak deviatoric stress with a Mohr–Coulomb target.

## Web app features

- Run one simulation or calibrate `Kinf`, `Ko`, and `δ₁` using the rule-based search.
- Set a peak axial strain range and absolute peak stress tolerance. Defaults are 2–6% and ±1 kPa.
- Set a maximum of 1–1,000 calibration iterations (default 25).
- View the stress–strain curves and the difference between peak and target stress by iteration.
- Download the last successful stress–strain curve and iteration history as CSV, and the input settings as JSON.

Calibration requires **both** criteria: the absolute peak stress difference is at most the selected tolerance, and peak strain lies within the selected range. The app reports when the iteration limit is reached without satisfying both conditions. A successful single simulation alone does not imply calibration.

## Run the Streamlit app locally

Use a compatible Python environment with OpenSeesPy installed. Python 3.10–3.12 is a suggested starting point.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, enter the soil and hardening properties, confining pressure, analysis settings, and calibration criteria. Choose **Calibrate hardening parameters** or **Run one simulation**, then select **Run analysis**.

For Streamlit Community Cloud, select this repository, the desired branch, and `app.py` as the main file. Deployment depends on the host supporting OpenSeesPy.

## Inputs and defaults

| Input | Symbol / key | Default | Units |
|---|---|---:|---|
| Young’s modulus | E | 50,000 | kPa |
| Poisson’s ratio | ν | 0.3 | — |
| Cohesion | c | 4.5 | kPa |
| Friction angle | φ | 35 | degrees |
| Confining pressure | p / `patm` | 100 | kPa |
| Mass density | `mDen` | 1.964 | Mg/m³ |
| Isotropic hardening | `Kinf` | 100 | kPa |
| Initial isotropic hardening | `Ko` | 20 | kPa |
| Isotropic hardening rate | δ₁ | 350 | — |
| Kinematic hardening | H | 500 | kPa |
| Hardening mix | θ | 0.3 | — |
| Tension softening | δ₂ | 0 | — |
| Maximum axial strain | `max_eps` | 15 | % |
| Displacement steps | `steps` | 1,000 | — |
| Maximum calibration iterations | `max_iter` | 25 | — |
| Minimum peak axial strain | `strain_min` | 2 | % |
| Maximum peak axial strain | `strain_max` | 6 | % |
| Peak stress tolerance | `stress_tolerance` | 1 | kPa |

The input `patm` is used both for the applied confining pressure and as the atmospheric pressure argument of the OpenSees DruckerPrager material. The last three convergence criteria and maximum iteration limit apply to the Streamlit calibration; the desktop application has fixed convergence criteria.

## Model and target

The simulation uses a 1 × 1 × 1 m cube, one 3D `SSPbrick` element, and the OpenSees `DruckerPrager` material. The model applies nodal loads, uses constraints on the cube boundaries, and controls axial displacement at node 5. Stress and strain are extracted from the element recorder.

The code derives material parameters from cohesion and friction angle:

```text
K      = E / [3(1 − 2ν)]
G      = E / [2(1 + ν)]
rho    = 2 sin(φ) / [√3 (3 − sin(φ))]
sigY   = 6 c cos(φ) / [√2 (3 − sin(φ))]
rhoBar = rho / 3
qf     = (c cot(φ) + p) × 2 sin(φ) / [1 − sin(φ)]
```

Here, `K` and `G` are bulk and shear moduli; `rho`, `sigY`, and `rhoBar` are arguments passed to the DruckerPrager material; `qf` is the theoretical target deviatoric stress; and `p` is the entered confining pressure.

## Calibration procedure

For each successful simulation, the app calculates `diff = q_peak − qf`. It checks both convergence criteria first. If they are not satisfied, it uses the following rules **in order**:

| Condition | Parameter update |
|---|---|
| `diff < 0` | Increase `Kinf` by 40, `Ko` by 2, and δ₁ by 10 |
| Otherwise, `diff > stress_tolerance` | Decrease `Kinf` by 20 and δ₁ by 10 |
| Otherwise, peak strain below the selected minimum | Decrease δ₁ by 25 and `Ko` by 2; increase `Kinf` by 5 |
| Otherwise, peak strain above the selected maximum | Increase δ₁ by 25 and `Ko` by 2; decrease `Kinf` by 5 |
| A simulation reports failure | Increase `Ko` by 5 and `Kinf` by 10, up to 1,000 |

After successful iterations, `Kinf`, `Ko`, and δ₁ are bounded between 0 and 1,000. The first rule also applies when `diff` is negative but its magnitude is within the stress tolerance and the strain criterion is not satisfied. This is a heuristic; convergence is not guaranteed.

## Results and files

The stress–strain plot displays up to the ten latest successful curves. The iteration plot displays signed peak stress differences; failed iterations are omitted. The displayed parameters correspond to the last successful simulation and are a calibrated result only if the app reports convergence.

Each web simulation runs in a separate process and temporary directory. Its recorder files are temporary; use the download buttons to retain the CSV and JSON results. A failed displacement step is treated as a failed web simulation.

## Desktop application

To use the Tkinter desktop version, install `openseespy`, `numpy`, and `matplotlib`, then run:

```bash
python main.py
```

The desktop application uses a fixed stress tolerance of 1 kPa and a fixed peak strain range of 2–6%, and its optimization loop has no user-specified iteration limit. It writes recorder files to `CTC_GUI_Output/` in the working directory. Its failure handling differs from the web app: it can process partial displacement-analysis results after a failed step.

## Project files

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface and calibration loop |
| `simulation.py` | Web app’s OpenSeesPy single-element simulation |
| `worker.py` | Isolated simulation process |
| `main.py` | Tkinter desktop application |
| `requirements.txt` | Web app dependencies |
| `STREAMLIT_README.md` | Web app quick-start guide |

## Limitations

- The search adjusts three hardening parameters using fixed increments and may not converge.
- Matching the peak stress and peak strain range does not validate the entire stress–strain response.
- Runtime depends on the iteration count, displacement steps, and solver behavior.
- Courier New is used when available; fallback fonts may appear on systems where it is not installed.

---

## Disclaimer

This software is provided **“as is”**, without warranty of any kind, express or implied, including warranties of accuracy, reliability, fitness for a particular purpose, or suitability for engineering design.

The application uses OpenSeesPy simulations and a rule-based procedure to estimate Drucker–Prager material parameters. The results depend on the input properties, model assumptions, numerical settings, and convergence behavior. A match to the specified peak stress and strain criteria does not guarantee that the complete soil response is accurately represented.

Users are responsible for verifying the inputs, assessing the suitability of the model, and independently reviewing and validating the results before using them in research, design, analysis, or other applications. The software is not a substitute for professional engineering judgment.

To the fullest extent permitted by applicable law, the author and contributors are not liable for any loss, damage, or consequences arising from the use of, inability to use, or reliance on this software or its results.

---

## License

The existing repository README states MIT licensing; consult the repository’s license file for the applicable license terms.

## Acknowledgements

- [OpenSeesPy](https://openseespydoc.readthedocs.io/)
- OpenSees Drucker–Prager material and SSPbrick element
