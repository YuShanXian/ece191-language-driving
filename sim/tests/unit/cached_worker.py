"""Compatibility entry point: current worker caches current map scenes in memory."""
import sys, runpy
from pathlib import Path
sim = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(sim))
runpy.run_path(str(sim / 'worker.py'), run_name='__main__')
