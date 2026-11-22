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
[data-testid="stAppViewContainer"] *:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]):not([class*="material-icons"]),
[data-testid="stSidebar"] *:not([data-testid="stIconMaterial"]):not([class*="material-symbols"]):not([class*="material-icons"]) {
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
        patm = st.number_input('Confining pressure p (kPa)', min_value=0.01, value=100.0, help='Confining pressure at which the test is conducted.')
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
        st.subheader('Calibration criteria')
        strain_min = st.number_input('Minimum peak axial strain (%)', min_value=0.0, value=2.0, step=0.1)
        strain_max = st.number_input('Maximum peak axial strain (%)', min_value=0.0, value=6.0, step=0.1)
        stress_tolerance = st.number_input('Peak stress tolerance (kPa)', min_value=0.0, value=1.0, step=0.1, help='Maximum absolute difference between simulated peak stress and the target.')
        run = st.form_submit_button('Run analysis', type='primary', use_container_width=True)

def draw_stress_strain_chart(curves, target):
    """Display the most recent successful curves and the target stress."""
    if not curves:
        return
    latest_iteration = curves[-1][0]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for it, curve in curves[-10:]:
        ax.plot(curve['strain'], curve['stress'],
                alpha=1 if it == latest_iteration else .35,
                linewidth=2 if it == latest_iteration else 1,
                label=f'Iteration {it}')
    ax.axhline(target, color='#cc4b4b', linestyle='--', label='Mohr–Coulomb target')
    ax.set(xlabel='Axial strain (%)', ylabel='Deviatoric stress (kPa)')
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def draw_error_chart(history, tolerance):
    """Plot signed stress difference for each successfully completed iteration."""
    successful = [row for row in history if row.get('difference_kPa') is not None]
    if not successful:
        return
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot([row['iteration'] for row in successful],
            [row['difference_kPa'] for row in successful], marker='o', markersize=3, linewidth=1.4)
    ax.axhline(0, color='#333333', linewidth=0.9)
    ax.axhspan(-tolerance, tolerance, color='#45a36b', alpha=0.18, label=f'Stress tolerance ±{tolerance:g} kPa')
    ax.set(xlabel='Iteration', ylabel='Peak stress − target stress (kPa)')
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def draw_hardening_chart(history):
    """Show the parameters used in each attempted iteration."""
    if not history:
        return
    iterations = [row['iteration'] for row in history]
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True)
    for ax, (key, label, color) in zip(axes, [
        ('Kinf', 'Kinf (kPa)', '#2563a6'),
        ('Ko', 'Ko (kPa)', '#d07828'),
        ('delta1', 'δ₁', '#27805c'),
    ]):
        values = [row[key] for row in history]
        ax.plot(iterations, values, color=color, marker='o', markersize=2.5, linewidth=1.2)
        failed = [row for row in history if row['status'] == 'Analysis failed']
        if failed:
            ax.scatter([row['iteration'] for row in failed], [row[key] for row in failed],
                       marker='x', color='#bd3131', s=30, zorder=3, label='Failed analysis')
            ax.legend(fontsize=8)
        ax.set_ylabel(label)
        ax.grid(alpha=.2)
    axes[-1].set_xlabel('Iteration')
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


params = dict(E=E, nu=nu, c=c, phi=phi, patm=patm, mDen=mDen, Kinf=Kinf, Ko=Ko, delta1=delta1, H=H, theta=theta, delta2=delta2, max_eps=max_eps, steps=steps)
sin_phi = math.sin(math.radians(phi))
qf = (c / math.tan(math.radians(phi)) + patm) * 2 * sin_phi / (1 - sin_phi)
st.info(f'Mohr–Coulomb target peak: **{qf:.2f} kPa**. Calibration requires an absolute stress difference ≤ {stress_tolerance:g} kPa and a peak strain from {strain_min:g}% to {strain_max:g}%.')

