"""Run each OpenSees analysis in an isolated process and temporary directory."""
import json
import os
import sys
import tempfile
from simulation import run_simulation

if __name__ == '__main__':
    p = json.load(sys.stdin)
    with tempfile.TemporaryDirectory(prefix='drucker_prager_') as directory:
        os.chdir(directory)
        eps, stress, peak, peak_strain, ok = run_simulation(p, 1)
        result = {'success': ok, 'peak': peak, 'peak_strain': peak_strain}
        if ok:
            result.update(strain=eps.tolist(), stress=stress.tolist())
        print(json.dumps(result, allow_nan=False))
