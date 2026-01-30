"""AWS Route53 to Terraform property mappings.

Maps AWS Route53 API response properties to Terraform resource properties
for hosted zones and record sets.
"""

from typing import Any, Dict, Optional

# Route53 Hosted Zone configurable properties
# Maps AWS API field names to Terraform aws_route53_zone argument names
HOSTED_ZONE_CONFIGURABLE: Dict[str, str] = {
    "Name": "name",
    "Comment": "comment",
    "PrivateZone": "private_zone",  # Complex nested block
    "VPC": "vpc",  # Complex nested block for private zones
    "HostedZoneTags": "tags",
    "CallerReference": "caller_reference",
    "DelegationSetId": "delegation_set_id",
}

# Route53 Hosted Zone computed/read-only properties
HOSTED_ZONE_COMPUTED: set = {
    "HostedZoneId",
    "Id",
    "ResourceRecordSetCount",
    "NameServers",
    "VPCs",
    "LinkedServiceDescription",
    "LinkedServicePrincipal",
    "Config",
}

# Route53 Record Set configurable properties
# Maps AWS API field names to Terraform aws_route53_record argument names
RECORD_SET_CONFIGURABLE: Dict[str, str] = {
    "Name": "name",
    "Type": "type",
    "TTL": "ttl",
    "ResourceRecords": "records",
    "AliasTarget": "alias",  # Complex nested block
    "SetIdentifier": "set_identifier",
    "Weight": "weighted_routing_policy",  # Complex nested block
    "Region": "latency_routing_policy",  # Complex nested block
    "GeolocationContinent": "geolocation_routing_policy",  # Complex nested block
    "FailoverRoutingPolicy": "failover_routing_policy",  # Complex nested block
    "MultiValueAnswer": "multivalue_answer_routing_policy",
    "GeoProximityLocation": "geoproximity_routing_policy",  # Complex nested block
}

# Route53 Record Set computed/read-only properties
RECORD_SET_COMPUTED: set = {
    "ResourceRecordSetArn",
    "TrafficPolicyInstanceId",
    "TrafficPolicyVersionNumber",
}


