"""Load current scenes from the external map; no historical pickle or app copies."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from engine.scene import get_scene as load_scene
