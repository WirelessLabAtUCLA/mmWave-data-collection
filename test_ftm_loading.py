#!/usr/bin/env python3
"""
Test script to verify FTM data loading functionality.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'data_processing'))

from session_data import SessionData
import numpy as np

def test_ftm_loading():
    """Test FTM data loading with the 2026-01-31 session."""
    
    # Load the session with FTM data
    session_dir = Path("data/2026-01-31/session_132737")
    
    print("="*60)
    print("Testing FTM Data Loading")
    print("="*60)
    
    # Load session
    print(f"\nLoading session from: {session_dir}")
    session = SessionData.from_directory(session_dir)
    
    # Print session summary
    print("\nSession Summary:")
    print(session.summary())
    
    # Load router batches (CSI data)
    print("\nLoading CSI batches...")
    session.load_all_router_batches()
    csi_data = session.get_csi_data(averaged=False)
    print(f"CSI data shape: {csi_data.shape}")
    print(f"Total CSI measurements: {len(csi_data)}")
    
    # Load FTM data
    print("\nLoading FTM batches...")
    ftm_batches = session.load_all_ftm_batches()
    
    # Show FTM batch info
    print(f"\nFTM batch info:")
    for i, (dp, ftm_batch) in enumerate(zip(session.data_points, ftm_batches)):
        if ftm_batch is not None:
            print(f"  Data point {dp.index}: {ftm_batch.count} FTM measurements")
        else:
            print(f"  Data point {dp.index}: No FTM data")
    
    # Get FTM data aligned with CSI
    print("\nGetting FTM data aligned with CSI...")
    ftm_data = session.get_ftm_data()
    print(f"FTM data shape: {ftm_data.shape}")
    print(f"Total FTM measurements (padded): {len(ftm_data)}")
    
    # Verify sizes match
    print(f"\nVerification:")
    if len(csi_data) == len(ftm_data):
        print(f"✓ CSI and FTM data sizes match! ({len(csi_data)} measurements)")
    else:
        print(f"✗ Size mismatch: CSI={len(csi_data)}, FTM={len(ftm_data)}")
    
    # Check how many FTM measurements are non-zero
    non_zero_ftm = np.sum(np.any(ftm_data != 0, axis=1))
    print(f"  Non-zero FTM measurements: {non_zero_ftm}/{len(ftm_data)}")
    print(f"  Zero-padded measurements: {len(ftm_data) - non_zero_ftm}/{len(ftm_data)}")
    
    # Show sample FTM data
    print("\nSample FTM timestamps (first non-zero measurement):")
    for i, timestamps in enumerate(ftm_data):
        if np.any(timestamps != 0):
            print(f"  Measurement {i}: t1={timestamps[0]}, t2={timestamps[1]}, "
                  f"t3={timestamps[2]}, t4={timestamps[3]}")
            break
    
    # Test RTT calculation
    print("\nGetting RTT data...")
    rtt_data = session.get_ftm_rtt_data()
    print(f"RTT data shape: {rtt_data.shape}")
    non_zero_rtt = np.sum(rtt_data != 0)
    print(f"  Non-zero RTT values: {non_zero_rtt}/{len(rtt_data)}")
    
    if non_zero_rtt > 0:
        non_zero_rtts = rtt_data[rtt_data != 0]
        print(f"  RTT statistics (picoseconds):")
        print(f"    Min: {np.min(non_zero_rtts)}")
        print(f"    Max: {np.max(non_zero_rtts)}")
        print(f"    Mean: {np.mean(non_zero_rtts):.2f}")
        print(f"    Std: {np.std(non_zero_rtts):.2f}")
    
    print("\n" + "="*60)
    print("Test completed successfully!")
    print("="*60)

def test_backward_compatibility():
    """Test backward compatibility with old session format."""
    
    print("\n\n")
    print("="*60)
    print("Testing Backward Compatibility (Old Session Format)")
    print("="*60)
    
    # Load an old session without FTM data
    session_dir = Path("data/2025-11-20/session_135938")
    
    if not session_dir.exists():
        print(f"Old session not found at {session_dir}, skipping backward compatibility test")
        return
    
    print(f"\nLoading old session from: {session_dir}")
    session = SessionData.from_directory(session_dir)
    
    # Print session summary
    print("\nSession Summary:")
    print(session.summary())
    
    # Load router batches
    print("\nLoading CSI batches...")
    session.load_all_router_batches()
    csi_data = session.get_csi_data(averaged=False)
    print(f"CSI data shape: {csi_data.shape}")
    
    # Try to load FTM data (should return all zeros)
    print("\nAttempting to load FTM data (should return zeros)...")
    ftm_data = session.get_ftm_data()
    print(f"FTM data shape: {ftm_data.shape}")
    
    # Verify all zeros
    if np.all(ftm_data == 0):
        print("✓ FTM data is all zeros (expected for old sessions)")
    else:
        print("✗ FTM data contains non-zero values (unexpected)")
    
    # Verify sizes match
    if len(csi_data) == len(ftm_data):
        print(f"✓ CSI and FTM data sizes match! ({len(csi_data)} measurements)")
    else:
        print(f"✗ Size mismatch: CSI={len(csi_data)}, FTM={len(ftm_data)}")
    
    print("\n" + "="*60)
    print("Backward compatibility test completed!")
    print("="*60)

if __name__ == "__main__":
    test_ftm_loading()
    test_backward_compatibility()
