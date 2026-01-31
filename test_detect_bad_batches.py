#!/usr/bin/env python3
"""
Test script to verify detect_bad_batches only checks CSI data, not FTM data.
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'data_processing'))

from session_data import detect_bad_batches, SessionData

def test_detect_bad_batches_ftm():
    """Test that detect_bad_batches doesn't flag missing FTM as bad."""
    
    # Test with new session that has FTM data
    session_dir = Path("data/2026-01-31/session_132737")
    
    if not session_dir.exists():
        print(f"Session not found: {session_dir}")
        return
    
    print("="*60)
    print("Testing detect_bad_batches with FTM-enabled session")
    print("="*60)
    
    # Load session first to see what we have
    session = SessionData.from_directory(session_dir)
    print("\nSession Summary:")
    print(session.summary())
    
    # Check FTM availability per data point
    print("\nFTM availability per data point:")
    for dp in session.data_points:
        ftm_info = "has FTM" if dp.ftm_batch_info and dp.ftm_batch_info.get('measurement_count', 0) > 0 else "no FTM"
        print(f"  Data point {dp.index}: {ftm_info}")
    
    # Now run detect_bad_batches
    print("\n" + "="*60)
    print("Running detect_bad_batches (should only check CSI)...")
    print("="*60)
    bad_indices = detect_bad_batches(session_dir, verbose=True)
    
    if len(bad_indices) == 0:
        print("\n✓ SUCCESS: No batches flagged as bad!")
        print("  (Even though some batches have no FTM data)")
    else:
        print(f"\n✗ WARNING: {len(bad_indices)} batches flagged as bad: {bad_indices}")
        print("  This could be legitimate if CSI data is actually invalid")

def test_old_session_format():
    """Test backward compatibility with old session format."""
    
    session_dir = Path("data/2025-11-20/session_135938")
    
    if not session_dir.exists():
        print(f"\nOld session not found: {session_dir}, skipping test")
        return
    
    print("\n\n" + "="*60)
    print("Testing detect_bad_batches with old session format")
    print("="*60)
    
    # Run detect_bad_batches on old format
    bad_indices = detect_bad_batches(session_dir, verbose=True)
    
    if len(bad_indices) == 0:
        print("\n✓ SUCCESS: Backward compatibility maintained!")
    else:
        print(f"\n✗ Found {len(bad_indices)} bad batches in old session")

if __name__ == "__main__":
    test_detect_bad_batches_ftm()
    test_old_session_format()
