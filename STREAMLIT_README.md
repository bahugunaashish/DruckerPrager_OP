# Streamlit web application

See the main [README](README.md) for model details, input definitions, calibration rules, and the disclaimer.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Select **Run one simulation** or **Calibrate hardening parameters**. For calibration, set the peak axial strain range, peak stress tolerance, and maximum iteration count. The defaults are 2–6%, ±1 kPa, and 25 iterations; the maximum selectable iteration count is 1,000. A successful calibration must meet both stress and strain criteria.

The app shows the latest successful stress–strain curves and the peak stress difference by iteration. Download the last successful curve and iteration history as CSV and input settings as JSON. A successful result is calibrated only when convergence is reported.

For Streamlit Community Cloud, select this repository, the intended branch, and `app.py` as the main file. OpenSeesPy must be supported by the deployment environment.
