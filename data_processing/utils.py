from typing import List, Tuple
import numpy as np
from scipy.signal import find_peaks, savgol_filter

from session_data import SessionData

def read_and_process_csi_data(session: SessionData) -> Tuple[np.ndarray, List[int]]:
    """Read and process CSI data from a session.
    
    Args:
        session: SessionData object
        
    Returns:
        Processed CSI data
    """
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

    return process_csi_data(channel_data[1:, :])

def process_csi_data(H: np.ndarray, sample_rate: float = 0.4) -> np.ndarray:
    """Process CSI data by removing outliers and smoothing.

    This method:
    1. Unwraps phase and calculates phase velocity
    2. Detects and removes measurements with anomalous phase jumps
    3. Applies Savitzky-Golay filtering for smoothing

    Args:
        H: Complex CSI data of shape (num_measurements, num_subcarriers)
        sample_rate: Sampling rate in Hz (default: 0.4 Hz)

    Returns:
        Processed CSI data (may have fewer measurements due to outlier removal)
    """
    if H.size == 0 or len(H.shape) != 2:
        return H

    global_indices = np.arange(H.shape[0])

    # Antennas to check for outliers 
    remove_peaks_ant_p1 = [2, 3, 4, 6, 7, 8, 11, 13, 21, 23, 25, 27]

    # First pass: Remove major outliers
    unwrapped_phase = np.unwrap(np.angle(H), axis=0)
    phase_velocity = np.diff(unwrapped_phase, axis=0)

    indexes_to_remove = []
    for i in remove_peaks_ant_p1:
        if i >= phase_velocity.shape[1]:
            continue
            
        pv = phase_velocity[:, i]
        
        # Adaptive threshold based on standard deviation
        min_peak_prominence = np.std(np.abs(pv)) * 4
        min_peak_distance = int(max(1, round(0.005 / sample_rate)))  # Minimum 5ms between peaks
        
        # Find peaks in absolute phase velocity
        peaks, _ = find_peaks(np.abs(pv), 
                                prominence=min_peak_prominence,
                                distance=min_peak_distance)
        
        # Remove peak and neighboring measurements
        for peak in peaks:
            indexes_to_remove.extend([peak-1, peak, peak+1, peak+2])  # +2 because diff reduces size by 1

    # Remove duplicates and invalid indexes
    indexes_to_remove = np.unique(indexes_to_remove)
    indexes_to_remove = indexes_to_remove[(indexes_to_remove >= 0) & (indexes_to_remove < len(H))]

    if len(indexes_to_remove) > 0:
        H = np.delete(H, indexes_to_remove, axis=0)
        global_indices = np.delete(global_indices, indexes_to_remove)

    # Second pass: Remove remaining outliers with stricter threshold
    if H.shape[0] > 2:
        unwrapped_phase = np.unwrap(np.angle(H), axis=0)
        phase_velocity = np.diff(unwrapped_phase, axis=0)
        
        indexes_to_remove = []
        for i in remove_peaks_ant_p1:
            if i >= phase_velocity.shape[1]:
                continue
                
            pv = phase_velocity[:, i]
            
            # Stricter threshold
            min_peak_prominence = np.std(np.abs(pv)) * 4.2
            min_peak_distance = int(max(1, round(0.005 / sample_rate)))
            
            peaks, _ = find_peaks(np.abs(pv), 
                                    prominence=min_peak_prominence,
                                    distance=min_peak_distance)
            
            for peak in peaks:
                indexes_to_remove.extend([peak-1, peak, peak+1, peak+2])
        
        indexes_to_remove = np.unique(indexes_to_remove)
        indexes_to_remove = indexes_to_remove[(indexes_to_remove >= 0) & (indexes_to_remove < len(H))]
        
        if len(indexes_to_remove) > 0:
            H = np.delete(H, indexes_to_remove, axis=0)
            global_indices = np.delete(global_indices, indexes_to_remove)

    # Apply Savitzky-Golay filter for smoothing
    if H.shape[0] >= 9:  # Need at least window_length points
        window_length = 9  # Must be odd
        poly_order = 1
        
        smoothed_channel = np.zeros_like(H, dtype=complex)
        for i in range(H.shape[1]):
            # Filter real and imaginary parts separately
            smoothed_channel[:, i] = savgol_filter(H[:, i].real, window_length, poly_order) + \
                                    1j * savgol_filter(H[:, i].imag, window_length, poly_order)
        
        H = smoothed_channel

    return (H, global_indices)