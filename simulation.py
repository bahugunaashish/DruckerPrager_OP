"""Single-element simulation adapted from the repository desktop application."""
import os
import numpy as np

def run_simulation(p, iteration):
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

    out_dir = os.getcwd()
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
            if ok != 0:
                raise RuntimeError(f"Displacement analysis failed at step {_step_id} of {steps}.")
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
