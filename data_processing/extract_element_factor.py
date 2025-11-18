import numpy as np
import matplotlib.pyplot as plt
from session_data import *
from visualize import *
from antenna_array import *

session_dir = Path("../data/2025-11-16/rotation_80_direct")
session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

channel_data = np.zeros((1, 16), dtype=np.complex128)

for dp in session.data_points:
    # Check if router batch is loaded
    if dp.router_batch is None:
        continue
        
    csi_data = dp.router_batch.csi_processed_data
    
    # Check if CSI data is not empty and has the right shape
    if csi_data.size == 0 or len(csi_data.shape) < 2:
        continue
    
    channel_data = np.vstack((channel_data, csi_data))

num_samples = channel_data.shape[0] - 1
valid_antennas = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27]


num_samples = int(np.shape(channel_data)[0] / 10)
theta_vals = np.linspace(-80, 80, num_samples)
theta_vals = np.deg2rad(theta_vals)

# Create antenna arrays for each sample
spacing = 0.58 * 58.32 / 60.48
antenna_arrays = [AntennaArray() for _ in range(num_samples)]
antenna_arrays_real = [AntennaArray() for _ in range(num_samples)]
for i in range(num_samples):
    averaged_channel_data = np.mean(channel_data[i*10:(i+1)*10, :], axis=0)

    for antenna in range(32):
        if antenna not in valid_antennas:
            continue
        antenna_arrays[i].add_element(ordering_sets[antenna, 0]*spacing - np.sign(ordering_sets[antenna, 0])*spacing/2, 
            0, ordering_sets[antenna, 1]*spacing - np.sign(ordering_sets[antenna, 1])*spacing/2)
        antenna_arrays_real[i].add_element(ordering_sets[antenna, 0]*spacing - np.sign(ordering_sets[antenna, 0])*spacing/2, 
            0, ordering_sets[antenna, 1]*spacing - np.sign(ordering_sets[antenna, 1])*spacing/2)

    w = antenna_arrays[i].get_conjugate_beamformer(az=theta_vals[i], el=0)
    antenna_arrays[i].set_weights(w)
    antenna_arrays_real[i].set_weights(np.conjugate(averaged_channel_data))

# Notes
"""
So we have the real-world antenna array and the ideal antenna array that are pointed towards the theta_vals[i] angle.
We can get the element factor for each element by dividing the real-world antenna array by the ideal antenna array at each theta and phi to get R(theta, phi).
"""

R = np.zeros((16, 512, 512))
theta_range = np.linspace(-np.pi/2, np.pi/2, 512)
phi_range = np.linspace(-np.pi/2, np.pi/2, 512)

for i in range(16):
    for j, theta in enumerate(theta_range):
        for k, phi in enumerate(phi_range):
            R[i, j, k] = antenna_arrays[i].get_array_response(theta, phi) / antenna_arrays_real[i].get_array_response(theta, phi)

plt.figure(figsize=(10, 10))
plt.imshow(R[0, :, :], cmap='viridis')
plt.colorbar()
plt.show()

