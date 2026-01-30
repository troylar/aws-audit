"""AWS DynamoDB to Terraform property mappings.

Maps AWS DynamoDB API response properties to Terraform resource properties
for DynamoDB tables.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# DynamoDB Table configurable properties
# Maps AWS API field names to Terraform aws_dynamodb_table argument names
DYNAMODB_TABLE_CONFIGURABLE: Dict[str, str] = {
    "TableName": "name",
    "AttributeDefinitions": "attribute",
    "KeySchema": "hash_key",  # Also includes range_key
    "BillingMode": "billing_mode",
    "ProvisionedThroughput": "read_capacity",  # Also includes write_capacity
    "GlobalSecondaryIndexes": "global_secondary_index",
    "LocalSecondaryIndexes": "local_secondary_index",
    "StreamSpecification": "stream_enabled",  # Also includes stream_view_type
    "Tags": "tags",
    "TTL": "ttl",
}

# DynamoDB Table computed/read-only properties
DYNAMODB_TABLE_COMPUTED: Dict[str, str] = {
    "TableArn": "arn",
    "TableStatus": "status",
    "CreationDateTime": "creation_date_time",
    "TableSizeBytes": "table_size_bytes",
    "ItemCount": "item_count",
    "TableId": "table_id",
    "LatestStreamArn": "latest_stream_arn",
    "LatestStreamLabel": "latest_stream_label",
    "RestoreSummary": "restore_summary",
}


def process_attribute_definitions(raw_attrs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Transform AWS attribute definitions to Terraform format.

    AWS format:
    [
        {"AttributeName": "id", "AttributeType": "S"},
        {"AttributeName": "sort_key", "AttributeType": "N"}
    ]

    Terraform format:
    [
        {"name": "id", "type": "S"},
        {"name": "sort_key", "type": "N"}
    ]

    Args:
        raw_attrs: List of attribute definitions from AWS

    Returns:
        List of transformed attribute definitions
    """
    if not raw_attrs:
        return []

    terraform_attrs = []
    for attr in raw_attrs:
        terraform_attrs.append(
            {
                "name": attr.get("AttributeName"),
                "type": attr.get("AttributeType"),
            }
        )

    return terraform_attrs


def process_key_schema(raw_schema: List[Dict[str, str]]) -> tuple[Optional[str], Optional[str]]:
    """Extract hash and range keys from key schema.

    AWS format:
    [
        {"AttributeName": "id", "KeyType": "HASH"},
        {"AttributeName": "sort_key", "KeyType": "RANGE"}
    ]

    Args:
        raw_schema: List of key schema items

    Returns:
        Tuple of (hash_key, range_key)
    """
    hash_key = None
    range_key = None

    if not raw_schema:
        return hash_key, range_key

    for item in raw_schema:
        if item.get("KeyType") == "HASH":
            hash_key = item.get("AttributeName")
        elif item.get("KeyType") == "RANGE":
            range_key = item.get("AttributeName")

    return hash_key, range_key


def process_provisioned_throughput(raw_throughput: Dict[str, int]) -> tuple[int, int]:
    """Extract read and write capacity from provisioned throughput.

    AWS format:
    {
        "ReadCapacityUnits": 5,
        "WriteCapacityUnits": 5
    }

    Args:
        raw_throughput: Provisioned throughput configuration

    Returns:
        Tuple of (read_capacity, write_capacity)
    """
    if not raw_throughput:
        return 0, 0

    return (
        raw_throughput.get("ReadCapacityUnits", 0),
        raw_throughput.get("WriteCapacityUnits", 0),
    )


