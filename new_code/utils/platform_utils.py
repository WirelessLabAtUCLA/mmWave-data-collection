"""Cross-platform utilities for device detection"""
import platform
import glob
from pathlib import Path
from typing import List, Optional


def get_platform() -> str:
    """Get platform name: 'linux' or 'macos'"""
    system = platform.system()
    if system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "macos"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def find_gps_devices() -> List[str]:
    """Find all potential GPS serial devices"""
    plat = get_platform()
    
    if plat == "linux":
        devices = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    else:  # macos
        devices = glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*")
    
    return sorted(devices)


def find_gps_device(config_device: str = "auto") -> Optional[str]:
    """Find GPS device, returns first available or configured device"""
    if config_device != "auto" and Path(config_device).exists():
        return config_device
    
    devices = find_gps_devices()
    return devices[0] if devices else None


def find_camera_devices() -> List[int]:
    """Find available camera device IDs"""
    import cv2
    
    available = []
    for i in range(5):  # Try first 5 IDs
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    
    return available


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path"""
    return Path(path).expanduser()

