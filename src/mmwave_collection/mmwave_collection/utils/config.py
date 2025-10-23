"""Configuration loader"""
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config/default_config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_nested(config: Dict, *keys, default=None):
    """Safely get nested config value"""
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value

