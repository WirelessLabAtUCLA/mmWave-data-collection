#!/usr/bin/env python3
"""
Example script showing how to use the FTM data loading functionality.

This script demonstrates:
1. Loading a session with FTM data
2. Getting FTM timestamps aligned with CSI data
3. Computing RTT from FTM data
4. Working with FTM data that may have missing values
"""

from pathlib import Path
from session_data import SessionData
import numpy as np

def example_ftm_usage():
    """Example of using FTM data loading functionality."""
    
    # Load a session with FTM data
    session_dir = Path("../data/2026-01-31/session_132737")
    session = SessionData.from_directory(session_dir)
    
    print("Session loaded:", session.session_id)
    print(session.summary())
    
    # Load all router batches (CSI data)
    session.load_all_router_batches()
    
    # Get CSI data
    csi_data = session.get_csi_data(averaged=False)
    print(f"\nCSI data shape: {csi_data.shape}")
    print(f"  -> {csi_data.shape[0]} measurements, {csi_data.shape[1]} antennas")
    
    # Get FTM data (automatically aligned with CSI)
    ftm_data = session.get_ftm_data()
    print(f"\nFTM data shape: {ftm_data.shape}")
    print(f"  -> {ftm_data.shape[0]} measurements, {ftm_data.shape[1]} timestamps (t1,t2,t3,t4)")
    
    # Check which measurements have FTM data
    has_ftm = np.any(ftm_data != 0, axis=1)
    print(f"\nMeasurements with FTM data: {np.sum(has_ftm)}/{len(ftm_data)}")
    
    # Get RTT (Round Trip Time) data
    rtt_data = session.get_ftm_rtt_data()
    print(f"\nRTT data shape: {rtt_data.shape}")
    
    # Compute statistics on valid RTT values
    valid_rtt = rtt_data[rtt_data != 0]
    if len(valid_rtt) > 0:
        print(f"\nRTT Statistics (picoseconds):")
        print(f"  Count: {len(valid_rtt)}")
        print(f"  Min: {np.min(valid_rtt)}")
        print(f"  Max: {np.max(valid_rtt)}")
        print(f"  Mean: {np.mean(valid_rtt):.2f}")
        print(f"  Std: {np.std(valid_rtt):.2f}")
        
        # Convert to nanoseconds for easier interpretation
        print(f"\nRTT Statistics (nanoseconds):")
        print(f"  Mean: {np.mean(valid_rtt)/1000:.2f} ns")
        print(f"  Std: {np.std(valid_rtt)/1000:.2f} ns")
    
    # Example: Process data where FTM is available
    print(f"\n{'='*60}")
    print("Example: Working with measurements that have FTM data")
    print('='*60)
    
    # Filter to only include measurements with FTM data
    csi_with_ftm = csi_data[has_ftm]
    ftm_with_data = ftm_data[has_ftm]
    rtt_with_data = rtt_data[has_ftm]
    
    print(f"\nFiltered data shapes:")
    print(f"  CSI with FTM: {csi_with_ftm.shape}")
    print(f"  FTM timestamps: {ftm_with_data.shape}")
    print(f"  RTT values: {rtt_with_data.shape}")
    
    # Example: Access individual FTM timestamps
    if len(ftm_with_data) > 0:
        print(f"\nFirst FTM measurement:")
        t1, t2, t3, t4 = ftm_with_data[0]
        print(f"  t1 (packet left initiator): {t1} ps")
        print(f"  t2 (packet arrived responder): {t2} ps")
        print(f"  t3 (ACK left responder): {t3} ps")
        print(f"  t4 (ACK arrived initiator): {t4} ps")
        print(f"  RTT: {rtt_with_data[0]} ps = {rtt_with_data[0]/1000:.2f} ns")
    
    # Example: Work with both CSI and FTM per data point
    print(f"\n{'='*60}")
    print("Example: Per-batch analysis")
    print('='*60)
    
    for i, dp in enumerate(session.data_points[:3]):  # First 3 data points
        print(f"\nData Point {dp.index}:")
        
        # Load router batch
        router_batch = dp.load_router_batch(session.session_dir)
        print(f"  CSI measurements: {len(router_batch.csi_processed_data)}")
        
        # Load FTM batch
        ftm_batch = dp.load_ftm_batch(session.session_dir)
        if ftm_batch is not None:
            print(f"  FTM measurements: {ftm_batch.count}")
            if ftm_batch.count > 0:
                rtt_values = ftm_batch.get_all_rtt()
                print(f"  Mean RTT: {np.mean(rtt_values):.2f} ps = {np.mean(rtt_values)/1000:.2f} ns")
        else:
            print(f"  FTM measurements: 0 (no FTM data)")
    
    print(f"\n{'='*60}")
    print("Example completed!")
    print('='*60)


def example_backward_compatibility():
    """Example showing backward compatibility with old sessions."""
    
    print(f"\n\n{'='*60}")
    print("Backward Compatibility Example")
    print('='*60)
    
    # Load an old session without FTM data
    session_dir = Path("../data/2025-11-20/session_135938")
    
    if not session_dir.exists():
        print("Old session not available, skipping this example")
        return
    
    session = SessionData.from_directory(session_dir)
    print(f"\nLoaded old session: {session.session_id}")
    
    # Load all data
    session.load_all_router_batches()
    
    # Get CSI and FTM data
    csi_data = session.get_csi_data(averaged=False)
    ftm_data = session.get_ftm_data()
    
    print(f"\nCSI data shape: {csi_data.shape}")
    print(f"FTM data shape: {ftm_data.shape}")
    print(f"Sizes match: {len(csi_data) == len(ftm_data)}")
    print(f"FTM data is all zeros: {np.all(ftm_data == 0)}")
    
    print("\n✓ Old sessions work correctly (FTM filled with zeros)")


if __name__ == "__main__":
    example_ftm_usage()
    example_backward_compatibility()
