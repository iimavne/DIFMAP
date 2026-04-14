# difmap_wrapper/gui/constants.py
"""
Constantes et configurations centralisées pour l'UI.

Avantage: Une seule source de vérité (DRY)
"""

# Raccourcis clavier
KEYBOARD_SHORTCUTS = {
    'S': 'Inspect Visibilities (Hover mouse)',
    'Z': 'Toggle Zoom mode (Left click/Drag to select)',
    'C': 'Toggle Cut/Flag mode (Left click to select area)',
    'U': 'Undo last flagging operation',
    'L': 'Refresh / Redraw plot',
    'N': 'Next Subarray',
    'P': 'Previous Subarray',
    'n': 'Next Antenna in current Subarray',
    'p': 'Previous Antenna in current Subarray',
    'T': 'Specific Telescope Search',
    'W': 'Toggle Channel Flagging scope',
    '+': 'Toggle Crosshair cursor',
    '.': 'Toggle Marker size',
    '%': 'Toggle Conjugate points (-U, -V)',
}

# Tailles et sélection de poids
IMAGING_PRESETS = {
    'natural': {'bin_size': 0.0, 'err_power': -1.0, 'desc': 'Maximum sensitivity'},
    'uniform': {'bin_size': 2.0, 'err_power': 0.0, 'desc': 'Maximum resolution'},
    'briggs': {'bin_size': 2.0, 'err_power': -1.0, 'desc': 'Balanced/Robust'},
}

# Formatage des messages
MESSAGES = {
    'loading': 'Loading: {}...',
    'loaded': 'Successfully loaded {} visibilities.',
    'polarization_switch': 'Switching polarization to: {}...',
    'polarization_loaded': 'Polarization {} loaded successfully.',
    'computing_map': 'Computing Dirty Map (Size: {}, Cell: {}, Weight: {}, Taper: {})...',
    'map_computed': 'Dirty Map computed successfully.',
    'file_closed': 'File closed successfully.',
}

# Erreurs
ERROR_MESSAGES = {
    'no_data': 'No data found for current selection.',
    'load_failed': 'Could not load FITS file: {}',
    'pol_failed': 'Failed to change polarization: {}',
    'map_failed': 'Failed to compute map: {}',
    'invalid_input': 'Invalid input: {}',
}

# Couleurs d'état (thème)
STATUS_COLORS = {
    'error': '#dc3545',
    'warning': '#ffc107',
    'success': '#28a745',
    'info': '#17a2b8',
}

# Limites d'entrée
INPUT_LIMITS = {
    'mapsize': {'min': 64, 'max': 4096, 'default': 256},
    'cellsize': {'min': 0.001, 'max': 10.0, 'default': 1.0},
    'taper': {'min': 0.0, 'max': 100.0, 'default': 0.0},
}
