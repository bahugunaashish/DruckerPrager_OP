# Streamlit web application

The app runs the existing single-element OpenSeesPy triaxial test and the desktop application's rule-based calibration in a browser.

## Run locally

Use Python 3.10–3.12, then from this repository directory:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Enter the properties in the sidebar, select either one simulation or calibration, and run. The app plots up to the ten most recent successful curves and provides CSV downloads. Calibration uses the desktop program's 1 kPa tolerance and 2–6% peak-strain criterion, parameter update rules and 0–1000 bounds, with a user-defined iteration limit. An iteration that fails to complete is not used as a successful result. The last successful parameters are displayed; they are calibrated only when convergence is reported. Each simulation runs in a separate process and temporary directory to avoid sharing OpenSees state and recorder files across sessions.

The original model uses the same input for confining pressure and the DruckerPrager material's atmospheric pressure argument. The app preserves this behavior. The rule-based search may not converge, and matching a peak alone does not establish that the complete stress–strain response is calibrated or validated. Review the model and results before engineering use.

## Deploy

For Streamlit Community Cloud, select this repository and branch and set the main file path to `app.py`. Installations for private repositories and OpenSeesPy platform support depend on the hosting environment. The app does not itself publish a site.
