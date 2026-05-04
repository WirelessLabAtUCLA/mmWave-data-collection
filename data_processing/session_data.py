"""
Data classes for reading and storing mmWave data collection session data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import numpy as np
import re
import os

from utils import process_csi_data

FREQ_CHANNELS = {1 : 58.32, 2 : 60.48, 3 : 62.64, 4 : 64.8}

@dataclass
class SlamPose:
    """6-DOF pose from RTAB-Map visual-inertial odometry.

    Position is in metres relative to the SLAM map origin.
    Orientation is a unit quaternion (x, y, z, w).
    """
    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'SlamPose':
        return cls(
            x=data['x'], y=data['y'], z=data['z'],
            qx=data['qx'], qy=data['qy'], qz=data['qz'], qw=data['qw'],
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            'x': self.x, 'y': self.y, 'z': self.z,
            'qx': self.qx, 'qy': self.qy, 'qz': self.qz, 'qw': self.qw,
        }

    def xy(self) -> tuple:
        """Return (x, y) position in metres."""
        return (self.x, self.y)


@dataclass
class RouterMeasurement:
    """Single router measurement from AOA/CSI data.
    
    Parses measurement strings according to the format:
    [system_timestamp] [AOA] Measurement: return_code,measurement_time,peer_mac,
    channel,measurement_type,rf_mask,measurement_status,length,
    phase[0-31],magnitude[0-31]
    """
    system_timestamp: float
    return_code: int
    measurement_time: float
    peer_mac: str
    channel: int
    measurement_type: int
    rf_mask: int
    measurement_status: int
    length: int
    phase: List[int]
    magnitude: List[int]
    raw_string: str
    
    @classmethod
    def from_string(cls, measurement_string: str) -> 'RouterMeasurement':
        """Parse a measurement string from the router data.
        
        Example format:
        "[ 530.502229] [AOA] Measurement: 0,1626941747.663218,f4:1e:57:64:92:ae,2,1,2,0,128,355,44,928,..."
        
        Args:
            measurement_string: Raw measurement string from router
            
        Returns:
            RouterMeasurement object with parsed data
            
        Raises:
            ValueError: If the measurement string cannot be parsed
        """
        
        # Extract system timestamp from brackets
        timestamp_match = re.search(r'\[\s*(\d+\.\d+)\]', measurement_string)
        if not timestamp_match:
            raise ValueError("Could not extract system timestamp")
        system_timestamp = float(timestamp_match.group(1))
        
        # Extract the measurement data after "Measurement: "
        if '[AOA] Measurement:' in measurement_string:
            data_part = measurement_string.split('[AOA] Measurement:')[1].strip()
        else:
            data_part = measurement_string.strip()
        
        # Split by comma
        parts = data_part.split(',')
        
        # Validate minimum number of expected parts
        # Need: 8 metadata fields + 32 phase + 32 magnitude = 72 total
        if len(parts) < 72:
            raise ValueError(f"Insufficient data parts: expected 72, got {len(parts)}")
        
        # Parse metadata fields
        return_code = int(parts[0])
        measurement_time = float(parts[1])
        peer_mac = parts[2]
        channel = int(parts[3])
        measurement_type = int(parts[4])
        rf_mask = int(parts[5])
        measurement_status = int(parts[6])
        length_val = int(parts[7])
        
        # Extract phase values (32 values starting at index 8)
        phase_start = 8
        phase_end = phase_start + 32
        phase = [int(parts[i]) for i in range(phase_start, phase_end)]
        
        # Extract magnitude values (32 values after phase)
        magnitude_start = phase_end
        magnitude_end = magnitude_start + 32
        magnitude = [int(parts[i]) for i in range(magnitude_start, magnitude_end)]
        
        return cls(
            system_timestamp=system_timestamp,
            return_code=return_code,
            measurement_time=measurement_time,
            peer_mac=peer_mac,
            channel=channel,
            measurement_type=measurement_type,
            rf_mask=rf_mask,
            measurement_status=measurement_status,
            length=length_val,
            phase=phase,
            magnitude=magnitude,
            raw_string=measurement_string
        )
    
    def get_phase_data(self) -> List[int]:
        """Get phase data (32 values).
        
        Returns:
            List of 32 phase values
        """
        return self.phase
    
    def get_magnitude_data(self) -> List[int]:
        """Get magnitude data (32 values).
        
        Returns:
            List of 32 magnitude values
        """
        return self.magnitude
    

@dataclass
class FTMMeasurement:
    """Single FTM (Fine Time Measurement) measurement.
    
    Parses FTM measurement strings according to the format:
    [system_timestamp] wil6210 ... [FTM] Measurement: t1,t2,t3,t4
    
    The four timestamps (t1, t2, t3, t4) are in picoseconds and represent:
    - t1: Time packet left initiator
    - t2: Time packet arrived at responder
    - t3: Time ACK left responder
    - t4: Time ACK arrived at initiator
    """
    system_timestamp: float
    t1: int  # picoseconds
    t2: int  # picoseconds
    t3: int  # picoseconds
    t4: int  # picoseconds
    raw_string: str
    
    @classmethod
    def from_string(cls, measurement_string: str) -> 'FTMMeasurement':
        """Parse an FTM measurement string.
        
        Example format:
        "[ 6477.673180] wil6210 0000:01:00.0 wlan0: wil_ftm_evt_per_dest_res: [FTM] Measurement: 36147079068, 43575762336, 43584915456, 36158089524"
        
        Args:
            measurement_string: Raw FTM measurement string
            
        Returns:
            FTMMeasurement object with parsed data
            
        Raises:
            ValueError: If the measurement string cannot be parsed
        """
        # Extract system timestamp from brackets
        timestamp_match = re.search(r'\[\s*(\d+\.\d+)\]', measurement_string)
        if not timestamp_match:
            raise ValueError("Could not extract system timestamp")
        system_timestamp = float(timestamp_match.group(1))
        
        # Extract the measurement data after "[FTM] Measurement:"
        if '[FTM] Measurement:' in measurement_string:
            data_part = measurement_string.split('[FTM] Measurement:')[1].strip()
        else:
            raise ValueError("FTM Measurement marker not found")
        
        # Split by comma and parse the 4 timestamps
        parts = [p.strip() for p in data_part.split(',')]
        
        if len(parts) < 4:
            raise ValueError(f"Insufficient FTM data: expected 4 timestamps, got {len(parts)}")
        
        try:
            t1 = int(parts[0])
            t2 = int(parts[1])
            t3 = int(parts[2])
            t4 = int(parts[3])
        except ValueError as e:
            raise ValueError(f"Failed to parse FTM timestamps: {e}")
        
        return cls(
            system_timestamp=system_timestamp,
            t1=t1,
            t2=t2,
            t3=t3,
            t4=t4,
            raw_string=measurement_string
        )
    
    def get_timestamps(self) -> List[int]:
        """Get all four timestamps as a list.
        
        Returns:
            List of [t1, t2, t3, t4] in picoseconds
        """
        return [self.t1, self.t2, self.t3, self.t4]
    
    def calculate_rtt(self) -> int:
        """Calculate Round Trip Time in picoseconds.
        
        RTT = (t4 - t1) - (t3 - t2)
        
        Returns:
            RTT in picoseconds
        """
        return (self.t4 - self.t1) - (self.t3 - self.t2)
    
    def calculate_distance(self) -> float:
        """Calculate distance in meters.
        
        Returns:
            Distance in meters
        """
        return 3e8 * self.calculate_rtt() / 2


@dataclass
class FTMBatch:
    """Batch of FTM measurements."""
    batch_id: int
    timestamp: datetime
    measurements: List[FTMMeasurement]
    count: int
    file_path: Optional[Path] = None
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'FTMBatch':
        """Load FTM batch data from JSON file.
        
        Skips measurements that cannot be parsed (poor quality data).
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        measurements = []
        skipped_count = 0
        
        for i, measurement_str in enumerate(data['measurements']):
            try:
                measurement = FTMMeasurement.from_string(measurement_str)
                measurements.append(measurement)
            except (ValueError, IndexError) as e:
                # Skip poor quality measurements
                skipped_count += 1
                # Optionally log warning (uncomment for debugging)
                # print(f"Warning: Skipped FTM measurement {i} in batch {data['batch_id']}: {e}")
        
        return cls(
            batch_id=data['batch_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            measurements=measurements,
            count=len(measurements),
            file_path=file_path
        )
    
    def get_all_timestamps(self) -> np.ndarray:
        """Get all FTM timestamps as a numpy array.
        
        Returns:
            Numpy array of shape (num_measurements, 4) containing [t1, t2, t3, t4] in picoseconds
        """
        if not self.measurements:
            return np.array([])
        
        timestamps = []
        for measurement in self.measurements:
            timestamps.append(measurement.get_timestamps())
        return np.array(timestamps, dtype=np.int64)
    
    def get_all_rtt(self) -> np.ndarray:
        """Get all RTT values as a numpy array.
        
        Returns:
            Numpy array of RTT values in picoseconds
        """
        if not self.measurements:
            return np.array([])
        
        return np.array([m.calculate_rtt() for m in self.measurements], dtype=np.int64)
    
    def get_all_distance(self) -> np.ndarray:
        """Get all distance values as a numpy array.
        
        Returns:
            Numpy array of distance values in meters
        """
        if not self.measurements:
            return np.array([])
        
        return np.array([m.calculate_distance() for m in self.measurements], dtype=np.float64)


@dataclass
class RouterBatch:
    """Batch of router measurements."""
    batch_id: int
    timestamp: datetime
    csi_processed_data: np.ndarray
    averaged_csi_data: np.ndarray
    measurements: List[RouterMeasurement]
    count: int
    file_path: Optional[Path] = None
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'RouterBatch':
        """Load router batch data from JSON file.
        
        Skips measurements that cannot be parsed (poor quality data).
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        measurements = []
        skipped_count = 0
        
        for i, measurement_str in enumerate(data['measurements']):
            try:
                measurement = RouterMeasurement.from_string(measurement_str)
                measurements.append(measurement)
            except (ValueError, IndexError) as e:
                # Skip poor quality measurements
                skipped_count += 1
                # Optionally log warning (uncomment for debugging)
                print(f"Warning: Skipped measurement {i} in batch {data['batch_id']}: {e}")

        # Process CSI data if we have valid measurements
        csi_processed_data = np.array([])
        averaged_csi_data = np.array([])
        valid_antennas = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 21, 23, 25, 27];
        if len(measurements) > 0:
            phase_range = np.linspace(0, 2*np.pi, 1024)
            phase_data = []
            magnitude_data = []
            for measurement in measurements:
                phase_data.append(measurement.get_phase_data())
                magnitude_data.append(measurement.get_magnitude_data())
            
            phase_data = np.array(phase_data)
            magnitude_data = np.array(magnitude_data)
            # Convert phase indices to radians
            phase_radians = phase_range[phase_data.astype(int)]

            # Create complex CSI from phase
            H = np.exp(1j * phase_radians)
            H = H[:, valid_antennas]
            csi_processed_data = process_csi_data(H)
            averaged_csi_data = np.mean(csi_processed_data, axis=0)

        return cls(
            batch_id=data['batch_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            csi_processed_data=csi_processed_data,
            averaged_csi_data=averaged_csi_data,
            measurements=measurements,
            count=len(csi_processed_data),  # Update count to actual valid measurements
            file_path=file_path
        )
    
    def get_all_phase_data(self) -> np.ndarray:
        """Get phase data from all measurements as a numpy array.
        
        Returns:
            Numpy array of shape (num_measurements, 32) containing phase values
        """
        phase_data = []
        phase_range = np.linspace(0, 2*np.pi, 1024)
        for measurement in self.measurements:
            phases = measurement.get_phase_data()
            if phases and len(phases) == 32:
                phase_data.append(phases)
        phase_data = np.array(phase_data)
        phase_data = phase_range[phase_data.astype(int)]
        return phase_data
    
    def get_all_magnitude_data(self) -> np.ndarray:
        """Get magnitude data from all measurements as a numpy array.
        
        Returns:
            Numpy array of shape (num_measurements, 32) containing magnitude values
        """
        magnitude_data = []
        for measurement in self.measurements:
            magnitudes = measurement.get_magnitude_data()
            if magnitudes and len(magnitudes) == 32:
                magnitude_data.append(magnitudes)
        return np.array(magnitude_data) if magnitude_data else np.array([])
    
    

@dataclass
class DataPoint:
    """Single data point in a session."""
    index: int
    timestamp: datetime
    slam_pose: Optional[SlamPose]  # None when RTAB-Map was not running during collection
    router_batch_info: Dict[str, Any]
    ftm_batch_info: Optional[Dict[str, Any]] = None
    image_path: Optional[Path] = None
    router_batch: Optional[RouterBatch] = None
    ftm_batch: Optional[FTMBatch] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], session_dir: Path) -> 'DataPoint':
        """Create DataPoint from dictionary.

        Handles:
          - New format: slam_pose (dict or null) + router_batch
          - Old format: gps dict + csi_batch/router_batch (GPS mapped to XY for
            backward compatibility; lon→x, lat→y, alt→z with identity orientation)
        """
        router_batch_info = data.get('csi_batch') or data.get('router_batch')
        ftm_batch_info = data.get('ftm_batch')

        slam_pose: Optional[SlamPose] = None
        raw_pose = data.get('slam_pose')
        if raw_pose:
            slam_pose = SlamPose.from_dict(raw_pose)
        elif 'gps' in data and data['gps']:
            gps = data['gps']
            slam_pose = SlamPose(
                x=float(gps.get('longitude', 0.0)),
                y=float(gps.get('latitude', 0.0)),
                z=float(gps.get('altitude', 0.0)),
                qx=0.0, qy=0.0, qz=0.0, qw=1.0,
            )

        return cls(
            index=data['index'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            slam_pose=slam_pose,
            router_batch_info=router_batch_info,
            ftm_batch_info=ftm_batch_info,
            image_path=session_dir / data['image'] if 'image' in data else None,
            router_batch=None,
            ftm_batch=None,
        )

    def load_router_batch(self, session_dir: Path) -> RouterBatch:
        """Load the associated router batch data."""
        if self.router_batch is None:
            batch_file = session_dir / self.router_batch_info['file']
            self.router_batch = RouterBatch.from_file(batch_file)
        return self.router_batch

    def load_ftm_batch(self, session_dir: Path) -> Optional[FTMBatch]:
        """Load the associated FTM batch data if it exists."""
        if self.ftm_batch_info is None:
            return None
        if self.ftm_batch is None:
            batch_file = session_dir / self.ftm_batch_info['file']
            if batch_file.exists():
                self.ftm_batch = FTMBatch.from_file(batch_file)
            else:
                return None
        return self.ftm_batch

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'index': self.index,
            'timestamp': self.timestamp.isoformat(),
            'slam_pose': self.slam_pose.to_dict() if self.slam_pose else None,
            'router_batch_info': self.router_batch_info,
            'image_path': str(self.image_path) if self.image_path else None,
        }
        if self.ftm_batch_info is not None:
            result['ftm_batch_info'] = self.ftm_batch_info
        return result


@dataclass
class SessionData:
    """Complete session data."""
    session_id: str
    start_time: datetime
    end_time: datetime
    total_samples: int
    data_points: List[DataPoint]
    session_dir: Path
    frequency: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_directory(cls, session_dir: Path, channel: int = 1) -> 'SessionData':
        """Load session data from a directory.
        
        Args:
            session_dir: Path to session directory containing metadata.json
        
        Returns:
            SessionData object with all session information
        """
        if channel not in FREQ_CHANNELS:
            raise ValueError(f"Invalid channel: {channel}")
        session_dir = Path(session_dir)
        metadata_file = session_dir / 'metadata.json'
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        data_points = [
            DataPoint.from_dict(dp, session_dir) 
            for dp in metadata['data_points']
        ]
        
        # end_time and total_samples are written on clean shutdown; fall back
        # gracefully for sessions that were interrupted mid-collection.
        end_time_str = metadata.get('end_time') or metadata['start_time']
        total_samples = metadata.get('total_samples', len(data_points))

        return cls(
            session_id=metadata['session_id'],
            start_time=datetime.fromisoformat(metadata['start_time']),
            end_time=datetime.fromisoformat(end_time_str),
            total_samples=total_samples,
            data_points=data_points,
            session_dir=session_dir,
            metadata=metadata,
            frequency=FREQ_CHANNELS[channel],
        )

    def get_csi_data(self, averaged: bool = False) -> np.ndarray:
        """Get CSI data from all data points."""
        channel_data = np.zeros((1, 16), dtype=np.complex128)
        for dp in self.data_points:
            if averaged:
                csi_data = dp.router_batch.averaged_csi_data
            else:
                if dp.router_batch is None:
                    continue
                csi_data = dp.router_batch.csi_processed_data
            channel_data = np.vstack((channel_data, csi_data))
        return channel_data[1:, :]

    
    def load_all_router_batches(self) -> None:
        """Load all router batch data for all data points."""
        self.router_batches = []
        for data_point in self.data_points:
            self.router_batches.append(data_point.load_router_batch(self.session_dir))
        return self.router_batches
    
    def load_all_ftm_batches(self) -> List[Optional[FTMBatch]]:
        """Load all FTM batch data for all data points."""
        self.ftm_batches = []
        for data_point in self.data_points:
            ftm_batch = data_point.load_ftm_batch(self.session_dir)
            self.ftm_batches.append(ftm_batch)
        return self.ftm_batches

    def get_ftm_data(self) -> Dict[str, np.ndarray]:
        """Get per-batch averaged FTM data, with linear interpolation for missing batches.

        For each data point, if an FTM batch exists its RTT and distance
        measurements are averaged into a single value.  If no FTM batch is
        available for a data point, a placeholder of 0 is stored.  After all
        batches are processed the zeros are filled in by linearly interpolating
        between the surrounding valid (non-zero) values.  Leading / trailing
        zeros (before the first or after the last valid measurement) are
        clamped to the nearest valid value by np.interp.

        Returns:
            Dictionary with keys:
                'rtt'      – averaged RTT per batch in picoseconds (np.ndarray)
                'distance' – averaged distance per batch in metres  (np.ndarray)
        """
        rtt_raw: List[float] = []
        dist_raw: List[float] = []

        for dp in self.data_points:
            ftm_batch = dp.load_ftm_batch(self.session_dir)
            if ftm_batch is None or ftm_batch.count == 0:
                rtt_raw.append(0.0)
                dist_raw.append(0.0)
            else:
                rtt_raw.append(float(np.mean(ftm_batch.get_all_rtt())))
                dist_raw.append(float(np.mean(ftm_batch.get_all_distance())))

        rtt_arr  = np.array(rtt_raw,  dtype=np.float64)
        dist_arr = np.array(dist_raw, dtype=np.float64)

        # Linearly interpolate over missing (zero) entries
        indices = np.arange(len(rtt_arr))
        for arr in (rtt_arr, dist_arr):
            valid_mask = arr != 0.0
            if valid_mask.any() and not valid_mask.all():
                arr[:] = np.interp(indices, indices[valid_mask], arr[valid_mask])

        return {"rtt": rtt_arr, "distance": dist_arr}
        
    def get_data_point(self, index: int) -> Optional[DataPoint]:
        """Get a data point by index."""
        for dp in self.data_points:
            if dp.index == index:
                return dp
        return None
    
    def get_slam_trajectory(self) -> np.ndarray:
        """Get SLAM trajectory as numpy array of shape (N, 3) with columns [x, y, z] in metres.

        Only data points that have a valid SLAM pose are included.
        Returns an empty array if no pose data was recorded (e.g. RTAB-Map was not running).
        """
        trajectory = [
            [dp.slam_pose.x, dp.slam_pose.y, dp.slam_pose.z]
            for dp in self.data_points
            if dp.slam_pose is not None
        ]
        return np.array(trajectory) if trajectory else np.empty((0, 3))
    
    def get_timestamps(self) -> List[datetime]:
        """Get list of all timestamps."""
        return [dp.timestamp for dp in self.data_points]
    
    def get_duration(self) -> float:
        """Get session duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()
    
    def get_image_paths(self) -> List[Path]:
        """Get list of all image paths."""
        return [dp.image_path for dp in self.data_points if dp.image_path]

    def get_expanded_data_for_ml(self) -> tuple:
        """Get timestamps, CSI data, image paths, and pose data expanded to match individual CSI samples.

        Each batch may have a different number of CSI samples. This method expands
        the timestamps, image paths, and pose (x, y, z) so each CSI sample gets the
        values from its batch.

        Returns:
            Tuple of (timestamps, csi_data, image_paths, positions) where all have the
            same length. ``positions`` is a numpy array of shape (N, 3) with columns
            [x, y, z] in metres; rows are NaN when no SLAM pose was recorded for that
            batch.
            Requires load_all_router_batches() to have been called first.
        """
        expanded_timestamps = []
        expanded_image_paths = []
        expanded_positions = []
        all_csi_data = []

        for dp in self.data_points:
            if dp.router_batch is None:
                continue

            csi_data = dp.router_batch.csi_processed_data
            num_samples = len(csi_data)
            if num_samples == 0:
                continue

            if dp.slam_pose is not None:
                pos = [dp.slam_pose.x, dp.slam_pose.y, dp.slam_pose.z]
            else:
                pos = [float('nan'), float('nan'), float('nan')]

            expanded_timestamps.extend([dp.timestamp] * num_samples)
            expanded_image_paths.extend([dp.image_path] * num_samples)
            expanded_positions.extend([pos] * num_samples)
            all_csi_data.append(csi_data)

        csi_array = np.vstack(all_csi_data) if all_csi_data else np.array([])
        positions_array = np.array(expanded_positions, dtype=np.float64) if expanded_positions else np.empty((0, 3))

        return expanded_timestamps, csi_array, expanded_image_paths, positions_array

    def get_save_plot_path(self) -> Path:
        """Get the path to save the plot."""
        if not os.path.exists(self.session_dir / 'plots'):
            os.makedirs(self.session_dir / 'plots')
        return self.session_dir / 'plots' 
    
    def summary(self) -> str:
        """Get a summary string of the session."""
        duration = self.get_duration()
        ftm_count = sum(1 for dp in self.data_points if dp.ftm_batch_info is not None)
        pose_count = sum(1 for dp in self.data_points if dp.slam_pose is not None)

        trajectory = self.get_slam_trajectory()
        if len(trajectory) >= 2:
            total_dist = float(np.sum(np.linalg.norm(np.diff(trajectory[:, :2], axis=0), axis=1)))
            pose_str = f"{pose_count}/{len(self.data_points)} points | dist ≈ {total_dist:.2f} m"
        elif pose_count > 0:
            pose_str = f"{pose_count}/{len(self.data_points)} points"
        else:
            pose_str = "no pose data (RTAB-Map not running during collection)"

        return (
            f"Session: {self.session_id}\n"
            f"Start: {self.start_time}\n"
            f"End: {self.end_time}\n"
            f"Duration: {duration:.1f} seconds\n"
            f"Total Samples: {self.total_samples}\n"
            f"Data Points: {len(self.data_points)}\n"
            f"Data Points with FTM: {ftm_count}\n"
            f"Images: {len(self.get_image_paths())}\n"
            f"SLAM Pose: {pose_str}\n"
        )
    
    def __repr__(self) -> str:
        return f"SessionData(session_id='{self.session_id}', samples={self.total_samples})"


def detect_bad_batches(session_dir: Path, verbose: bool = True) -> List[int]:
    """Detect batches with insufficient or invalid CSI data.
    
    Only checks CSI/router batch data validity. FTM data is optional and
    missing FTM data does not flag a batch as bad.
    
    Args:
        session_dir: Path to session directory
        verbose: Whether to print detailed information about bad batches
    
    Returns:
        List of indices of bad batches (based on CSI data only)
    """
    session_dir = Path(session_dir)
    metadata_file = session_dir / 'metadata.json'
    
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    bad_indices = []
    
    if verbose:
        print(f"Scanning session: {metadata['session_id']}")
        print(f"Total data points: {len(metadata['data_points'])}")
        print("-" * 60)
    
    for i, data_point in enumerate(metadata['data_points']):
        # Check for CSI batch info (handle both old and new format)
        csi_batch_info = data_point.get('csi_batch') or data_point.get('router_batch')
        
        if not csi_batch_info or 'file' not in csi_batch_info:
            if verbose:
                print(f"Batch {i}: Missing CSI batch info")
            bad_indices.append(i)
            continue

        router_file = session_dir / csi_batch_info['file']
        if not router_file.exists():
            if verbose:
                print(f"Batch {i}: CSI file not found: {router_file.name}")
            bad_indices.append(i)
            continue
        
        try:
            with open(router_file, 'r') as f:
                batch_data = json.load(f)
            
            if 'measurements' not in batch_data or not batch_data['measurements']:
                if verbose:
                    print(f"Batch {i}: No CSI measurements found")
                bad_indices.append(i)
                continue

            # Count valid CSI measurements
            valid_measurements = 0
            for measurement_str in batch_data['measurements']:
                try:
                    RouterMeasurement.from_string(measurement_str)
                    valid_measurements += 1
                except (ValueError, IndexError):
                    pass
            
            # Only flag as bad if NO valid measurements exist
            if valid_measurements == 0:
                if verbose:
                    print(f"Batch {i}: All CSI measurements failed to parse (0/{len(batch_data['measurements'])} valid)")
                bad_indices.append(i)
                
        except Exception as e:
            if verbose:
                print(f"Batch {i}: Error loading CSI batch: {e}")
            bad_indices.append(i)
    
    if verbose:
        print("-" * 60)
        print(f"Found {len(bad_indices)} bad batches (based on CSI data): {bad_indices}")
    
    return bad_indices


def clean_session_data(session_dir: Path, batch_indices_to_remove: List[int], 
                       backup: bool = True) -> SessionData:
    """Clean session data by removing bad batches and their associated files.
    
    This function will:
    1. Load the metadata.json file
    2. Remove data points at the specified indices
    3. Delete associated image files
    4. Delete associated CSI/router batch files
    5. Delete associated FTM batch files (if they exist)
    6. Renumber remaining data points
    7. Update metadata and save it
    8. Return a new SessionData object with cleaned data
    
    Args:
        session_dir: Path to session directory
        batch_indices_to_remove: List of batch indices to remove (0-based)
        backup: Whether to create a backup of metadata.json before modifying (default: True)
    
    Returns:
        SessionData object with cleaned data
    """
    session_dir = Path(session_dir)
    metadata_file = session_dir / 'metadata.json'
    
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
    
    # Load metadata
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Create backup if requested
    if backup:
        backup_file = session_dir / f'metadata_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(backup_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Created backup: {backup_file}")
    
    # Sort indices in descending order to avoid index shifting issues during removal
    indices_to_remove = sorted(set(batch_indices_to_remove), reverse=True)
    
    print(f"\nCleaning session: {metadata['session_id']}")
    print(f"Removing {len(indices_to_remove)} bad batches: {sorted(indices_to_remove)}")
    print("-" * 60)
    
    # Remove data points and associated files
    removed_count = 0
    for idx in indices_to_remove:
        if idx < 0 or idx >= len(metadata['data_points']):
            print(f"Warning: Index {idx} out of range, skipping")
            continue
        
        data_point = metadata['data_points'][idx]
        
        # Delete image file if it exists
        if 'image' in data_point:
            image_path = session_dir / data_point['image']
            if image_path.exists():
                os.remove(image_path)
                print(f"Deleted image: {image_path.name}")
            else:
                print(f"Image not found (already deleted?): {image_path.name}")
        
        # Delete CSI/router batch file if it exists (handle both old and new format)
        csi_batch_info = data_point.get('csi_batch') or data_point.get('router_batch')
        if csi_batch_info and 'file' in csi_batch_info:
            csi_file = session_dir / csi_batch_info['file']
            if csi_file.exists():
                os.remove(csi_file)
                print(f"Deleted CSI batch: {csi_file.name}")
            else:
                print(f"CSI batch not found (already deleted?): {csi_file.name}")
        
        # Delete FTM batch file if it exists (optional, won't error if missing)
        if 'ftm_batch' in data_point and 'file' in data_point['ftm_batch']:
            ftm_file = session_dir / data_point['ftm_batch']['file']
            if ftm_file.exists():
                os.remove(ftm_file)
                print(f"Deleted FTM batch: {ftm_file.name}")
            # Don't print warning if FTM file doesn't exist - it's optional
        
        # Remove from metadata
        del metadata['data_points'][idx]
        removed_count += 1
    
    # Renumber remaining data points
    for i, data_point in enumerate(metadata['data_points']):
        data_point['index'] = i
    
    # Update metadata counts
    metadata['total_samples'] = len(metadata['data_points'])
    
    # Update end time if we removed the last data point
    if metadata['data_points']:
        metadata['end_time'] = metadata['data_points'][-1]['timestamp']
    
    # Save updated metadata
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("-" * 60)
    print(f"Removed {removed_count} data points")
    print(f"Remaining data points: {metadata['total_samples']}")
    print(f"Updated metadata saved to: {metadata_file}")
    
    # Load and return the cleaned session
    return SessionData.from_directory(session_dir)


def auto_clean_session(session_dir: Path, backup: bool = True) -> SessionData:
    """Automatically detect and clean bad batches from a session.
    
    This is a convenience function that combines detect_bad_batches() and clean_session_data().
    
    Args:
        session_dir: Path to session directory
        backup: Whether to create a backup of metadata.json before modifying (default: True)
    
    Returns:
        SessionData object with cleaned data
    """
    # Detect bad batches
    print("\n" + "=" * 60)
    print("STEP 1: DETECTING BAD BATCHES")
    print("=" * 60)
    bad_indices = detect_bad_batches(session_dir, verbose=True)
    
    if not bad_indices:
        print("\nNo bad batches found! Session is clean.")
        return SessionData.from_directory(session_dir)
    
    # Clean the session
    print("\n" + "=" * 60)
    print("STEP 2: CLEANING SESSION")
    print("=" * 60)
    return clean_session_data(session_dir, bad_indices, backup=backup)


def load_all_sessions(data_dir: Path) -> Dict[str, SessionData]:
    """Load all sessions from a data directory.
    
    Args:
        data_dir: Path to directory containing session folders
    
    Returns:
        Dictionary mapping session_id to SessionData
    """
    data_dir = Path(data_dir)
    sessions = {}
    
    for session_dir in sorted(data_dir.iterdir()):
        if session_dir.is_dir() and session_dir.name.startswith('session_'):
            try:
                session = SessionData.from_directory(session_dir)
                sessions[session.session_id] = session
            except Exception as e:
                print(f"Warning: Failed to load session {session_dir.name}: {e}")
    
    return sessions

