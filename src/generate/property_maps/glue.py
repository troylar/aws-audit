"""AWS Glue to Terraform property mappings.

Maps AWS Glue API response properties to Terraform resource properties
for Glue Databases and Glue Tables.
"""

from typing import Any, Dict, List

# Glue Database configurable properties
# Maps AWS API field names to Terraform aws_glue_catalog_database argument names
GLUE_DATABASE_CONFIGURABLE: Dict[str, Dict[str, Any]] = {
    "name": {
        "aws_key": "Name",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "name",
        "type": "string",
        "required": True,
        "description": "Name of the Glue database",
    },
    "catalog_id": {
        "aws_key": "CatalogId",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "catalog_id",
        "type": "string",
        "required": False,
        "description": "AWS Account ID of the database catalog (computed from owner)",
    },
    "description": {
        "aws_key": "Description",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "description",
        "type": "string",
        "required": False,
        "description": "Description of the database",
    },
    "location_uri": {
        "aws_key": "LocationUri",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "location_uri",
        "type": "string",
        "required": False,
        "description": "Location of the database (S3 path or other URI)",
    },
    "parameters": {
        "aws_key": "Parameters",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "parameters",
        "type": "map(string)",
        "required": False,
        "description": "Map of custom database parameters",
    },
}

# Glue Database computed/read-only properties
GLUE_DATABASE_COMPUTED: Dict[str, Dict[str, Any]] = {
    "arn": {
        "aws_key": "Arn",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the Glue database",
    },
    "create_time": {
        "aws_key": "CreateTime",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "create_time",
        "type": "string",
        "computed": True,
        "description": "Date and time when the database was created",
    },
    "update_time": {
        "aws_key": "UpdateTime",
        "tf_resource": "aws_glue_catalog_database",
        "tf_attribute": "update_time",
        "type": "string",
        "computed": True,
        "description": "Date and time when the database was last updated",
    },
}

# Glue Table configurable properties
GLUE_TABLE_CONFIGURABLE: Dict[str, Dict[str, Any]] = {
    "name": {
        "aws_key": "Name",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "name",
        "type": "string",
        "required": True,
        "description": "Name of the Glue table",
    },
    "database_name": {
        "aws_key": "DatabaseName",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "database_name",
        "type": "string",
        "required": True,
        "description": "Name of the database containing the table",
    },
    "table_type": {
        "aws_key": "TableType",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "table_type",
        "type": "string",
        "required": False,
        "description": "Type of the table (EXTERNAL_TABLE, ICEBERG, etc.)",
    },
    "storage_descriptor": {
        "aws_key": "StorageDescriptor",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "storage_descriptor",
        "type": "object",
        "required": False,
        "description": "Storage descriptor with location, format, columns, etc.",
    },
    "partition_keys": {
        "aws_key": "PartitionKeys",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "partition_keys",
        "type": "list(object)",
        "required": False,
        "description": "List of partition keys (Name, Type, Comment)",
    },
    "parameters": {
        "aws_key": "Parameters",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "parameters",
        "type": "map(string)",
        "required": False,
        "description": "Map of custom table parameters",
    },
}

# Glue Table computed/read-only properties
GLUE_TABLE_COMPUTED: Dict[str, Dict[str, Any]] = {
    "arn": {
        "aws_key": "Arn",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the Glue table",
    },
    "create_time": {
        "aws_key": "CreateTime",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "create_time",
        "type": "string",
        "computed": True,
        "description": "Date and time when the table was created",
    },
    "update_time": {
        "aws_key": "UpdateTime",
        "tf_resource": "aws_glue_catalog_table",
        "tf_attribute": "update_time",
        "type": "string",
        "computed": True,
        "description": "Date and time when the table was last updated",
    },
}


def get_glue_database_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Glue Database properties from raw AWS config.

    Extracts database properties including name, description, location, and parameters.

    Args:
        raw_config: Raw Glue Database configuration from AWS API

    Returns:
        Dictionary of Terraform aws_glue_catalog_database properties
    """
    properties = {}

    # Extract database name
    if "Name" in raw_config:
        properties["name"] = raw_config["Name"]

    # Extract catalog ID if present
    if "CatalogId" in raw_config:
        properties["catalog_id"] = raw_config["CatalogId"]

    # Extract description if present
    if "Description" in raw_config:
        properties["description"] = raw_config["Description"]

    # Extract location URI if present
    if "LocationUri" in raw_config:
        properties["location_uri"] = raw_config["LocationUri"]

    # Extract parameters if present
    if "Parameters" in raw_config:
        properties["parameters"] = raw_config["Parameters"]

    return properties


def get_glue_database_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed properties from Glue Database config.

    Args:
        raw_config: Raw Glue Database configuration from AWS API

    Returns:
        Dictionary of computed properties
    """
    computed = {}

    if "Arn" in raw_config:
        computed["arn"] = raw_config["Arn"]

    if "CreateTime" in raw_config:
        computed["create_time"] = str(raw_config["CreateTime"])

    if "UpdateTime" in raw_config:
        computed["update_time"] = str(raw_config["UpdateTime"])

    return computed