if run and mode.startswith('Calibrate') and strain_min > strain_max:
    st.error('Minimum peak strain must not exceed maximum peak strain.')
    run = False
if run and mode.startswith('Calibrate') and strain_min > max_eps:
    st.warning('The minimum peak strain is greater than the maximum axial strain setting; the requested range may not be reached.')

if run:
    history, curves = [], []
    placeholder = st.empty()
    stress_placeholder = st.empty()
    error_placeholder = st.empty()
    hardening_placeholder = st.empty()
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
            if mode.startswith('Calibrate'):
                with hardening_placeholder.container():
                    st.subheader('Hardening parameters by iteration')
                    draw_hardening_chart(history)
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
        with stress_placeholder.container():
            st.subheader('Stress–strain response')
            draw_stress_strain_chart(curves, qf)
        with placeholder.container():
            st.write(f'Completed iteration {iteration}: peak **{peak:.2f} kPa** at **{strain:.2f}%** strain; difference from target **{diff:+.2f} kPa**.')
        if mode.startswith('Calibrate'):
            with error_placeholder.container():
                st.subheader('Stress difference by iteration')
                draw_error_chart(history, stress_tolerance)
            with hardening_placeholder.container():
                st.subheader('Hardening parameters by iteration')
                draw_hardening_chart(history)
        if mode == 'Run one simulation':
            status = 'Single simulation completed.'
            break
        if abs(diff) <= stress_tolerance and strain_min <= strain <= strain_max:
            status = f'Calibration converged at iteration {iteration}.'
            break
        # Same rule ordering and increments as the desktop application.
        if diff < 0:
            params['Kinf'] += 40; params['Ko'] += 2; params['delta1'] += 10
        elif diff > stress_tolerance:
            params['Kinf'] -= 20; params['delta1'] -= 10
        elif strain < strain_min:
            params['delta1'] -= 25; params['Ko'] -= 2; params['Kinf'] += 5
        elif strain > strain_max:
            params['delta1'] += 25; params['Ko'] += 2; params['Kinf'] -= 5
        for key in ('Kinf', 'Ko', 'delta1'):
            params[key] = max(0.0, min(params[key], 1000.0))
    stress_placeholder.empty()
    error_placeholder.empty()
    hardening_placeholder.empty()
    progress.progress(1.0, text='Analysis finished')
    st.session_state['results'] = dict(status=status, history=history, curves=curves, qf=qf, inputs=dict(E=E, nu=nu, c=c, phi=phi, patm=patm, mDen=mDen, Kinf=Kinf, Ko=Ko, delta1=delta1, H=H, theta=theta, delta2=delta2, max_eps=max_eps, steps=steps, strain_min=strain_min, strain_max=strain_max, stress_tolerance=stress_tolerance, max_iter=int(max_iter)), mode=mode)

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
        st.subheader('Stress–strain response')
        draw_stress_strain_chart(data['curves'], data['qf'])
        curve_df = pd.DataFrame({'axial_strain_pct': last['strain'], 'deviatoric_stress_kPa': last['stress']})
        st.download_button('Download last stress–strain curve (CSV)', curve_df.to_csv(index=False).encode(), 'stress_strain.csv', 'text/csv')
    if data['mode'].startswith('Calibrate') and any(row.get('difference_kPa') is not None for row in data['history']):
        st.subheader('Stress difference by iteration')
        st.caption(f"Positive values exceed the target; negative values fall below it. Failed iterations are omitted. Convergence also requires a peak strain from {data['inputs'].get('strain_min', 2):g}% to {data['inputs'].get('strain_max', 6):g}%.")
        draw_error_chart(data['history'], data['inputs'].get('stress_tolerance', 1.0))
    if data['mode'].startswith('Calibrate') and data['history']:
        st.subheader('Hardening parameters by iteration')
        st.caption('Values used in each attempted simulation. Red crosses mark failed analyses.')
        draw_hardening_chart(data['history'])
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
