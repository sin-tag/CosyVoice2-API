# CosyVoice2 API Application Package

import os
import sys

# CRITICAL: Ensure proper Python path setup for all import scenarios
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)

# Add paths if not already present - this fixes uvicorn direct usage
_paths_to_add = [
    _root_dir,
    os.path.join(_root_dir, 'cosyvoice_original'),
    os.path.join(_root_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
]

for _path in _paths_to_add:
    if os.path.exists(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

# Also set PYTHONPATH environment variable
_current_pythonpath = os.environ.get('PYTHONPATH', '')
_new_paths = [p for p in _paths_to_add if p not in _current_pythonpath.split(os.pathsep)]
if _new_paths:
    if _current_pythonpath:
        os.environ['PYTHONPATH'] = os.pathsep.join(_new_paths + [_current_pythonpath])
    else:
        os.environ['PYTHONPATH'] = os.pathsep.join(_new_paths)
