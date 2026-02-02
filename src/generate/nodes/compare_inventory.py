"""Compare inventory node for LangGraph workflow.

Compares original inventory resources against generated Terraform code
using AWS Bedrock to identify coverage, gaps, and issues.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import boto3

from ...models.generation import TrackedResource
from ..state import GenerationConfig, GenerationState


def compare_inventory(state: GenerationState) -> Dict[str, Any]:
    """Compare original inventory against generated Terraform code using AI.

    Calls AWS Bedrock to semantically analyze how well the generated Terraform
    code represents the original inventory resources.

    Args:
        state: Current state with resources and generated_code

    Returns:
        Dict with comparison_result containing coverage analysis
    """
    resources: List[Any] = state.get("resources", [])
    generated_code: Dict[str, str] = state.get("generated_code", {})

    if not resources:
        return {
            "comparison_result": {
                "coverage_percentage": 0.0,
                "total_resources": 0,
                "represented_count": 0,
                "missing_count": 0,
                "represented_resources": [],
                "missing_resources": [],
                "issues": [],
                "summary": "No resources in inventory to compare.",
            }
        }

    if not generated_code:
        return {
            "comparison_result": {
                "coverage_percentage": 0.0,
                "total_resources": len(resources),
                "represented_count": 0,
                "missing_count": len(resources),
                "represented_resources": [],
                "missing_resources": [
                    {
                        "type": _get_resource_type(r),
                        "name": _get_resource_name(r),
                        "reason": "No Terraform code generated",
                    }
                    for r in resources
                ],
                "issues": [{"severity": "error", "resource": "all", "description": "No Terraform code was generated"}],
                "summary": "No Terraform code was generated to compare against inventory.",
            }
        }

    config = GenerationConfig.from_env()

    inventory_text = _format_inventory_for_comparison(resources)
    terraform_text = _combine_generated_code(generated_code)

    try:
        client = boto3.client("bedrock-runtime", region_name=config.bedrock_region)

        system_prompt = _get_comparison_system_prompt()
        user_prompt = _format_comparison_prompt(inventory_text, terraform_text, len(resources))

        response = client.converse(
            modelId=config.bedrock_model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_prompt}],
                }
            ],
            system=[{"text": system_prompt}],
            inferenceConfig={
                "temperature": 0.1,
                "maxTokens": config.max_tokens,
            },
        )

        response_text = response["output"]["message"]["content"][0]["text"] or ""
        comparison_result = _parse_comparison_response(response_text, len(resources))

        return {"comparison_result": comparison_result}

    except Exception as e:
        return {
            "comparison_result": {
                "coverage_percentage": 0.0,
                "total_resources": len(resources),
                "represented_count": 0,
                "missing_count": len(resources),
                "represented_resources": [],
                "missing_resources": [],
                "issues": [{"severity": "error", "resource": "comparison", "description": f"Comparison failed: {e}"}],
                "summary": f"Unable to perform comparison due to error: {e}",
            },
            "errors": [{"message": f"Inventory comparison failed: {e}"}],
        }


def _get_resource_type(resource: Any) -> str:
    """Extract resource type from TrackedResource or dict."""
    if isinstance(resource, TrackedResource):
        return resource.resource_type
    if isinstance(resource, dict):
        return resource.get("resource_type", resource.get("type", "unknown"))
    return "unknown"


def _get_resource_name(resource: Any) -> str:
    """Extract resource name from TrackedResource or dict."""
    if isinstance(resource, TrackedResource):
        return resource.name
    if isinstance(resource, dict):
        return resource.get("name", "unnamed")
    return "unnamed"


def _format_inventory_for_comparison(resources: List[Any]) -> str:
    """Format inventory resources for AI comparison prompt.

    Args:
        resources: List of TrackedResource objects or resource dicts

    Returns:
        Formatted string listing all resources with key attributes
    """
    lines = []
    for i, resource in enumerate(resources, 1):
        if isinstance(resource, TrackedResource):
            resource_type = resource.resource_type
            name = resource.name
            arn = resource.arn
            raw_config = resource.raw_config
        else:
            resource_type = resource.get("resource_type", resource.get("type", "unknown"))
            name = resource.get("name", "unnamed")
            arn = resource.get("arn", "")
            raw_config = resource.get("raw_config", {})

        key_attrs = _extract_key_attributes(resource_type, raw_config)
        attrs_str = ", ".join(f"{k}={v}" for k, v in key_attrs.items()) if key_attrs else "none"

        lines.append(f"{i}. Type: {resource_type} | Name: {name} | ARN: {arn} | Key attrs: {attrs_str}")

    return "\n".join(lines)


def _extract_key_attributes(resource_type: str, raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key configuration attributes based on resource type.

    Args:
        resource_type: AWS resource type (e.g., ec2:vpc, lambda:function)
        raw_config: Raw configuration dictionary

    Returns:
        Dictionary of key attributes for comparison
    """
    key_attrs: Dict[str, Any] = {}

    if "vpc" in resource_type:
        for key in ["CidrBlock", "VpcId", "EnableDnsSupport", "EnableDnsHostnames"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "subnet" in resource_type:
        for key in ["CidrBlock", "SubnetId", "VpcId", "AvailabilityZone"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "lambda" in resource_type:
        for key in ["Runtime", "Handler", "MemorySize", "Timeout", "FunctionName"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "s3" in resource_type:
        for key in ["BucketName", "VersioningStatus"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "rds" in resource_type:
        for key in ["Engine", "EngineVersion", "DBInstanceClass", "AllocatedStorage"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "security-group" in resource_type or "securitygroup" in resource_type.lower():
        for key in ["GroupId", "GroupName", "VpcId"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "instance" in resource_type:
        for key in ["InstanceType", "InstanceId", "ImageId"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    elif "role" in resource_type:
        for key in ["RoleName", "Path"]:
            if key in raw_config:
                key_attrs[key] = raw_config[key]
    else:
        for key in list(raw_config.keys())[:3]:
            if not key.startswith("_") and raw_config[key] is not None:
                key_attrs[key] = raw_config[key]

    return key_attrs


def _combine_generated_code(generated_code: Dict[str, str]) -> str:
    """Combine all generated Terraform code with layer markers.

    Args:
        generated_code: Dictionary mapping layer names to Terraform code

    Returns:
        Combined code string with layer delimiters
    """
    sections = []
    for layer_name, code in generated_code.items():
        sections.append(f"# === LAYER: {layer_name} ===\n{code}")
    return "\n\n".join(sections)


def _get_comparison_system_prompt() -> str:
    """Get the system prompt for inventory comparison."""
    return (
        "You are an expert Terraform and AWS infrastructure analyst. "
        "Your task is to compare an AWS resource inventory against generated Terraform code "
        "and determine how well the Terraform represents the original resources.\n\n"
        "You must respond with ONLY valid JSON in the exact structure specified. "
        "Do not include any text before or after the JSON.\n\n"
        "MATCHING RULES - A resource is REPRESENTED if:\n"
        "1. The Terraform resource TYPE matches the AWS resource type:\n"
        "   - ec2:vpc → aws_vpc\n"
        "   - ec2:subnet → aws_subnet\n"
        "   - ec2:security-group → aws_security_group\n"
        "   - s3:bucket → aws_s3_bucket\n"
        "   - lambda:function → aws_lambda_function\n"
        "   - iam:role → aws_iam_role\n"
        "   - rds:db-instance → aws_db_instance\n"
        "2. The resource can be identified by ANY of these:\n"
        "   - Similar name (ignore case, hyphens vs underscores: 'my-vpc' matches 'my_vpc')\n"
        "   - Matching key attributes (CIDR block, function name, bucket name, etc.)\n"
        "   - Same resource count of that type if names differ\n\n"
        "BE GENEROUS in matching - if a Terraform resource exists for the same type "
        "and has similar identifying attributes, count it as represented. "
        "Only mark as MISSING if there is NO corresponding Terraform resource of that type.\n\n"
        "Issues should only flag SIGNIFICANT problems like:\n"
        "- Missing required attributes that would cause deployment failure\n"
        "- Security misconfigurations\n"
        "- Hardcoded values that should be variables"
    )


def _format_comparison_prompt(inventory_text: str, terraform_text: str, total_resources: int) -> str:
    """Format the user prompt for comparison.

    Args:
        inventory_text: Formatted inventory resources
        terraform_text: Combined Terraform code
        total_resources: Total number of resources in inventory

    Returns:
        Formatted prompt string
    """
    return f"""Compare the following AWS inventory resources against the generated Terraform code.

## INVENTORY RESOURCES ({total_resources} total):
{inventory_text}

## GENERATED TERRAFORM CODE:
{terraform_text}

## MATCHING INSTRUCTIONS:
For EACH inventory resource, find the corresponding Terraform resource by:
1. Match the resource TYPE (ec2:subnet → aws_subnet, s3:bucket → aws_s3_bucket, etc.)
2. Match by name OR key attributes (CIDR, function_name, bucket name, etc.)
3. Treat hyphens and underscores as equivalent (my-vpc = my_vpc)
4. If multiple resources of same type exist, match by count and attributes

A resource IS REPRESENTED if there's a Terraform resource of the matching type with similar config.
A resource is MISSING ONLY if no Terraform resource of that type exists for it.

## REQUIRED OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure:
{{
    "coverage_percentage": <float 0-100>,
    "total_resources": {total_resources},
    "represented_count": <int>,
    "missing_count": <int>,
    "represented_resources": [
        {{"type": "<resource_type>", "name": "<resource_name>", "terraform_resource": "<aws_resource.name>"}}
    ],
    "missing_resources": [
        {{"type": "<resource_type>", "name": "<resource_name>", "reason": "<why missing>"}}
    ],
    "issues": [
        {{"severity": "warning|error", "resource": "<resource_name>", "description": "<issue description>"}}
    ],
    "summary": "<2-3 sentence summary of coverage and key findings>"
}}

CRITICAL RULES:
- represented_count + missing_count MUST equal {total_resources}
- Every inventory resource MUST appear in either represented_resources OR missing_resources
- Be GENEROUS - if a matching Terraform resource exists, count it as represented"""


def _parse_comparison_response(response_text: str, total_resources: int) -> Dict[str, Any]:
    """Parse AI response into structured comparison result.

    Args:
        response_text: Raw response from Bedrock
        total_resources: Expected total resource count

    Returns:
        Structured comparison result dictionary
    """
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if json_match:
        try:
            result = json.loads(json_match.group())

            if not isinstance(result.get("coverage_percentage"), (int, float)):
                result["coverage_percentage"] = 0.0
            if not isinstance(result.get("total_resources"), int):
                result["total_resources"] = total_resources
            if not isinstance(result.get("represented_count"), int):
                result["represented_count"] = 0
            if not isinstance(result.get("missing_count"), int):
                result["missing_count"] = total_resources
            if not isinstance(result.get("represented_resources"), list):
                result["represented_resources"] = []
            if not isinstance(result.get("missing_resources"), list):
                result["missing_resources"] = []
            if not isinstance(result.get("issues"), list):
                result["issues"] = []
            if not isinstance(result.get("summary"), str):
                result["summary"] = "Comparison completed."

            return result
        except json.JSONDecodeError:
            pass

    return {
        "coverage_percentage": 0.0,
        "total_resources": total_resources,
        "represented_count": 0,
        "missing_count": total_resources,
        "represented_resources": [],
        "missing_resources": [],
        "issues": [
            {"severity": "error", "resource": "parser", "description": "Failed to parse AI comparison response"}
        ],
        "summary": f"Unable to parse comparison response. Raw output: {response_text[:200]}...",
    }
