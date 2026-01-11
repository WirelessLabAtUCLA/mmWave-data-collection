"""
Plot all beamforming patterns overlayed with different colors.
"""

from session_data import SessionData
from antenna_array import AntennaArray
from mikrotik_metadata import ordering_sets
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Load the same session as in load_and_visualize_data.py
session_dir = Path("../data/2025-11-20/session_135938")
session = SessionData.from_directory(session_dir)
session.load_all_router_batches()
print(session.summary())

# Get averaged CSI data
channel_data = session.get_csi_data(averaged=True)
num_samples = channel_data.shape[0]
valid_antennas = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27]

# Create antenna arrays for each sample
spacing = 0.58 * session.frequency / 60.48
antenna_arrays = []

for i in range(num_samples):
    array = AntennaArray()
    for antenna in range(32):
        if antenna not in valid_antennas:
            continue
        array.add_element(
            ordering_sets[antenna, 0] * spacing - np.sign(ordering_sets[antenna, 0]) * spacing / 2, 
            0, 
            ordering_sets[antenna, 1] * spacing - np.sign(ordering_sets[antenna, 1]) * spacing / 2
        )
    array.set_weights(np.conjugate(channel_data[i, :]))
    antenna_arrays.append(array)

# Create the overlay plot
fig = plt.figure(figsize=(12, 10))
ax_polar = fig.add_subplot(111, projection='polar')

# Generate colormap for different samples
colors = plt.cm.viridis(np.linspace(0, 1, num_samples))

print(f"Plotting {num_samples} beamforming patterns...")

# Plot each beamforming pattern
for i, (array, color) in enumerate(zip(antenna_arrays, colors)):
    # Get array pattern in azimuth
    x, th, el = array.get_array_pattern_azimuth(el=0, N=1024, full=True)
    
    # Plot with alpha for transparency
    ax_polar.plot(th, np.abs(x), color=color, alpha=0.6, linewidth=1.5)
    
    if (i + 1) % 10 == 0:
        print(f"  Plotted {i + 1}/{num_samples} patterns")

# Configure polar plot
ax_polar.set_theta_direction(-1)
ax_polar.set_theta_zero_location('N')
ax_polar.set_thetamin(-90)
ax_polar.set_thetamax(90)
ax_polar.set_title(f'All Beamforming Patterns Overlayed\nSession: {session.session_id}\n'
                   f'Total Patterns: {num_samples}', fontsize=14)

# Add colorbar to show temporal progression
sm = plt.cm.ScalarMappable(cmap=plt.cm.viridis, 
                           norm=plt.Normalize(vmin=0, vmax=num_samples-1))
sm.set_array([])
# cbar = plt.colorbar(sm, ax=ax_polar, pad=0.1)
# cbar.set_label('Sample Index', rotation=270, labelpad=20)
plt.tight_layout()

# Save the figure
save_path = session.get_save_plot_path() / 'beamforming_overlay.png'
plt.savefig(save_path, dpi=300, bbox_inches='tight')
print(f"\nPlot saved to: {save_path}")

# Also show the plot
plt.show()

