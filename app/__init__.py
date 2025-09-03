# CosyVoice2 API Application Package

import os
import sys

# Ensure proper Python path setup
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)

# Add paths if not already present
_paths_to_add = [
    _root_dir,
    os.path.join(_root_dir, 'cosyvoice_original'),
    os.path.join(_root_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
]

for _path in _paths_to_add:
    if os.path.exists(_path) and _path not in sys.path:
        sys.path.insert(0, _path)
