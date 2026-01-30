"""AWS Config service integration for resource collection.

This module provides Config-first resource collection with fallback to direct API.
"""

from .collector import ConfigResourceCollector
from .detector import ConfigAvailability, detect_config_availability
from .resource_type_mapping import (
    CONFIG_SUPPORTED_TYPES,
    DIRECT_API_ONLY_TYPES,
    is_config_supported_type,
)

__all__ = [
    "ConfigAvailability",
    "detect_config_availability",
    "ConfigResourceCollector",
    "CONFIG_SUPPORTED_TYPES",
    "DIRECT_API_ONLY_TYPES",
    "is_config_supported_type",
]
