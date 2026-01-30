"""AWS Config availability detection.

Detects if AWS Config is enabled in a region and what resource types it supports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    import boto3

from ..aws.client import create_boto_client

logger = logging.getLogger(__name__)


@dataclass
class ConfigAvailability:
    """AWS Config availability status for a region.

    Attributes:
        region: AWS region
        is_enabled: Whether Config is enabled and recording
        recorder_name: Name of the configuration recorder (if enabled)
        recording_group_all_supported: Whether recorder captures all supported types
        resource_types_recorded: Specific resource types being recorded
        delivery_channel_configured: Whether a delivery channel is set up
        error_message: Error message if detection failed
    """

    region: str
    is_enabled: bool = False
    recorder_name: Optional[str] = None
    recording_group_all_supported: bool = False
    resource_types_recorded: Set[str] = field(default_factory=set)
    delivery_channel_configured: bool = False
    error_message: Optional[str] = None

    def supports_resource_type(self, resource_type: str) -> bool:
        """Check if this region's Config supports a specific resource type.

        Args:
            resource_type: AWS resource type (e.g., "AWS::EC2::Instance")

        Returns:
            True if Config can collect this resource type in this region
        """
        if not self.is_enabled:
            return False

        # If recording all supported types, check against the global list
        if self.recording_group_all_supported:
            from .resource_type_mapping import is_config_supported_type

            return is_config_supported_type(resource_type)

        # Otherwise, check specific recorded types
        return resource_type in self.resource_types_recorded


def detect_config_availability(
    session: "boto3.Session",
    region: str,
    profile_name: Optional[str] = None,
) -> ConfigAvailability:
    """Detect AWS Config availability in a region.

    Checks if AWS Config is enabled, has a recorder configured,
    and what resource types it's recording.

    Args:
        session: Boto3 session
        region: AWS region to check
        profile_name: Optional AWS profile name

    Returns:
        ConfigAvailability with detection results
    """
    availability = ConfigAvailability(region=region)

    try:
        # Create Config client
        profile = profile_name or (session.profile_name if hasattr(session, "profile_name") else None)
        client = create_boto_client(
            service_name="config",
            region_name=region,
            profile_name=profile,
        )

        # Check configuration recorders
        recorders_response = client.describe_configuration_recorders()
        recorders = recorders_response.get("ConfigurationRecorders", [])

        if not recorders:
            availability.error_message = "No configuration recorders found"
            logger.debug(f"Config not enabled in {region}: no recorders")
            return availability

        # Get the first (usually only) recorder
        recorder = recorders[0]
        availability.recorder_name = recorder.get("name")

        # Check recording group settings
        recording_group = recorder.get("recordingGroup", {})
        availability.recording_group_all_supported = recording_group.get("allSupported", False)

        # Get specific resource types if not recording all
        if not availability.recording_group_all_supported:
            resource_types = recording_group.get("resourceTypes", [])
            availability.resource_types_recorded = set(resource_types)

        # Check recorder status
        status_response = client.describe_configuration_recorder_status()
        statuses = status_response.get("ConfigurationRecordersStatus", [])

        recorder_is_recording = False
        for status in statuses:
            if status.get("name") == availability.recorder_name:
                recorder_is_recording = status.get("recording", False)
                break

        if not recorder_is_recording:
            availability.error_message = "Configuration recorder is not recording"
            logger.debug(f"Config recorder in {region} is not recording")
            return availability

        # Check delivery channel
        try:
            channels_response = client.describe_delivery_channels()
            channels = channels_response.get("DeliveryChannels", [])
            availability.delivery_channel_configured = len(channels) > 0
        except Exception as e:
            logger.debug(f"Could not check delivery channels in {region}: {e}")
            # Not a critical failure, continue

        # All checks passed
        availability.is_enabled = True
        logger.debug(
            f"Config enabled in {region}: recorder={availability.recorder_name}, "
            f"all_supported={availability.recording_group_all_supported}"
        )

    except client.exceptions.NoSuchConfigurationRecorderException:
        availability.error_message = "No configuration recorder exists"
        logger.debug(f"Config not enabled in {region}: no recorder exists")

    except Exception as e:
        availability.error_message = str(e)
        logger.debug(f"Error detecting Config in {region}: {e}")

    return availability


def detect_config_availability_multi_region(
    session: "boto3.Session",
    regions: List[str],
    profile_name: Optional[str] = None,
) -> dict[str, ConfigAvailability]:
    """Detect AWS Config availability across multiple regions.

    Args:
        session: Boto3 session
        regions: List of AWS regions to check
        profile_name: Optional AWS profile name

    Returns:
        Dict mapping region to ConfigAvailability
    """
    results = {}
    for region in regions:
        results[region] = detect_config_availability(session, region, profile_name)
    return results


def get_config_supported_resource_types(
    session: "boto3.Session",
    region: str,
    profile_name: Optional[str] = None,
) -> Set[str]:
    """Get the set of resource types that AWS Config can collect in a region.

    This queries what the Config recorder is actually recording, not just
    what's theoretically supported.

    Args:
        session: Boto3 session
        region: AWS region
        profile_name: Optional AWS profile name

    Returns:
        Set of resource type strings (e.g., {"AWS::EC2::Instance", "AWS::S3::Bucket"})
    """
    availability = detect_config_availability(session, region, profile_name)

    if not availability.is_enabled:
        return set()

    if availability.recording_group_all_supported:
        # Return all Config-supported types
        from .resource_type_mapping import CONFIG_SUPPORTED_TYPES

        return CONFIG_SUPPORTED_TYPES.copy()

    return availability.resource_types_recorded


def check_aggregator_availability(
    session: "boto3.Session",
    aggregator_name: str,
    region: str = "us-east-1",
    profile_name: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Check if a Config aggregator is available and accessible.

    Args:
        session: Boto3 session
        aggregator_name: Name of the Config aggregator
        region: Region where aggregator is configured
        profile_name: Optional AWS profile name

    Returns:
        Tuple of (is_available, error_message)
    """
    try:
        profile = profile_name or (session.profile_name if hasattr(session, "profile_name") else None)
        client = create_boto_client(
            service_name="config",
            region_name=region,
            profile_name=profile,
        )

        response = client.describe_configuration_aggregators(ConfigurationAggregatorNames=[aggregator_name])

        aggregators = response.get("ConfigurationAggregators", [])
        if aggregators:
            logger.debug(f"Config aggregator '{aggregator_name}' is available")
            return True, None

        return False, f"Aggregator '{aggregator_name}' not found"

    except client.exceptions.NoSuchConfigurationAggregatorException:
        return False, f"Aggregator '{aggregator_name}' does not exist"

    except Exception as e:
        return False, str(e)
