# -*- coding: utf-8 -*-
"""
Drucker-Prager Triaxial Compression Test - Autonomous Optimizer
Features: Native Tkinter GUI, Interactive Plot, Continuous Calibration
by Ashish Bahuguna 
Basic units: kPa and meters.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import sys
import numpy as np


# ── parameter definitions ───────────────────────────────────────────────────
PARAMS = [
    ("Young's Modulus E  [kPa]",       "E",       "50000",  "Elastic modulus in kPa"),
    ("Poisson's Ratio ν",              "nu",      "0.3",    "Range: 0 – 0.49"),
    ("Cohesion c  [kPa]",              "c",       "4.5",    "Effective cohesion"),
    ("Friction Angle φ  [°]",          "phi",     "35",     "Internal friction angle"),

    ("Isotropic Hard. Kinf  [kPa]",    "Kinf",    "222",    "Maximum isotropic hardening (Max 1000)"),
    ("Isotropic Hard. Ko  [kPa]",      "Ko",      "20",     "Initial isotropic hardening (Max 1000)"),
    ("δ₁  (hardening rate)",           "delta1",  "200",    "Isotropic hardening rate (Max 1000)"),

    ("Kinematic Hard. H  [kPa]",       "H",       "500",    "Kinematic hardening modulus ≥ 0"),
    ("θ  (hardening mix)",             "theta",   "0.2",    "0 = pure kinematic, 1 = pure isotropic"),
    ("δ₂  (tension softening)",        "delta2",  "0",      "Tension softening parameter"),

    ("Mass Density ρ  [Mg/m³]",        "mDen",    "1.964",  "Bulk mass density"),
    ("Confining Pressure p  [kPa]",    "patm",    "100",    "Hydrostatic confining pressure"),

    ("Max Axial Strain  [%]",          "max_eps", "15",     "Target axial strain"),
    ("Analysis Steps",                 "steps",   "1000",   "Number of displacement-control steps"),
]


class ToolTip:
    """Simple native-looking hover tooltip."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 6
        y = self.widget.winfo_rooty() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(tw, borderwidth=1, relief="solid", padding=(8, 4))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.text).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class DruckerPragerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Drucker-Prager · Autonomous Triaxial Optimization")
        self.resizable(True, True)
        self.minsize(1100, 720)

        self.entries = {}
        self._running = False
        self._plot_canvas = None
        self.fig = None
        self.ax = None

        self._setup_style()
        self.configure(background=self.ui_bg)
        self._build_ui()

    def _setup_style(self):
        self.style = ttk.Style(self)
        themes = self.style.theme_names()
        if sys.platform.startswith("win") and "vista" in themes:
            self.style.theme_use("vista")
        elif sys.platform == "darwin" and "aqua" in themes:
            self.style.theme_use("aqua")

        self.ui_bg = self.style.lookup("TFrame", "background")
        if not self.ui_bg:
            self.ui_bg = self.cget("background")

    def _build_ui(self):
        header = ttk.Frame(self, padding=(20, 14))
        header.pack(fill="x")

        ttk.Label(header, text="Drucker-Prager · Autonomous Optimizer", font=("", 13, "bold")).pack(side="left")
        ttk.Label(header, text="OpenSeesPy · 3-D SSPbrick").pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=350, padding=(12, 12))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        self._build_param_panel(left)

        ttk.Separator(body, orient="vertical").pack(side="left", fill="y")

        right = ttk.Frame(body, padding=(16, 16))
        right.pack(side="left", fill="both", expand=True)

        self._build_right_panel(right)

    def _build_param_panel(self, parent):
        ttk.Label(parent, text="Model Parameters", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(parent, text="Hover labels for hints. Units: kPa / m.").pack(anchor="w", pady=(0, 10))

        button_frame = ttk.Frame(parent)
        button_frame.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Separator(button_frame, orient="horizontal").pack(fill="x", pady=(0, 10))

        self.run_btn = ttk.Button(button_frame, text="Run Autonomous Loop", command=self._run_thread)
        self.run_btn.pack(fill="x", pady=(0, 6))

        self.reset_btn = ttk.Button(button_frame, text="Reset Defaults", command=self._reset_defaults)
        self.reset_btn.pack(fill="x")

        scroll_area = ttk.Frame(parent)
        scroll_area.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(scroll_area, highlightthickness=0, background=self.ui_bg)
        scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda event: canvas.itemconfig(win_id, width=canvas.winfo_width()))

        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")

        canvas.bind("<Enter>", lambda event: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda event: canvas.unbind_all("<MouseWheel>"))

        for label, key, default, tip in PARAMS:
            row = ttk.Frame(inner)
            row.pack(fill="x", pady=4)
            lbl = ttk.Label(row, text=label, width=30, anchor="w")
            lbl.pack(side="left")
            ToolTip(lbl, tip)
            var = tk.StringVar(value=default)
            entry = ttk.Entry(row, textvariable=var, width=12)
            entry.pack(side="right", padx=(6, 0))
            self.entries[key] = var

    def _build_right_panel(self, parent):
        plot_frame = ttk.Frame(parent)
        plot_frame.pack(fill="both", expand=True)

        self.plot_placeholder = ttk.Label(
            plot_frame,
            text=("Run the analysis to generate the\n" "Deviatoric Stress vs Axial Strain plot"),
            justify="center",
        )
        self.plot_placeholder.pack(expand=True)
        self.plot_frame = plot_frame

        self.summary_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.summary_var, anchor="w").pack(fill="x", pady=(8, 0))
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(parent, text="Analysis Log", font=("", 10, "bold")).pack(anchor="w")

        log_frame = ttk.Frame(parent)
        log_frame.pack(fill="x", pady=(4, 0))

        self.log = tk.Text(log_frame, height=9, relief="sunken", borderwidth=1, state="disabled", wrap="word", font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="x", expand=True)

    def _log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _reset_defaults(self):
        defaults = {p[1]: p[2] for p in PARAMS}
        for key, var in self.entries.items():
            var.set(defaults[key])
        self.summary_var.set("")
        self._log_msg("Defaults restored.")

    def _get_params(self):
        vals = {}
        for key, var in self.entries.items():
            value = var.get().strip()
            try:
                vals[key] = float(value)
            except ValueError:
                raise ValueError(f"Invalid value for '{key}': '{value}'")
        return vals

    def _validate_params(self, p):
        if p["E"] <= 0: raise ValueError("Young's modulus E must be positive.")
        if not (0.0 <= p["nu"] < 0.5): raise ValueError("Poisson's ratio ν must satisfy 0 ≤ ν < 0.5.")
        if p["c"] < 0: raise ValueError("Cohesion c must be non-negative.")
        if not (0.0 < p["phi"] < 90.0): raise ValueError("Friction angle φ must be between 0 and 90 degrees.")
        if p["steps"] <= 0 or int(p["steps"]) != p["steps"]: raise ValueError("Analysis Steps must be a positive integer.")

    def _run_thread(self):
        if self._running: return

        try:
            p = self._get_params()
            self._validate_params(p)
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return

        self._running = True
        self.run_btn.configure(state="disabled", text="Running Continuous Optimization...")
        self.summary_var.set("Optimizing parameters...")

        self.log.configure(state="normal")
        self.log.delete(1.0, "end")
        self.log.configure(state="disabled")

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure

        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        self.fig = Figure(figsize=(6, 4))
        self.ax = self.fig.add_subplot(111)
        self._plot_canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        
        toolbar = NavigationToolbar2Tk(self._plot_canvas, self.plot_frame)
        toolbar.update()
        
        self._plot_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self._log_msg("────────────────────────────────────────")
        self._log_msg("Starting Continuous Optimization Loop...")

        thread = threading.Thread(target=self._optimization_loop, args=(p,), daemon=True)
        thread.start()

    def _finish(self, ok=True):
        self._running = False
        self.run_btn.configure(state="normal", text="Run Autonomous Loop")
        if not ok: self.bell()

    def _reset_plot_view(self, qf):
        """Clears the plot but keeps formatting and theoretical line."""
        self.ax.clear()
        self.ax.grid(True, linestyle="--", linewidth=0.6)
        self.ax.set_xlabel(r"Axial Strain  $\epsilon_z$  (%)")
        self.ax.set_ylabel(r"Deviatoric Stress  $(\sigma_1 - \sigma_3)$  (kPa)")
        self.ax.axhline(y=qf, color="tab:red", linestyle="--", linewidth=1.4, label=f"M-C theoretical qf = {qf:.2f} kPa")
        self._plot_canvas.draw()

    # ── Continuous Autonomous Optimization Loop ─────────────────────────────
    def _optimization_loop(self, p):
        c = p["c"]
        phi = p["phi"]
        patm = p["patm"]
        sin_phi = np.sin(np.radians(phi))
        qf = ((c * (1.0 / np.tan(np.radians(phi))) + patm) * 2.0 * sin_phi / (1.0 - sin_phi))
        
        self.after(0, self._reset_plot_view, qf)
        
        tolerance = 1.0  # Target tolerance
        matched = False
        iteration = 0
        chunk_size = 25  # Number of iterations before clearing plot lines

        while not matched and self._running:
            iteration += 1

            # Clear old curves every chunk_size (25) iterations
            if iteration > 1 and (iteration - 1) % chunk_size == 0:
                self.after(0, self._log_msg, f"\n--- Cleared plot after {iteration-1} iterations ---")
                self.after(0, self._reset_plot_view, qf)

            self.after(0, self._log_msg, f"\n--- Iteration {iteration} ---")
            self.after(0, self._log_msg, f"Using: Kinf={p['Kinf']:.2f}, Ko={p['Ko']:.2f}, delta1={p['delta1']:.2f}")

            eps_pct, dev_stress, peak_q, peak_strain, success = self._run_single_simulation(p, iteration)
            
            if not success:
                self.after(0, self._log_msg, "Simulation failed structurally. Nudging Ko and Kinf...")
                # Push parameters up to gain stability, bounded by 1000
                p["Ko"] = min(p["Ko"] + 5.0, 1000.0)
                p["Kinf"] = min(p["Kinf"] + 10.0, 1000.0)
                self.after(0, self.entries["Ko"].set, f"{p['Ko']:.2f}")
                self.after(0, self.entries["Kinf"].set, f"{p['Kinf']:.2f}")
                continue

            self.after(0, self._update_plot_lines, eps_pct, dev_stress, iteration, peak_q, peak_strain, p.copy())
            
            diff = peak_q - qf
            strain_ok = (2.0 <= peak_strain <= 6.0)
            
            self.after(0, self._log_msg, f"Peak: {peak_q:.2f} kPa @ {peak_strain:.2f}% strain | Gap: {abs(diff):.2f} kPa")

            if abs(diff) <= tolerance and strain_ok:
                self.after(0, self._log_msg, f"✅ MATCH FOUND! Stress within tolerance AND Strain in [2%, 6%].")
                self.after(0, self.summary_var.set, f"Converged at Iter {iteration}. Peak q = {peak_q:.2f} kPa @ {peak_strain:.2f}%.")
                matched = True
            else:
                self.after(0, self._log_msg, "Adjusting parameters for next iteration...")
                
                if diff < 0: 
                    p["Kinf"] += 40.0
                    p["Ko"] += 2.0
                    p["delta1"] += 10.0
                elif diff > tolerance: 
                    p["Kinf"] -= 20.0
                    p["delta1"] -= 10.0
                else:
                    self.after(0, self._log_msg, "Stress is good, but shifting strain peak...")
                    if peak_strain < 2.0:
                        p["delta1"] -= 25.0
                        p["Ko"] -= 2.0
                        p["Kinf"] += 5.0 
                    elif peak_strain > 6.0:
                        p["delta1"] += 25.0
                        p["Ko"] += 2.0
                        p["Kinf"] -= 5.0

                # --- APPLY THE 1000 MAX CAP HERE ---
                p["Kinf"] = max(0.0, min(p["Kinf"], 1000.0))
                p["Ko"] = max(0.0, min(p["Ko"], 1000.0))
                p["delta1"] = max(0.0, min(p["delta1"], 1000.0))
                
                self.after(0, self.entries["Kinf"].set, f"{p['Kinf']:.2f}")
                self.after(0, self.entries["Ko"].set, f"{p['Ko']:.2f}")
                self.after(0, self.entries["delta1"].set, f"{p['delta1']:.2f}")

        self.after(0, self._finish, matched)

    def _update_plot_lines(self, eps, stress, it, peak, peak_strain, p):
        label_text = (f"Iter {it}: Kinf={p['Kinf']:.1f}, Ko={p['Ko']:.1f}, δ1={p['delta1']:.1f}\n"
                      f"Peak={peak:.1f} kPa @ {peak_strain:.1f}%")
        
        self.ax.plot(eps, stress, linewidth=1.8, label=label_text)
        self.ax.legend(fontsize="7", loc="lower right")
        self.fig.tight_layout()
        self._plot_canvas.draw()

    # ── User's Original Core Simulation Block ───────────────────────────────
    def _run_single_simulation(self, p, iteration):
        try:
            import openseespy.opensees as op
        except ImportError:
            return None, None, 0, 0, False

        E = p["E"]
        nu = p["nu"]
        c = p["c"]
        phi = p["phi"]
        Kinf = p["Kinf"]
        Ko = p["Ko"]
        delta1 = p["delta1"]
        H_kin = p["H"]
        theta = p["theta"]
        delta2 = p["delta2"]
        mDen = p["mDen"]
        patm = p["patm"]
        max_eps = p["max_eps"] / 100.0
        steps = int(p["steps"])

        nsim = "sim-2"
        nelel = 1

        out_dir = os.path.join(os.getcwd(), "CTC_GUI_Output")
        os.makedirs(out_dir, exist_ok=True)

        stress_file = os.path.join(out_dir, "stress1.out")
        strain_file = os.path.join(out_dir, "strain1.out")
        disp1_file = os.path.join(out_dir, "displacements1.out")
        disp2_file = os.path.join(out_dir, "displacements2.out")

        for fn in (stress_file, strain_file, disp1_file, disp2_file):
            try: os.remove(fn)
            except FileNotFoundError: pass

        kk = E / (3.0 * (1.0 - 2.0 * nu))
        G = E / (2.0 * (1.0 + nu))
        sin_phi = np.sin(np.radians(phi))
        cos_phi = np.cos(np.radians(phi))
        rho = 2.0 * sin_phi / (np.sqrt(3.0) * (3.0 - sin_phi))
        sigY = 6.0 * c * cos_phi / (np.sqrt(2.0) * (3.0 - sin_phi))
        rhoBar = (1.0 / 3.0) * rho

        try:
            op.wipe()
            op.wipeAnalysis()
            op.model("BasicBuilder", "-ndm", 3, "-ndf", 3)

            block = [
                1, 1.0, 0.0, 0.0,
                2, 1.0, 1.0, 0.0,
                3, 0.0, 1.0, 0.0,
                4, 0.0, 0.0, 0.0,
                5, 1.0, 0.0, 1.0,
                6, 1.0, 1.0, 1.0,
                7, 0.0, 1.0, 1.0,
                8, 0.0, 0.0, 1.0,
            ]

            op.nDMaterial(
                "DruckerPrager", 2, kk, G, sigY, rho, rhoBar,
                Kinf, Ko, delta1, delta2, H_kin, theta, mDen, patm,
            )

            op.block3D(
                nelel, nelel, nelel, 1, 1, "SSPbrick", 2,
                *block, 0.0, 0.0, 0.0,
            )

            AllNodes = op.getNodeTags()
            cornernode = (nelel + 1) ** 2 - nelel

            XYnodesFixZ, XYnodesFixY, XYnodesFixX = [], [], []
            TopNodes, CornNodeFixXY, YZnodeFixX, XZnodeFixY = [], [], [], []

            for node in AllNodes:
                nodcord = op.nodeCoord(node)
                if nodcord[0] > 0 and nodcord[1] > 0 and nodcord[2] == 0: XYnodesFixZ.append(node)
                if nodcord[0] == 0 and nodcord[2] == 0:
                    if node != cornernode: XYnodesFixX.append(node)
                if nodcord[1] == 0 and nodcord[2] == 0:
                    if node != cornernode: XYnodesFixY.append(node)
                if nodcord[0] >= 0 and nodcord[1] >= 0 and nodcord[2] > 0.999: TopNodes.append(node)
                if nodcord[0] == 0 and nodcord[1] == 0 and nodcord[2] > 0: CornNodeFixXY.append(node)
                if nodcord[0] == 0 and nodcord[1] > 0 and nodcord[2] > 0: YZnodeFixX.append(node)
                if nodcord[0] > 0 and nodcord[1] == 0 and nodcord[2] > 0: XZnodeFixY.append(node)

            op.fix(cornernode, 1, 1, 1)
            for node in XYnodesFixZ: op.fix(node, 0, 0, 1)
            for node in XYnodesFixX: op.fix(node, 1, 0, 1)
            for node in XYnodesFixY: op.fix(node, 0, 1, 1)
            for node in CornNodeFixXY: op.fix(node, 1, 1, 0)
            for node in YZnodeFixX: op.fix(node, 1, 0, 0)
            for node in XZnodeFixY: op.fix(node, 0, 1, 0)

            TopMidNodes, TopEdgeNodes, TopFaceCornerNode = [], [], []
            for node in TopNodes:
                nodcord = op.nodeCoord(node)
                if 0 < nodcord[0] < 1 and 0 < nodcord[1] < 1:
                    TopMidNodes.append(node)
                else:
                    if (nodcord[1] == 0 or nodcord[1] > 0.99) and (nodcord[0] == 0 or nodcord[0] > 0.99):
                        TopFaceCornerNode.append(node)
                    else:
                        TopEdgeNodes.append(node)

            pvd_dir = os.path.join(out_dir, "MultiCTC" + nsim + ".pvd")
            try:
                if not os.path.exists(pvd_dir): os.makedirs(pvd_dir)
                op.recorder("PVD", pvd_dir, "pressure", "-dT", 1)
            except Exception: pass

            unitArea = (1.0 / nelel) ** 2
            p_hydro = patm
            pnode1_hydro = -p_hydro * unitArea
            pnode2_hydro = -p_hydro * unitArea * 0.5
            pnode3_hydro = -p_hydro * unitArea * 0.25

            op.timeSeries("Path", 10, "-values", *[0, 1, 1], "-time", *[0, 10, 100])
            op.pattern("Plain", 10, 10, "-fact", 1)

            pNode = patm / 4.0
            op.load(1,  pNode,  -0.0,    0.0)
            op.load(2,  pNode,   pNode,  0.0)
            op.load(3, -0.0,     pNode,  0.0)
            op.load(4, -0.0,    -0.0,    0.0)
            op.load(5,  pNode,  -0.0,    pNode)
            op.load(6,  pNode,   pNode,  pNode)
            op.load(7, -0.0,     pNode,  pNode)
            op.load(8, -0.0,    -0.0,    pNode)

            op.integrator("LoadControl", 0.1)
            op.numberer("RCM")
            op.system("SparseGeneral")
            op.constraints("Transformation")
            op.test("NormDispIncr", 1e-3, 50)
            op.algorithm("ModifiedNewton")
            op.analysis("Static")

            ok = op.analyze(10)
            op.loadConst("-time", 0.0)

            if ok != 0:
                op.wipe()
                op.wipeAnalysis()
                return None, None, 0, 0, False

            try: op.remove("recorders")
            except Exception: pass

            PushDir = 3
            nodeCont = 5
            Peaks = [0.0, -max_eps]

            op.timeSeries("Linear", 2)
            op.pattern("Plain", 2, 2)

            reference_load = 1.0
            pnode1 = reference_load
            pnode2 = pnode2_hydro
            pnode3 = pnode3_hydro

            op.recorder("Node", "-file", disp1_file, "-time", "-node", 5, "-dof", 3, "disp")
            op.recorder("Node", "-file", disp2_file, "-time", "-node", 1, "-dof", 3, "disp")
            op.recorder("Element", "-ele", 1, "-time", "-file", stress_file, "stress")
            op.recorder("Element", "-ele", 1, "-time", "-file", strain_file, "strain")

            for node in TopMidNodes: op.load(node, 0.0, 0.0, pnode1)
            for node in TopEdgeNodes: op.load(node, 0.0, 0.0, pnode2)
            for node in TopFaceCornerNode: op.load(node, 0.0, 0.0, pnode3)

            op.wipeAnalysis()

            tol = 1e-3
            niter = 500
            dj = [Peaks[0]]
            jn = 1

            for i in range(1, len(Peaks)):
                Delta = (Peaks[i] - Peaks[i - 1]) / steps
                for _ in range(steps):
                    dj.append(dj[jn - 1] + Delta)
                    jn += 1

            op.constraints("Transformation")
            op.numberer("RCM")
            op.system("SparseGeneral")

            d1 = 0.0

            for _step_id, d2 in enumerate(dj):
                DeltaDisp = d2 - d1
                op.test("NormDispIncr", tol, niter, 2)
                op.algorithm("KrylovNewton")
                op.integrator("DisplacementControl", nodeCont, PushDir, DeltaDisp)
                op.analysis("Static")

                ok = op.analyze(1)
                if ok != 0: break
                d1 = d2

            try: op.remove("recorders")
            except Exception: pass

            op.wipe()
            op.wipeAnalysis()

            stress = np.atleast_2d(np.loadtxt(stress_file))
            strain = np.atleast_2d(np.loadtxt(strain_file))
            
            syy, szz = stress[:, 2], stress[:, 3]
            ezz = strain[:, 3]

            strainZ = -(ezz - ezz[0])
            dstress = -(szz - syy)

            eps_pct = strainZ * 100.0
            
            peak_idx = np.argmax(dstress)
            peak_q = float(dstress[peak_idx])
            peak_strain = float(eps_pct[peak_idx])

            return eps_pct, dstress, peak_q, peak_strain, True

        except Exception as e:
            try:
                op.wipe()
                op.wipeAnalysis()
            except Exception: pass
            return None, None, 0, 0, False

if __name__ == "__main__":
    app = DruckerPragerApp()
    app.mainloop()
