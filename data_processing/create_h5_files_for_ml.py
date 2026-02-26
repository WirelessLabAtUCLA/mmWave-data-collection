import h5py
from PIL import Image
from tqdm import tqdm
import numpy as np
from pathlib import Path
from session_data import SessionData
from antenna_array import AntennaArray
from mikrotik_metadata import ordering_sets, valid_antennas
import matplotlib.pyplot as plt

### User Inputs ###
data_path = Path("/home/kanishka/Projects/mmWave-datasets/raw/2025-11-25/session_122307")
h5_file_path = Path("/home/kanishka/Projects/mmWave-datasets/ml-ready/session_20251125_122307.h5")
### End User Inputs ###

session = SessionData.from_directory(data_path)
session.load_all_router_batches()
timestamps, csi_data, image_paths = session.get_expanded_data_for_ml()

print(f"Number of timestamps: {len(timestamps)}")
print(f"Number of csi data: {len(csi_data)}")
print(f"Number of image paths: {len(image_paths)}")

for i, (timestamp, csi, image_path) in tqdm(enumerate(zip(timestamps, csi_data, image_paths))):
    timestamp_array = np.array([timestamp.hour,
                                timestamp.minute,
                                timestamp.second,
                                timestamp.microsecond])
    image = Image.open(image_path).resize((320, 180))
    image_array = np.array(image)
    with h5py.File(h5_file_path, 'a') as f:
        f.create_group(f"sample_{i}")
        f[f"sample_{i}"].create_dataset("timestamp", data=timestamp_array)
        f[f"sample_{i}"].create_dataset("csi_data", data=csi, dtype=np.complex64)
        f[f"sample_{i}"].create_dataset("image_data", data=image_array, dtype=np.uint8)

print(f"H5 file created successfully at {h5_file_path}")


