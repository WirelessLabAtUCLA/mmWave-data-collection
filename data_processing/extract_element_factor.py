import numpy as np
import matplotlib.pyplot as plt
import tqdm
from session_data import *
from visualize import *
from antenna_array import *
from mikrotik_metadata import *

def extract_peak_theta(channel_data: np.ndarray) -> np.ndarray:
    """Extract the peak theta from the channel data."""
    # First create a antenna array
    spacing = 0.58 * session.frequency / 60.48
    antenna_array = AntennaArray()
    for ant in range(32):
        if ant not in valid_antennas:
            continue
        antenna_array.add_element(ordering_sets[ant, 0]*spacing - np.sign(ordering_sets[ant, 0])*spacing/2, 
             0, ordering_sets[ant, 1]*spacing - np.sign(ordering_sets[ant, 1])*spacing/2)

    theta_vals = np.linspace(-np.pi/2, np.pi/2, 1024)
    theta_peaks = np.zeros(np.shape(channel_data)[0])
    peak_values = np.zeros(np.shape(channel_data)[0])
    for sample in tqdm.trange(np.shape(channel_data)[0]):
        antenna_array.set_weights(np.conjugate(channel_data[sample, :]))
        array_response, _, _ = antenna_array.get_array_pattern_azimuth(0, 1024, full=True)
        peak_theta = np.argmax(np.abs(array_response))
        theta_peaks[sample] = theta_vals[peak_theta]
        peak_values[sample] = array_response[peak_theta]

    return theta_peaks, peak_values


session_dir = Path("/home/kanishka/Projects/mmWave-datasets/raw/2025-11-18/session_152325")
elevation_angle = np.deg2rad(3)
theta_range = np.deg2rad([-95, 95])

session = SessionData.from_directory(session_dir)
session.load_all_router_batches()

channel_data = session.get_csi_data(averaged=True)
channel_data_avg = session.get_csi_data(averaged=True)

theta_peaks, peak_values = extract_peak_theta(channel_data)
theta_peaks_avg, peak_values_avg = extract_peak_theta(channel_data_avg)

plt.figure()
plt.plot(peak_values)
plt.plot(peak_values_avg)
plt.xlabel('Theta (degrees)')
plt.ylabel('Peak Value')
plt.title('Peak Theta vs Peak Value')
plt.legend(['Averaged', 'Not Averaged'])
plt.show()






    











# num_samples = int(np.shape(channel_data)[0] / 10)
# valid_antennas = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27]

# theta_vals = np.linspace(theta_range[0], theta_range[1], num_samples)

# # Create antenna arrays for each sample
# spacing = 0.58 * 58.32 / 60.48
# antenna_arrays = [AntennaArray() for _ in range(num_samples)]
# antenna_arrays_real = [AntennaArray() for _ in range(num_samples)]
# for i in range(num_samples):
#     averaged_channel_data = np.mean(channel_data[i*10:(i+1)*10, :], axis=0)

#     for antenna in range(32):
#         if antenna not in valid_antennas:
#             continue
#         antenna_arrays[i].add_element(ordering_sets[antenna, 0]*spacing - np.sign(ordering_sets[antenna, 0])*spacing/2, 
#             0, ordering_sets[antenna, 1]*spacing - np.sign(ordering_sets[antenna, 1])*spacing/2)
#         antenna_arrays_real[i].add_element(ordering_sets[antenna, 0]*spacing - np.sign(ordering_sets[antenna, 0])*spacing/2, 
#             0, ordering_sets[antenna, 1]*spacing - np.sign(ordering_sets[antenna, 1])*spacing/2)

#     w = antenna_arrays[i].get_conjugate_beamformer(az=theta_vals[i], el=elevation_angle) 
#     antenna_arrays[i].set_weights(w)
#     antenna_arrays_real[i].set_weights(np.conjugate(averaged_channel_data))


# # Element Factor Estimation
# element_factor = np.zeros((np.shape(theta_vals)[0], 16), dtype=np.complex128)

# for j, theta in enumerate(theta_vals):
#     element_factor[j, :] = antenna_arrays_real[j].get_array_response(theta, elevation_angle) / antenna_arrays[j].get_array_response(theta, elevation_angle)

# # Create figure with 16 subplots (4x4 grid)
# fig = plt.figure(figsize=(16, 16))

# # Plot first 16 elements
# for idx in range(16):
#     ax = plt.subplot(4, 4, idx + 1, projection='polar')
    
#     element_pattern = np.abs(element_factor[:, idx])

#     # Convert to dB with proper floor
#     element_pattern_db = 10*np.log10(element_pattern)
#     element_pattern_db = element_pattern_db - np.max(element_pattern_db)
    
#     # Optional: clip the lower bound to avoid extreme negative values
#     element_pattern_db = np.maximum(element_pattern_db, -60)  # -60 dB floor
    
#     # Plot
#     ax.plot(theta_vals, element_pattern_db, linewidth=1.5)
    
#     # Configure polar plot
#     ax.set_theta_zero_location('N')  # 0° at top
#     ax.set_theta_direction(-1)  # Clockwise
#     ax.set_thetamin(-90)  # Set range from -90
#     ax.set_thetamax(90)   # to 90 degrees
#     ax.set_ylim([-20, 3])  # dB range
#     ax.set_title(f'Element {idx+1}', fontsize=10)
#     ax.grid(True, alpha=0.3)

# plt.tight_layout()
# plt.savefig(session.get_save_plot_path() / 'element_patterns_16_1d.png', dpi=150, bbox_inches='tight')
# plt.show()