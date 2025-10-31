"""
Example usage of the SessionData class for loading and analyzing mmWave data.
"""

from pathlib import Path
from session_data import SessionData, load_all_sessions


def main():
    # Example 1: Load a single session
    print("=" * 60)
    print("Example 1: Loading a single session")
    print("=" * 60)
    
    session_dir = Path("../data/2025-10-30/session_141256")
    session = SessionData.from_directory(session_dir)
    
    print(session.summary())
    print()
    
    # Example 2: Access GPS trajectory
    print("=" * 60)
    print("Example 2: GPS Trajectory")
    print("=" * 60)
    
    trajectory = session.get_gps_trajectory()
    print(f"Trajectory shape: {trajectory.shape}")
    print(f"First GPS point: Lat={trajectory[0, 0]:.6f}, Lon={trajectory[0, 1]:.6f}, Alt={trajectory[0, 2]:.1f}m")
    print(f"Last GPS point: Lat={trajectory[-1, 0]:.6f}, Lon={trajectory[-1, 1]:.6f}, Alt={trajectory[-1, 2]:.1f}m")
    print()
    
    # Example 3: Access a specific data point
    print("=" * 60)
    print("Example 3: Accessing specific data point")
    print("=" * 60)
    
    data_point = session.get_data_point(19)  # Get data point at index 19
    if data_point:
        print(f"Data Point {data_point.index}")
        print(f"  Timestamp: {data_point.timestamp}")
        print(f"  GPS: ({data_point.gps.latitude:.6f}, {data_point.gps.longitude:.6f})")
        print(f"  Altitude: {data_point.gps.altitude:.1f}m")
        print(f"  Image: {data_point.image_path.name if data_point.image_path else 'N/A'}")
        print(f"  Batch ID: {data_point.router_batch_info['batch_id']}")
        print()
    
    # Example 4: Load and analyze router batch data
    print("=" * 60)
    print("Example 4: Router batch data")
    print("=" * 60)
    
    # Load router batch for first data point
    first_dp = session.data_points[0]
    router_batch = first_dp.load_router_batch(session.session_dir)
    
    print(f"Batch ID: {router_batch.batch_id}")
    print(f"Timestamp: {router_batch.timestamp}")
    print(f"Number of measurements: {router_batch.count}")
    print(f"Measurements loaded: {len(router_batch.measurements)}")
    
    if router_batch.measurements:
        first_measurement = router_batch.measurements[0]
        print(f"\nFirst measurement:")
        print(f"  MAC Address: {first_measurement.mac_address}")
        print(f"  Timestamp: {first_measurement.timestamp_seconds}")
        print(f"  Raw data length: {len(first_measurement.raw_data)}")
        
        phase_data = first_measurement.get_phase_data()
        if phase_data:
            print(f"  Phase data: {len(phase_data)} values")
            print(f"  Phase sample: {phase_data[:5]}")
    
    print()
    
    # Example 5: Get phase data from batch
    print("=" * 60)
    print("Example 5: Phase data analysis")
    print("=" * 60)
    
    phase_data = router_batch.get_all_phase_data()
    if phase_data.size > 0:
        print(f"Phase data shape: {phase_data.shape}")
        print(f"Phase data mean: {phase_data.mean():.2f}")
        print(f"Phase data std: {phase_data.std():.2f}")
        print(f"Phase data range: [{phase_data.min()}, {phase_data.max()}]")
    print()
    
    # Example 6: Load all sessions from a date directory
    print("=" * 60)
    print("Example 6: Loading all sessions from a date")
    print("=" * 60)
    
    data_dir = Path("../data/2025-10-30")
    all_sessions = load_all_sessions(data_dir)
    
    print(f"Loaded {len(all_sessions)} sessions:")
    for session_id, session_data in all_sessions.items():
        print(f"  - {session_id}: {session_data.total_samples} samples, "
              f"Duration: {session_data.get_duration():.1f}s")
    print()
    
    # Example 7: Iterate through all data points
    print("=" * 60)
    print("Example 7: Iterating through data points")
    print("=" * 60)
    
    print("First 5 data points with their GPS coordinates:")
    for i, dp in enumerate(session.data_points[:5]):
        print(f"  {i+1}. Index {dp.index}: "
              f"({dp.gps.latitude:.6f}, {dp.gps.longitude:.6f}) "
              f"@ {dp.timestamp.strftime('%H:%M:%S')}")
    print()
    
    # Example 8: Get all timestamps
    print("=" * 60)
    print("Example 8: Timestamp analysis")
    print("=" * 60)
    
    timestamps = session.get_timestamps()
    if len(timestamps) > 1:
        time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                      for i in range(len(timestamps)-1)]
        avg_interval = sum(time_diffs) / len(time_diffs)
        print(f"Average time interval between samples: {avg_interval:.3f}s")
        print(f"Min interval: {min(time_diffs):.3f}s")
        print(f"Max interval: {max(time_diffs):.3f}s")
    print()


if __name__ == "__main__":
    main()