def process_storage_descriptor(
    storage_descriptor: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a Glue storage descriptor into Terraform format.

    Extracts location, input/output formats, serialization library,
    columns, and other storage-related properties.

    Args:
        storage_descriptor: Raw storage descriptor from AWS API

    Returns:
        Processed storage descriptor for Terraform
    """
    tf_descriptor = {}

    if "Location" in storage_descriptor:
        tf_descriptor["location"] = storage_descriptor["Location"]

    if "InputFormat" in storage_descriptor:
        tf_descriptor["input_format"] = storage_descriptor["InputFormat"]

    if "OutputFormat" in storage_descriptor:
        tf_descriptor["output_format"] = storage_descriptor["OutputFormat"]

    if "SerdeInfo" in storage_descriptor:
        serde_info = storage_descriptor["SerdeInfo"]
        tf_serde = {}

        if "SerializationLibrary" in serde_info:
            tf_serde["serialization_library"] = serde_info["SerializationLibrary"]

        if "Parameters" in serde_info:
            tf_serde["parameters"] = serde_info["Parameters"]

        if tf_serde:
            tf_descriptor["serde_info"] = tf_serde

    # Process columns
    if "Columns" in storage_descriptor:
        columns = storage_descriptor["Columns"]
        tf_columns = []

        for column in columns:
            tf_column = {}

            if "Name" in column:
                tf_column["name"] = column["Name"]

            if "Type" in column:
                tf_column["type"] = column["Type"]

            if "Comment" in column:
                tf_column["comment"] = column["Comment"]

            if tf_column:
                tf_columns.append(tf_column)

        if tf_columns:
            tf_descriptor["columns"] = tf_columns

    if "BucketColumns" in storage_descriptor:
        tf_descriptor["bucket_columns"] = storage_descriptor["BucketColumns"]

    if "SortColumns" in storage_descriptor:
        sort_cols = storage_descriptor["SortColumns"]
        tf_sort_cols = []

        for sort_col in sort_cols:
            tf_sort = {}
            if "Name" in sort_col:
                tf_sort["name"] = sort_col["Name"]
            if "SortOrder" in sort_col:
                tf_sort["sort_order"] = sort_col["SortOrder"]
            if tf_sort:
                tf_sort_cols.append(tf_sort)

        if tf_sort_cols:
            tf_descriptor["sort_columns"] = tf_sort_cols

    if "Parameters" in storage_descriptor:
        tf_descriptor["parameters"] = storage_descriptor["Parameters"]

    if "SkewedInfo" in storage_descriptor:
        skewed_info = storage_descriptor["SkewedInfo"]
        tf_skewed = {}

        if "SkewedColumnNames" in skewed_info:
            tf_skewed["skewed_column_names"] = skewed_info["SkewedColumnNames"]

        if "SkewedColumnValues" in skewed_info:
            tf_skewed["skewed_column_values"] = skewed_info["SkewedColumnValues"]

        if "SkewedColumnValueLocationMaps" in skewed_info:
            tf_skewed["skewed_column_value_location_maps"] = skewed_info["SkewedColumnValueLocationMaps"]

        if tf_skewed:
            tf_descriptor["skewed_info"] = tf_skewed

    if "StoredAsSubDirectories" in storage_descriptor:
        tf_descriptor["stored_as_sub_directories"] = storage_descriptor["StoredAsSubDirectories"]

    return tf_descriptor


def process_partition_keys(partition_keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process Glue partition keys into Terraform format.

    Args:
        partition_keys: List of partition key definitions from AWS API

    Returns:
        List of processed partition keys for Terraform
    """
    tf_keys = []

    for key in partition_keys:
        tf_key = {}

        if "Name" in key:
            tf_key["name"] = key["Name"]

        if "Type" in key:
            tf_key["type"] = key["Type"]

        if "Comment" in key:
            tf_key["comment"] = key["Comment"]

        if tf_key:
            tf_keys.append(tf_key)

    return tf_keys


def get_glue_table_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Glue Table properties from raw AWS config.

    Extracts table properties including name, database, type, storage descriptor,
    partition keys, and parameters.

    Args:
        raw_config: Raw Glue Table configuration from AWS API

    Returns:
        Dictionary of Terraform aws_glue_catalog_table properties
    """
    properties = {}

    # Extract table name
    if "Name" in raw_config:
        properties["name"] = raw_config["Name"]

    # Extract database name
    if "DatabaseName" in raw_config:
        properties["database_name"] = raw_config["DatabaseName"]

    # Extract table type if present
    if "TableType" in raw_config:
        properties["table_type"] = raw_config["TableType"]

    # Extract storage descriptor if present
    if "StorageDescriptor" in raw_config:
        descriptor = process_storage_descriptor(raw_config["StorageDescriptor"])
        if descriptor:
            properties["storage_descriptor"] = descriptor

    # Extract partition keys if present
    if "PartitionKeys" in raw_config:
        partition_keys = raw_config["PartitionKeys"]
        if partition_keys:
            properties["partition_keys"] = process_partition_keys(partition_keys)

    # Extract parameters if present
    if "Parameters" in raw_config:
        properties["parameters"] = raw_config["Parameters"]

    return properties


def get_glue_table_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed properties from Glue Table config.

    Args:
        raw_config: Raw Glue Table configuration from AWS API

    Returns:
        Dictionary of computed properties
    """
    computed = {}

    if "Arn" in raw_config:
        computed["arn"] = raw_config["Arn"]

    if "CreateTime" in raw_config:
        computed["create_time"] = str(raw_config["CreateTime"])

    if "UpdateTime" in raw_config:
        computed["update_time"] = str(raw_config["UpdateTime"])

    return computed
