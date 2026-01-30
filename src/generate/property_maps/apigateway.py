"""AWS API Gateway to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# REST API configurable properties that map to aws_api_gateway_rest_api
REST_API_CONFIGURABLE = {
    "Name": "name",
    "Description": "description",
    "EndpointConfiguration": "endpoint_configuration",
    "Policy": "policy",
    "Tags": "tags",
}

# REST API computed/read-only properties
REST_API_COMPUTED = {
    "Id": "id",
    "Arn": "arn",
    "CreatedDate": "created_date",
}

# HTTP API (v2) configurable properties that map to aws_apigatewayv2_api
HTTP_API_CONFIGURABLE = {
    "Name": "name",
    "ProtocolType": "protocol_type",
    "Description": "description",
    "CorsConfiguration": "cors_configuration",
    "Tags": "tags",
}

# HTTP API (v2) computed/read-only properties
HTTP_API_COMPUTED = {
    "ApiId": "id",
    "ApiArn": "arn",
    "CreatedDate": "created_date",
    "ApiEndpoint": "api_endpoint",
}


def _transform_endpoint_configuration(
    endpoint_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Transform endpoint configuration to Terraform format.

    Args:
        endpoint_config: AWS endpoint configuration dict with Types key

    Returns:
        Terraform-formatted endpoint configuration or None if empty
    """
    if not endpoint_config:
        return None

    result = {}

    if "Types" in endpoint_config:
        result["types"] = endpoint_config["Types"]

    if "VpcEndpointIds" in endpoint_config:
        result["vpc_endpoint_ids"] = endpoint_config["VpcEndpointIds"]

    return result if result else None


def _transform_cors_configuration(
    cors_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Transform CORS configuration to Terraform format.

    Args:
        cors_config: AWS CORS configuration dict

    Returns:
        Terraform-formatted CORS configuration or None if empty
    """
    if not cors_config:
        return None

    result = {}

    if "AllowCredentials" in cors_config:
        result["allow_credentials"] = cors_config["AllowCredentials"]

    if "AllowHeaders" in cors_config:
        result["allow_headers"] = cors_config["AllowHeaders"]

    if "AllowMethods" in cors_config:
        result["allow_methods"] = cors_config["AllowMethods"]

    if "AllowOrigins" in cors_config:
        result["allow_origins"] = cors_config["AllowOrigins"]

    if "ExposeHeaders" in cors_config:
        result["expose_headers"] = cors_config["ExposeHeaders"]

    if "MaxAge" in cors_config:
        result["max_age"] = cors_config["MaxAge"]

    return result if result else None


def get_rest_api_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform REST API properties for Terraform.

    This helper transforms AWS API Gateway REST API configuration into
    Terraform-compatible format, handling special cases for nested structures.

    Args:
        raw_config: Raw REST API configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_api_gateway_rest_api resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in REST_API_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "EndpointConfiguration":
            transformed = _transform_endpoint_configuration(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in REST_API_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


def get_http_api_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform HTTP API (v2) properties for Terraform.

    This helper transforms AWS API Gateway HTTP API configuration into
    Terraform-compatible format, handling special cases for nested structures.

    Args:
        raw_config: Raw HTTP API configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_apigatewayv2_api resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in HTTP_API_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "CorsConfiguration":
            transformed = _transform_cors_configuration(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in HTTP_API_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property maps for API Gateway resources
register_property_map("apigateway:rest_api", __name__)
register_property_map("apigateway:http_api", __name__)
register_property_map("apigateway", __name__)