def _extract_private_zone_config(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract private zone configuration into Terraform block format.

    Args:
        raw_config: Raw hosted zone configuration from AWS API

    Returns:
        Dictionary with private_zone block properties, or None if not a private zone
    """
    # Check if this is a private zone (presence of VPCs indicates private zone)
    vpcs = raw_config.get("VPCs", [])
    private_zone_config = raw_config.get("Config", {})

    if not vpcs and not private_zone_config:
        return None

    config = {}

    # Handle PrivateZone field if present
    if "PrivateZone" in raw_config:
        config["private_zone"] = raw_config["PrivateZone"]

    # Handle VPCs for private zones
    if vpcs:
        vpc_list = []
        for vpc in vpcs:
            if isinstance(vpc, dict):
                vpc_entry = {}
                if "VPCRegion" in vpc:
                    vpc_entry["vpc_region"] = vpc["VPCRegion"]
                if "VPCId" in vpc:
                    vpc_entry["vpc_id"] = vpc["VPCId"]
                if vpc_entry:
                    vpc_list.append(vpc_entry)
        if vpc_list:
            config["vpc"] = vpc_list

    # Handle Config.PrivateZone
    if private_zone_config.get("PrivateZone"):
        config["private_zone"] = private_zone_config["PrivateZone"]

    return config if config else None


def _extract_alias_target_block(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract alias target configuration into Terraform block format.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with alias block properties, or None if not an alias record
    """
    alias_target = raw_config.get("AliasTarget")

    if not alias_target or not isinstance(alias_target, dict):
        return None

    alias_block = {}

    if "Name" in alias_target:
        alias_block["name"] = alias_target["Name"]

    if "HostedZoneId" in alias_target:
        alias_block["zone_id"] = alias_target["HostedZoneId"]

    if "EvaluateTargetHealth" in alias_target:
        alias_block["evaluate_target_health"] = alias_target["EvaluateTargetHealth"]

    return alias_block if alias_block else None


def _extract_weighted_routing_policy(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract weighted routing policy configuration.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with weighted routing policy properties, or None
    """
    if "Weight" not in raw_config:
        return None

    weight = raw_config.get("Weight")
    if weight is None:
        return None

    return {
        "weight": weight,
        "set_identifier": raw_config.get("SetIdentifier"),
    }


def _extract_latency_routing_policy(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract latency-based routing policy configuration.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with latency routing policy properties, or None
    """
    if "Region" not in raw_config:
        return None

    region = raw_config.get("Region")
    if region is None:
        return None

    return {
        "region": region,
        "set_identifier": raw_config.get("SetIdentifier"),
    }


def _extract_geolocation_routing_policy(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract geolocation-based routing policy configuration.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with geolocation routing policy properties, or None
    """
    geo_config = raw_config.get("GeoLocation")

    if not geo_config or not isinstance(geo_config, dict):
        return None

    geolocation_policy = {}

    if "CountryCode" in geo_config:
        geolocation_policy["country_code"] = geo_config["CountryCode"]

    if "ContinentCode" in geo_config:
        geolocation_policy["continent_code"] = geo_config["ContinentCode"]

    if "SubdivisionCode" in geo_config:
        geolocation_policy["subdivision_code"] = geo_config["SubdivisionCode"]

    # Set identifier required for geolocation routing
    if "SetIdentifier" in raw_config:
        geolocation_policy["set_identifier"] = raw_config["SetIdentifier"]

    return geolocation_policy if geolocation_policy else None


def _extract_geoproximity_routing_policy(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract geoproximity-based routing policy configuration.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with geoproximity routing policy properties, or None
    """
    geo_prox = raw_config.get("GeoProximityLocation")

    if not geo_prox or not isinstance(geo_prox, dict):
        return None

    geoproximity_policy = {}

    if "Latitude" in geo_prox:
        geoproximity_policy["latitude"] = geo_prox["Latitude"]

    if "Longitude" in geo_prox:
        geoproximity_policy["longitude"] = geo_prox["Longitude"]

    if "Bias" in geo_prox:
        geoproximity_policy["bias"] = geo_prox["Bias"]

    # Set identifier and region for geoproximity routing
    if "SetIdentifier" in raw_config:
        geoproximity_policy["set_identifier"] = raw_config["SetIdentifier"]

    if "Region" in raw_config:
        geoproximity_policy["region"] = raw_config["Region"]

    return geoproximity_policy if geoproximity_policy else None


def get_hosted_zone_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract hosted zone properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles nested block conversions.

    Args:
        raw_config: Raw hosted zone configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in HOSTED_ZONE_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in HOSTED_ZONE_COMPUTED:
            value = raw_config[aws_key]
            if value is not None and tf_key not in ["private_zone", "vpc"]:
                terraform_config[tf_key] = value

    # Extract private_zone and vpc as nested blocks
    zone_config = _extract_private_zone_config(raw_config)
    if zone_config:
        if "private_zone" in zone_config:
            terraform_config["private_zone"] = zone_config["private_zone"]
        if "vpc" in zone_config:
            terraform_config["vpc"] = zone_config["vpc"]

    return terraform_config


def get_record_set_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract record set properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles nested block conversions for various routing policies.

    Args:
        raw_config: Raw record set configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in RECORD_SET_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in RECORD_SET_COMPUTED:
            value = raw_config[aws_key]
            if value is not None and tf_key not in [
                "alias",
                "weighted_routing_policy",
                "latency_routing_policy",
                "geolocation_routing_policy",
                "failover_routing_policy",
                "geoproximity_routing_policy",
            ]:
                terraform_config[tf_key] = value

    # Extract alias as a nested block
    alias_target = _extract_alias_target_block(raw_config)
    if alias_target:
        terraform_config["alias"] = alias_target

    # Extract weighted routing policy
    weighted_policy = _extract_weighted_routing_policy(raw_config)
    if weighted_policy:
        terraform_config["weighted_routing_policy"] = weighted_policy

    # Extract latency routing policy
    latency_policy = _extract_latency_routing_policy(raw_config)
    if latency_policy:
        terraform_config["latency_routing_policy"] = latency_policy

    # Extract geolocation routing policy
    geolocation_policy = _extract_geolocation_routing_policy(raw_config)
    if geolocation_policy:
        terraform_config["geolocation_routing_policy"] = geolocation_policy

    # Extract geoproximity routing policy
    geoproximity_policy = _extract_geoproximity_routing_policy(raw_config)
    if geoproximity_policy:
        terraform_config["geoproximity_routing_policy"] = geoproximity_policy

    # Extract multivalue answer routing
    if "MultiValueAnswer" in raw_config:
        terraform_config["multivalue_answer_routing_policy"] = {"enabled": raw_config["MultiValueAnswer"]}

    # Extract failover routing policy
    if "FailoverRoutingPolicy" in raw_config:
        failover = raw_config["FailoverRoutingPolicy"]
        if isinstance(failover, dict) and "Type" in failover:
            terraform_config["failover_routing_policy"] = {
                "type": failover["Type"],
                "set_identifier": raw_config.get("SetIdentifier"),
            }

    return terraform_config


def _register_maps() -> None:
    """Register Route53 property maps with the registry."""
    try:
        from . import register_property_map

        register_property_map(
            "route53:hosted_zone",
            {
                "configurable": HOSTED_ZONE_CONFIGURABLE,
                "computed": HOSTED_ZONE_COMPUTED,
                "get_properties": get_hosted_zone_properties,
            },
        )
        register_property_map(
            "route53:record_set",
            {
                "configurable": RECORD_SET_CONFIGURABLE,
                "computed": RECORD_SET_COMPUTED,
                "get_properties": get_record_set_properties,
            },
        )
        register_property_map(
            "aws:route53_zone",
            {
                "configurable": HOSTED_ZONE_CONFIGURABLE,
                "computed": HOSTED_ZONE_COMPUTED,
                "get_properties": get_hosted_zone_properties,
            },
        )
        register_property_map(
            "aws:route53_record",
            {
                "configurable": RECORD_SET_CONFIGURABLE,
                "computed": RECORD_SET_COMPUTED,
                "get_properties": get_record_set_properties,
            },
        )
    except ImportError:
        # Registry not available yet, will be registered on import
        pass


# Auto-register on module import
_register_maps()

__all__ = [
    "HOSTED_ZONE_CONFIGURABLE",
    "HOSTED_ZONE_COMPUTED",
    "RECORD_SET_CONFIGURABLE",
    "RECORD_SET_COMPUTED",
    "get_hosted_zone_properties",
    "get_record_set_properties",
]
