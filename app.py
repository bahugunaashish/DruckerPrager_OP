"""Streamlit interface for the repository's Drucker–Prager triaxial test."""
import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Drucker–Prager calibration', page_icon='🧱', layout='wide')
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
[data-testid="stAppViewContainer"] *, [data-testid="stSidebar"] * {
    font-family: "Courier New", Courier, monospace !important;
}
</style>
""", unsafe_allow_html=True)
plt.rcParams["font.family"] = ["Courier New", "Liberation Mono", "DejaVu Sans Mono"]
st.title('Drucker–Prager triaxial calibration')
st.caption('Single 3D SSPbrick · OpenSeesPy · Units: kPa, m, Mg/m³')

with st.sidebar:
    st.header('Model inputs')
    with st.form('inputs'):
        st.subheader('Soil properties')
        E = st.number_input("Young’s modulus E (kPa)", min_value=0.01, value=50000.0)
        nu = st.number_input('Poisson’s ratio ν', min_value=0.0, max_value=0.499, value=0.3, format='%.3f')
        c = st.number_input('Cohesion c (kPa)', min_value=0.0, value=4.5)
        phi = st.number_input('Friction angle φ (degrees)', min_value=0.01, max_value=89.99, value=35.0)
        patm = st.number_input('Confining pressure p (kPa)', min_value=0.01, value=100.0, help='Also passed as the OpenSees material atmospheric pressure, as in the original model.')
        mDen = st.number_input('Mass density (Mg/m³)', min_value=0.0, value=1.964, format='%.3f')
        st.subheader('Hardening parameters')
        Kinf = st.number_input('Kinf (kPa)', min_value=0.0, max_value=1000.0, value=100.0)
        Ko = st.number_input('Ko (kPa)', min_value=0.0, max_value=1000.0, value=20.0)
        delta1 = st.number_input('δ₁', min_value=0.0, max_value=1000.0, value=350.0)
        H = st.number_input('Kinematic hardening H (kPa)', min_value=0.0, value=500.0)
        theta = st.number_input('Hardening mix θ', min_value=0.0, max_value=1.0, value=0.3)
        delta2 = st.number_input('Tension softening δ₂', min_value=0.0, value=0.0)
        st.subheader('Analysis settings')
        max_eps = st.number_input('Maximum axial strain (%)', min_value=0.01, max_value=100.0, value=15.0)
        steps = st.number_input('Displacement steps', min_value=1, max_value=10000, value=1000, step=100)
        mode = st.selectbox('Run mode', ['Calibrate hardening parameters', 'Run one simulation'])
        max_iter = st.number_input('Maximum calibration iterations', min_value=1, max_value=1000, value=25, help='Calibration stops at this limit if no match is found.')
        run = st.form_submit_button('Run analysis', type='primary', use_container_width=True)

params = dict(E=E, nu=nu, c=c, phi=phi, patm=patm, mDen=mDen, Kinf=Kinf, Ko=Ko, delta1=delta1, H=H, theta=theta, delta2=delta2, max_eps=max_eps, steps=steps)
sin_phi = math.sin(math.radians(phi))
qf = (c / math.tan(math.radians(phi)) + patm) * 2 * sin_phi / (1 - sin_phi)
st.info(f'Mohr–Coulomb target peak: **{qf:.2f} kPa**. Calibration requires a stress difference ≤ 1 kPa and a peak strain between 2% and 6%.')

if run:
    history, curves = [], []
    placeholder = st.empty()
    progress = st.progress(0, text='Starting analysis')
    status = 'Iteration limit reached without satisfying both calibration criteria.'
    limit = int(max_iter) if mode.startswith('Calibrate') else 1
    for iteration in range(1, limit + 1):
        progress.progress((iteration-1)/limit, text=f'Running iteration {iteration} of {limit}…')
        try:
            process = subprocess.run([sys.executable, str(Path(__file__).with_name('worker.py'))], input=json.dumps(params), text=True, capture_output=True, timeout=300)
            if process.returncode:
                raise RuntimeError(process.stderr.strip()[-1500:] or 'Simulation process failed.')
            result = json.loads(process.stdout.strip().splitlines()[-1])
        except (subprocess.TimeoutExpired, ValueError, RuntimeError, IndexError) as exc:
            status = f'Analysis stopped: {exc}'
            break
        row = dict(iteration=iteration, Kinf=params['Kinf'], Ko=params['Ko'], delta1=params['delta1'])
        if not result['success']:
            row.update(peak_kPa=None, peak_strain_pct=None, difference_kPa=None, status='Analysis failed')
            history.append(row)
            if mode == 'Run one simulation':
                status = 'Simulation failed. Check the inputs and try again.'
                break
            params['Ko'] = min(params['Ko'] + 5, 1000)
            params['Kinf'] = min(params['Kinf'] + 10, 1000)
            continue
        peak, strain = result['peak'], result['peak_strain']
        diff = peak - qf
        row.update(peak_kPa=peak, peak_strain_pct=strain, difference_kPa=diff, status='Completed')
        history.append(row)
        curves.append((iteration, result))
        with placeholder.container():
            st.write(f'Completed iteration {iteration}: peak **{peak:.2f} kPa** at **{strain:.2f}%** strain; difference from target **{diff:+.2f} kPa**.')
        if mode == 'Run one simulation':
            status = 'Single simulation completed.'
            break
        if abs(diff) <= 1 and 2 <= strain <= 6:
            status = f'Calibration converged at iteration {iteration}.'
            break
        # Same rule ordering and increments as the desktop application.
        if diff < 0:
            params['Kinf'] += 40; params['Ko'] += 2; params['delta1'] += 10
        elif diff > 1:
            params['Kinf'] -= 20; params['delta1'] -= 10
        elif strain < 2:
            params['delta1'] -= 25; params['Ko'] -= 2; params['Kinf'] += 5
        elif strain > 6:
            params['delta1'] += 25; params['Ko'] += 2; params['Kinf'] -= 5
        for key in ('Kinf', 'Ko', 'delta1'):
            params[key] = max(0.0, min(params[key], 1000.0))
    progress.progress(1.0, text='Analysis finished')
    st.session_state['results'] = dict(status=status, history=history, curves=curves, qf=qf, inputs=dict(E=E, nu=nu, c=c, phi=phi, patm=patm, mDen=mDen, Kinf=Kinf, Ko=Ko, delta1=delta1, H=H, theta=theta, delta2=delta2, max_eps=max_eps, steps=steps), mode=mode)

if 'results' in st.session_state:
    data = st.session_state['results']
    if data['status'].startswith(('Calibration converged', 'Single simulation completed')):
        st.success(data['status'])
    else:
        st.warning(data['status'])
    if data['curves']:
        iteration, last = data['curves'][-1]
        used = next(row for row in data['history'] if row['iteration'] == iteration)
        a,b,c1 = st.columns(3)
        a.metric('Last successful peak', f"{last['peak']:.2f} kPa")
        b.metric('Peak axial strain', f"{last['peak_strain']:.2f}%")
        c1.metric('Difference from target', f"{last['peak'] - data['qf']:+.2f} kPa")
        st.caption(f"Last successful parameters: Kinf = {used['Kinf']:.2f} kPa, Ko = {used['Ko']:.2f} kPa, δ₁ = {used['delta1']:.2f}")
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for it, curve in data['curves'][-10:]:
            ax.plot(curve['strain'], curve['stress'], alpha=1 if it == iteration else .35, linewidth=2 if it == iteration else 1, label=f'Iteration {it}')
        ax.axhline(data['qf'], color='#cc4b4b', linestyle='--', label='Mohr–Coulomb target')
        ax.set(xlabel='Axial strain (%)', ylabel='Deviatoric stress (kPa)')
        ax.grid(alpha=.2); ax.legend(fontsize=8); fig.tight_layout()
        st.pyplot(fig); plt.close(fig)
        curve_df = pd.DataFrame({'axial_strain_pct': last['strain'], 'deviatoric_stress_kPa': last['stress']})
        st.download_button('Download last stress–strain curve (CSV)', curve_df.to_csv(index=False).encode(), 'stress_strain.csv', 'text/csv')
    if data['history']:
        st.subheader('Iteration history')
        table = pd.DataFrame(data['history'])
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button('Download iteration history (CSV)', table.to_csv(index=False).encode(), 'calibration_history.csv', 'text/csv')
        st.download_button('Download run inputs (JSON)', json.dumps(data['inputs'], indent=2), 'run_inputs.json', 'application/json')
else:
    st.subheader('Set your soil properties and run the analysis')
    st.write('Choose a single simulation to inspect one stress–strain curve, or calibrate Kinf, Ko and δ₁ against the target.')
    st.caption('The calibration uses the original rule-based update scheme; convergence is not guaranteed.')
