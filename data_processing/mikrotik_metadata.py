import numpy as np

ordering_sets = np.array([
    [-2, -1], [-3, -2], [-3, -1], [-2, -2], [-1, -3], [-1, -2],
    [-1, -1], [-2, -3], [3, -2], [2, -1], [3, -1], [1, -1],
    [1, -3], [2, -3], [1, -2], [2, -2], [-2, 1], [-3, 2],
    [-3, 1], [-2, 2], [-1, 3], [-1, 2], [-2, 3], [-1, 1],
    [3, 2], [2, 1], [3, 1], [1, 1], [1, 3], [2, 3],
    [1, 2], [2, 2]
])

# Reliable antennas (19): S, A+ and A tier of the cross-dataset raw phase-variance ranking
# (data_processing/antenna_variance_report.py).
valid_antennas = np.array([0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29])

# Previous 16-entry list. Kept for code that must stay exactly as before:
# utils.process_csi_data (outlier-detection columns) and extract_element_factor.py (array geometry).
legacy_valid_antennas = np.array([0, 1, 2, 3, 4, 5, 6, 7, 9, 11, 13, 19, 21, 23, 25, 27])