def process_global_secondary_indexes(raw_gsis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS global secondary indexes to Terraform format.

    Args:
        raw_gsis: List of global secondary indexes from AWS

    Returns:
        List of transformed GSI configurations
    """
    if not raw_gsis:
        return []

    terraform_gsis = []
    for gsi in raw_gsis:
        tf_gsi = {
            "name": gsi.get("IndexName"),
            "hash_key": None,
            "range_key": None,
            "projection_type": gsi.get("Projection", {}).get("ProjectionType"),
        }

        # Extract hash and range keys
        if "KeySchema" in gsi:
            hash_key, range_key = process_key_schema(gsi["KeySchema"])
            tf_gsi["hash_key"] = hash_key
            tf_gsi["range_key"] = range_key

        # Add projected attributes if applicable
        if gsi.get("Projection", {}).get("NonKeyAttributes"):
            tf_gsi["non_key_attributes"] = gsi["Projection"]["NonKeyAttributes"]

        # Add provisioned throughput if present
        if "ProvisionedThroughput" in gsi:
            read_cap, write_cap = process_provisioned_throughput(gsi["ProvisionedThroughput"])
            tf_gsi["read_capacity"] = read_cap
            tf_gsi["write_capacity"] = write_cap

        terraform_gsis.append(tf_gsi)

    return terraform_gsis


def process_local_secondary_indexes(raw_lsis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS local secondary indexes to Terraform format.

    Args:
        raw_lsis: List of local secondary indexes from AWS

    Returns:
        List of transformed LSI configurations
    """
    if not raw_lsis:
        return []

    terraform_lsis = []
    for lsi in raw_lsis:
        tf_lsi = {
            "name": lsi.get("IndexName"),
            "range_key": None,
            "projection_type": lsi.get("Projection", {}).get("ProjectionType"),
        }

        # Extract range key (LSI shares hash key with main table)
        if "KeySchema" in lsi:
            _, range_key = process_key_schema(lsi["KeySchema"])
            tf_lsi["range_key"] = range_key

        # Add projected attributes if applicable
        if lsi.get("Projection", {}).get("NonKeyAttributes"):
            tf_lsi["non_key_attributes"] = lsi["Projection"]["NonKeyAttributes"]

        terraform_lsis.append(tf_lsi)

    return terraform_lsis


def process_stream_specification(raw_stream: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Extract stream configuration from stream specification.

    AWS format:
    {
        "StreamEnabled": true,
        "StreamViewType": "NEW_AND_OLD_IMAGES"
    }

    Args:
        raw_stream: Stream specification

    Returns:
        Tuple of (stream_enabled, stream_view_type)
    """
    if not raw_stream:
        return False, None

    return (
        raw_stream.get("StreamEnabled", False),
        raw_stream.get("StreamViewType"),
    )


def process_ttl(raw_ttl: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract TTL configuration.

    AWS format:
    {
        "AttributeName": "expiration",
        "Enabled": true
    }

    Args:
        raw_ttl: TTL configuration

    Returns:
        TTL configuration for Terraform or None if not enabled
    """
    if not raw_ttl:
        return None

    if not raw_ttl.get("Enabled"):
        return None

    return {
        "attribute_name": raw_ttl.get("AttributeName"),
    }


def get_dynamodb_table_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract DynamoDB table properties from raw AWS config.

    Args:
        raw_config: Raw AWS DynamoDB table configuration from describe_table

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    properties = {}

    # Extract table name
    if "TableName" in raw_config:
        properties["name"] = raw_config["TableName"]

    # Process attribute definitions
    if "AttributeDefinitions" in raw_config:
        properties["attribute"] = process_attribute_definitions(raw_config["AttributeDefinitions"])

    # Process key schema
    if "KeySchema" in raw_config:
        hash_key, range_key = process_key_schema(raw_config["KeySchema"])
        if hash_key:
            properties["hash_key"] = hash_key
        if range_key:
            properties["range_key"] = range_key

    # Extract billing mode
    if "BillingModeSummary" in raw_config:
        properties["billing_mode"] = raw_config["BillingModeSummary"].get("BillingMode")

    # Process provisioned throughput
    if "ProvisionedThroughput" in raw_config and properties.get("billing_mode") == "PROVISIONED":
        read_cap, write_cap = process_provisioned_throughput(raw_config["ProvisionedThroughput"])
        properties["read_capacity"] = read_cap
        properties["write_capacity"] = write_cap

    # Process global secondary indexes
    if "GlobalSecondaryIndexes" in raw_config:
        gsis = process_global_secondary_indexes(raw_config["GlobalSecondaryIndexes"])
        if gsis:
            properties["global_secondary_index"] = gsis

    # Process local secondary indexes
    if "LocalSecondaryIndexes" in raw_config:
        lsis = process_local_secondary_indexes(raw_config["LocalSecondaryIndexes"])
        if lsis:
            properties["local_secondary_index"] = lsis

    # Process stream specification
    if "StreamSpecification" in raw_config:
        stream_enabled, stream_view_type = process_stream_specification(raw_config["StreamSpecification"])
        properties["stream_enabled"] = stream_enabled
        if stream_view_type:
            properties["stream_view_type"] = stream_view_type

    # Process tags
    if "Tags" in raw_config:
        tags_dict = {}
        for tag in raw_config["Tags"]:
            tags_dict[tag.get("Key")] = tag.get("Value")
        if tags_dict:
            properties["tags"] = tags_dict

    # Process TTL
    if "TimeToLiveDescription" in raw_config:
        ttl_config = process_ttl(raw_config["TimeToLiveDescription"])
        if ttl_config:
            properties["ttl"] = ttl_config

    return properties


def get_dynamodb_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed/read-only DynamoDB properties from raw AWS config.

    Args:
        raw_config: Raw AWS DynamoDB table configuration

    Returns:
        Dictionary of read-only properties
    """
    computed = {}

    for aws_field, tf_field in DYNAMODB_TABLE_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                computed[tf_field] = value

    return computed


# Register this property map for DynamoDB resources
from . import register_property_map

register_property_map(
    "dynamodb",
    {
        "table": {
            "configurable": DYNAMODB_TABLE_CONFIGURABLE,
            "computed": DYNAMODB_TABLE_COMPUTED,
            "get_properties": get_dynamodb_table_properties,
            "get_computed": get_dynamodb_computed_properties,
        },
    },
)

__all__ = [
    "DYNAMODB_TABLE_CONFIGURABLE",
    "DYNAMODB_TABLE_COMPUTED",
    "get_dynamodb_table_properties",
    "get_dynamodb_computed_properties",
    "process_attribute_definitions",
    "process_key_schema",
    "process_provisioned_throughput",
    "process_global_secondary_indexes",
    "process_local_secondary_indexes",
    "process_stream_specification",
    "process_ttl",
]
