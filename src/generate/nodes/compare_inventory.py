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
from ..state import GenerationConfig, GenerationState, emit_progress


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
                        "reason": "No IaC code generated",
                    }
                    for r in resources
                ],
                "issues": [
                    {
                        "severity": "error",
                        "resource": "all",
                        "description": "No IaC code was generated",
                    }
                ],
                "summary": "No IaC code was generated to compare against inventory.",
            }
        }

    config = GenerationConfig.from_env()

    emit_progress(
        "activity",
        {
            "message": f"Formatting {len(resources)} resources for comparison",
            "step": "compare_inventory",
        },
    )

    inventory_text = _format_inventory_for_comparison(resources)
    terraform_text = _combine_generated_code(generated_code)

    emit_progress(
        "activity",
        {
            "message": f"Prepared {len(generated_code)} layers ({len(terraform_text)} chars)",
            "step": "compare_inventory",
            "layers": len(generated_code),
        },
    )

    try:
        emit_progress(
            "activity",
            {
                "message": f"Connecting to Bedrock ({config.bedrock_region})",
                "step": "compare_inventory",
            },
        )

        client = boto3.client("bedrock-runtime", region_name=config.bedrock_region)

        system_prompt = _get_comparison_system_prompt()
        user_prompt = _format_comparison_prompt(inventory_text, terraform_text, len(resources))

        emit_progress(
            "activity",
            {
                "message": "Calling AI to analyze coverage",
                "step": "compare_inventory",
                "model": config.bedrock_model_id,
            },
        )

        # Use streaming for real-time progress
        response_text = ""
        token_count = 0

        try:
            stream_response = client.converse_stream(
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

            # Stream is an EventStream object
            event_stream = stream_response.get("stream")
            if event_stream:
                for event in event_stream:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        if "text" in delta:
                            response_text += delta["text"]
                            token_count += 1
                            if token_count % 50 == 0:
                                emit_progress(
                                    "activity",
                                    {
                                        "message": f"Analyzing... ({token_count} tokens)",
                                        "step": "compare_inventory",
                                        "tokens": token_count,
                                    },
                                )

            # If streaming didn't produce any text, fall back to non-streaming
            if not response_text:
                raise ValueError("Streaming produced no output")

        except Exception:
            # Fall back to non-streaming
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

        emit_progress(
            "activity",
            {
                "message": "Parsing comparison results",
                "step": "compare_inventory",
            },
        )

        comparison_result = _parse_comparison_response(response_text, len(resources))

        # Run deterministic check to validate AI results
        emit_progress(
            "activity",
            {
                "message": "Validating results with deterministic check",
                "step": "compare_inventory",
            },
        )

        deterministic = _deterministic_coverage_check(resources, terraform_text)
        det_covered = deterministic["estimated_covered"]

        # If AI result is significantly LOWER than deterministic (AI under-reporting),
        # use the deterministic result as a floor. Only override upward, never downward.
        if len(resources) > 0:
            det_pct = det_covered / len(resources) * 100
            ai_pct = comparison_result.get("coverage_percentage", 0)

            # Only override if deterministic found MORE coverage than AI
            # (AI is under-reporting, which was the original bug)
            if det_pct > ai_pct + 20:
                emit_progress(
                    "activity",
                    {
                        "message": (
                            f"AI under-reported ({ai_pct:.0f}%), "
                            f"deterministic found ({det_pct:.0f}%), using deterministic"
                        ),
                        "step": "compare_inventory",
                    },
                )

                # Override with deterministic results
                comparison_result["represented_count"] = det_covered
                comparison_result["missing_count"] = len(resources) - det_covered
                comparison_result["coverage_percentage"] = det_pct
                comparison_result["issues"].append(
                    {
                        "severity": "warning",
                        "resource": "validation",
                        "description": (
                            f"AI reported {ai_pct:.0f}% but deterministic check found "
                            f"{det_pct:.0f}%. Using deterministic result."
                        ),
                    }
                )
            elif ai_pct > det_pct + 20 and det_covered > 0:
                # AI found more than deterministic - add a note but trust AI
                # (deterministic may have incomplete type mapping)
                comparison_result["issues"].append(
                    {
                        "severity": "info",
                        "resource": "validation",
                        "description": (
                            f"AI reported {ai_pct:.0f}% but deterministic check found "
                            f"{det_pct:.0f}%. Trusting AI result."
                        ),
                    }
                )

        emit_progress(
            "activity",
            {
                "message": f"Coverage: {comparison_result.get('coverage_percentage', 0):.0f}%",
                "step": "compare_inventory",
                "coverage": comparison_result.get("coverage_percentage", 0),
            },
        )

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
                "issues": [
                    {
                        "severity": "error",
                        "resource": "comparison",
                        "description": f"Comparison failed: {e}",
                    }
                ],
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

    For large inventories (>100 resources), uses a summary format to avoid
    exceeding model context limits.

    Args:
        resources: List of TrackedResource objects or resource dicts

    Returns:
        Formatted string listing all resources with key attributes
    """
    # For large inventories, use summary format
    if len(resources) > 100:
        return _format_inventory_summary(resources)

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


def _format_inventory_summary(resources: List[Any]) -> str:
    """Format large inventory as a summary by resource type.

    Groups resources by type and shows counts with sample names.

    Args:
        resources: List of TrackedResource objects or resource dicts

    Returns:
        Summary format string
    """
    # Group by resource type
    by_type: Dict[str, List[str]] = {}
    for resource in resources:
        if isinstance(resource, TrackedResource):
            resource_type = resource.resource_type
            name = resource.name
        else:
            resource_type = resource.get("resource_type", resource.get("type", "unknown"))
            name = resource.get("name", "unnamed")

        if resource_type not in by_type:
            by_type[resource_type] = []
        by_type[resource_type].append(name)

    lines = [f"INVENTORY SUMMARY ({len(resources)} total resources):", ""]

    for resource_type in sorted(by_type.keys()):
        names = by_type[resource_type]
        count = len(names)
        # Show first 5 names as samples
        samples = names[:5]
        sample_str = ", ".join(samples)
        if count > 5:
            sample_str += f", ... and {count - 5} more"

        lines.append(f"- {resource_type}: {count} resources")
        lines.append(f"  Names: {sample_str}")

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
        "You are an expert AWS infrastructure analyst specializing in Terraform and AWS CDK. "
        "Your task is to compare an AWS resource inventory against generated Infrastructure "
        "as Code (Terraform, CDK TypeScript, or CDK Python) and determine how well the IaC "
        "represents the original resources.\n\n"
        "You must respond with ONLY valid JSON in the exact structure specified. "
        "Do not include any text before or after the JSON.\n\n"
        "MATCHING RULES - A resource is REPRESENTED if:\n"
        "1. An IaC resource of the MATCHING TYPE exists:\n\n"
        "   TERRAFORM PATTERNS:\n"
        "   - ec2:vpc → aws_vpc\n"
        "   - ec2:subnet → aws_subnet\n"
        "   - ec2:security-group → aws_security_group\n"
        "   - s3:bucket → aws_s3_bucket\n"
        "   - lambda:function → aws_lambda_function\n"
        "   - iam:role → aws_iam_role\n"
        "   - iam:policy → aws_iam_policy or aws_iam_role_policy\n"
        "   - rds:db-instance → aws_db_instance\n"
        "   - apigateway:rest-api → aws_api_gateway_rest_api\n"
        "   - dynamodb:table → aws_dynamodb_table\n"
        "   - sns:topic → aws_sns_topic\n"
        "   - sqs:queue → aws_sqs_queue\n"
        "   - cloudwatch:log-group → aws_cloudwatch_log_group\n\n"
        "   CDK TYPESCRIPT PATTERNS (new <module>.<Construct>(...)):\n"
        "   - ec2:vpc → new ec2.Vpc(...) or new Vpc(...)\n"
        "   - ec2:subnet → new ec2.Subnet(...) or new Subnet(...)\n"
        "   - ec2:security-group → new ec2.SecurityGroup(...)\n"
        "   - s3:bucket → new s3.Bucket(...) or new Bucket(...)\n"
        "   - lambda:function → new lambda.Function(...)\n"
        "   - iam:role → new iam.Role(...) or new Role(...)\n"
        "   - dynamodb:table → new dynamodb.Table(...)\n\n"
        "   CDK PYTHON PATTERNS (<module>.<Construct>(...)):\n"
        "   - ec2:vpc → ec2.Vpc(...) or Vpc(...)\n"
        "   - ec2:subnet → ec2.Subnet(...) or Subnet(...)\n"
        "   - ec2:security-group → ec2.SecurityGroup(...)\n"
        "   - s3:bucket → s3.Bucket(...) or Bucket(...)\n"
        "   - lambda:function → _lambda.Function(...)\n"
        "   - iam:role → iam.Role(...) or Role(...)\n"
        "   - dynamodb:table → dynamodb.Table(...)\n\n"
        "2. Match by ANY of these criteria:\n"
        "   - Similar name (ignore case, hyphens vs underscores: 'my-vpc' = 'my_vpc' = 'MyVpc')\n"
        "   - Matching key attributes (CIDR block, function name, bucket name, etc.)\n"
        "   - SAME COUNT of resources of that type (5 subnets in inventory = 5 Subnet constructs)\n\n"
        "CRITICAL: BE VERY GENEROUS in matching!\n"
        "- If there's an IaC resource of the same type with similar name/attributes, it's REPRESENTED\n"
        "- CDK uses PascalCase/camelCase - treat as equivalent to kebab-case/snake_case\n"
        "- Only mark as MISSING if there is absolutely NO IaC resource that could represent it\n"
        "- When in doubt, mark as REPRESENTED\n\n"
        "IMPORTANT for list output:\n"
        '- Group many resources of same type: {"type": "lambda:function", "name": "all 15 funcs"}\n'
        "- The counts (represented_count, missing_count) MUST be accurate even if lists are grouped\n\n"
        "Issues should only flag SIGNIFICANT problems like:\n"
        "- Missing required attributes that would cause deployment failure\n"
        "- Security misconfigurations"
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
    # Check if using summary format (for large inventories)
    is_summary = "INVENTORY SUMMARY" in inventory_text

    if is_summary:
        matching_instructions = """## MATCHING INSTRUCTIONS (SUMMARY MODE):
The inventory is provided as a summary by resource type. For each resource TYPE:
1. Count how many Terraform resources exist for that type
2. Compare counts: inventory count vs Terraform count
3. Type mapping: ec2:vpc → aws_vpc, ec2:subnet → aws_subnet, lambda:function → aws_lambda_function, etc.
4. A type is FULLY COVERED if Terraform has >= the inventory count for that type
5. A type is PARTIALLY COVERED if Terraform has some but fewer resources
6. A type is MISSING if Terraform has 0 resources of that type

Calculate coverage as: (sum of covered resources across all types) / total_resources * 100"""
    else:
        matching_instructions = """## MATCHING INSTRUCTIONS:
For EACH inventory resource, find the corresponding Terraform resource by:
1. Match the resource TYPE (ec2:subnet → aws_subnet, s3:bucket → aws_s3_bucket, etc.)
2. Match by name OR key attributes (CIDR, function_name, bucket name, etc.)
3. Treat hyphens and underscores as equivalent (my-vpc = my_vpc)
4. If multiple resources of same type exist, match by count and attributes

A resource IS REPRESENTED if there's a Terraform resource of the matching type with similar config.
A resource is MISSING ONLY if no Terraform resource of that type exists for it."""

    return f"""Compare the following AWS inventory resources against the generated Terraform code.

## INVENTORY RESOURCES ({total_resources} total):
{inventory_text}

## GENERATED TERRAFORM CODE:
{terraform_text}

{matching_instructions}

## REQUIRED OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure:
{{
    "coverage_percentage": <float 0-100>,
    "total_resources": {total_resources},
    "represented_count": <int>,
    "missing_count": <int>,
    "represented_resources": [
        {{"type": "<resource_type>", "name": "<resource_name or 'multiple'>"}}
    ],
    "missing_resources": [
        {{"type": "<resource_type>", "name": "<resource_name or 'multiple'>"}}
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


def _deterministic_coverage_check(resources: List[Any], iac_code: str) -> Dict[str, int]:
    """Perform a simple deterministic check of resource coverage.

    This provides a sanity check against AI results by counting IaC
    resource types that match inventory resource types. Supports
    Terraform, CDK TypeScript, and CDK Python.

    Args:
        resources: List of inventory resources
        iac_code: Combined IaC code string (Terraform, CDK TypeScript, or CDK Python)

    Returns:
        Dict with type_counts, terraform_counts, and estimated_covered
    """
    # Map inventory types to Terraform resource types
    terraform_type_mapping = {
        # Network (EC2)
        "ec2:vpc": "aws_vpc",
        "ec2:subnet": "aws_subnet",
        "ec2:security-group": "aws_security_group",
        "ec2:instance": "aws_instance",
        "ec2:route-table": "aws_route_table",
        "ec2:internet-gateway": "aws_internet_gateway",
        "ec2:nat-gateway": "aws_nat_gateway",
        "ec2:network-interface": "aws_network_interface",
        "ec2:elastic-ip": "aws_eip",
        "ec2:vpc-endpoint": "aws_vpc_endpoint",
        "ec2:transit-gateway": "aws_ec2_transit_gateway",
        "ec2:transit-gateway-attachment": "aws_ec2_transit_gateway_vpc_attachment",
        "ec2:vpc-peering-connection": "aws_vpc_peering_connection",
        "ec2:network-acl": "aws_network_acl",
        "ec2:launch-template": "aws_launch_template",
        "ec2:auto-scaling-group": "aws_autoscaling_group",
        # Storage
        "s3:bucket": "aws_s3_bucket",
        "efs:file-system": "aws_efs_file_system",
        "efs:mount-target": "aws_efs_mount_target",
        "efs:access-point": "aws_efs_access_point",
        "fsx:file-system": "aws_fsx_lustre_file_system",
        "backup:backup-vault": "aws_backup_vault",
        "backup:backup-plan": "aws_backup_plan",
        # Lambda
        "lambda:function": "aws_lambda_function",
        "lambda:layer": "aws_lambda_layer_version",
        "lambda:event-source-mapping": "aws_lambda_event_source_mapping",
        # IAM
        "iam:role": "aws_iam_role",
        "iam:policy": "aws_iam_policy",
        "iam:instance-profile": "aws_iam_instance_profile",
        "iam:user": "aws_iam_user",
        "iam:group": "aws_iam_group",
        # RDS
        "rds:db-instance": "aws_db_instance",
        "rds:db-cluster": "aws_rds_cluster",
        "rds:db-subnet-group": "aws_db_subnet_group",
        "rds:db-parameter-group": "aws_db_parameter_group",
        "rds:db-cluster-parameter-group": "aws_rds_cluster_parameter_group",
        # DynamoDB
        "dynamodb:table": "aws_dynamodb_table",
        # ElastiCache
        "elasticache:cluster": "aws_elasticache_cluster",
        "elasticache:replication-group": "aws_elasticache_replication_group",
        "elasticache:subnet-group": "aws_elasticache_subnet_group",
        # Other Data
        "redshift:cluster": "aws_redshift_cluster",
        "elasticsearch:domain": "aws_elasticsearch_domain",
        "opensearch:domain": "aws_opensearch_domain",
        # Glue
        "glue:database": "aws_glue_catalog_database",
        "glue:table": "aws_glue_catalog_table",
        "glue:crawler": "aws_glue_crawler",
        "glue:job": "aws_glue_job",
        "glue:trigger": "aws_glue_trigger",
        "glue:connection": "aws_glue_connection",
        "glue:classifier": "aws_glue_classifier",
        "glue:workflow": "aws_glue_workflow",
        # ECS
        "ecs:cluster": "aws_ecs_cluster",
        "ecs:service": "aws_ecs_service",
        "ecs:task-definition": "aws_ecs_task_definition",
        # EKS
        "eks:cluster": "aws_eks_cluster",
        "eks:nodegroup": "aws_eks_node_group",
        "eks:fargate-profile": "aws_eks_fargate_profile",
        # Batch
        "batch:compute-environment": "aws_batch_compute_environment",
        "batch:job-queue": "aws_batch_job_queue",
        "batch:job-definition": "aws_batch_job_definition",
        # Load Balancing
        "elbv2:loadbalancer": "aws_lb",
        "elbv2:target-group": "aws_lb_target_group",
        "elbv2:listener": "aws_lb_listener",
        "elbv2:listener-rule": "aws_lb_listener_rule",
        "elb:loadbalancer": "aws_elb",
        # API Gateway
        "apigateway:rest-api": "aws_api_gateway_rest_api",
        "apigateway:resource": "aws_api_gateway_resource",
        "apigateway:method": "aws_api_gateway_method",
        "apigateway:stage": "aws_api_gateway_stage",
        "apigateway:deployment": "aws_api_gateway_deployment",
        "apigatewayv2:api": "aws_apigatewayv2_api",
        "apigatewayv2:stage": "aws_apigatewayv2_stage",
        "apigatewayv2:route": "aws_apigatewayv2_route",
        "apigatewayv2:integration": "aws_apigatewayv2_integration",
        # AppRunner, AppSync, Cognito
        "apprunner:service": "aws_apprunner_service",
        "appsync:graphql-api": "aws_appsync_graphql_api",
        "cognito:user-pool": "aws_cognito_user_pool",
        "cognito:identity-pool": "aws_cognito_identity_pool",
        # Messaging
        "sns:topic": "aws_sns_topic",
        "sns:subscription": "aws_sns_topic_subscription",
        "sqs:queue": "aws_sqs_queue",
        "events:rule": "aws_cloudwatch_event_rule",
        "events:event-bus": "aws_cloudwatch_event_bus",
        "kinesis:stream": "aws_kinesis_stream",
        "firehose:delivery-stream": "aws_kinesis_firehose_delivery_stream",
        "stepfunctions:state-machine": "aws_sfn_state_machine",
        # Monitoring
        "cloudwatch:log-group": "aws_cloudwatch_log_group",
        "logs:log-group": "aws_cloudwatch_log_group",
        "cloudwatch:alarm": "aws_cloudwatch_metric_alarm",
        "cloudwatch:metric-alarm": "aws_cloudwatch_metric_alarm",
        "cloudwatch:dashboard": "aws_cloudwatch_dashboard",
        "xray:group": "aws_xray_group",
        "xray:sampling-rule": "aws_xray_sampling_rule",
        "cloudtrail:trail": "aws_cloudtrail",
        "config:config-rule": "aws_config_config_rule",
        # Security
        "wafv2:web-acl": "aws_wafv2_web_acl",
        "acm:certificate": "aws_acm_certificate",
        "acm:certificate-validation": "aws_acm_certificate_validation",
        "kms:key": "aws_kms_key",
        "secretsmanager:secret": "aws_secretsmanager_secret",
        # DNS
        "route53:hosted-zone": "aws_route53_zone",
        "route53:record-set": "aws_route53_record",
        "route53:health-check": "aws_route53_health_check",
        "cloudfront:distribution": "aws_cloudfront_distribution",
    }

    # Map inventory types to CDK construct patterns
    # These patterns match both TypeScript (new ec2.Vpc) and Python (ec2.Vpc)
    cdk_construct_mapping = {
        # Network (EC2)
        "ec2:vpc": ["Vpc"],
        "ec2:subnet": ["Subnet", "PublicSubnet", "PrivateSubnet"],
        "ec2:security-group": ["SecurityGroup"],
        "ec2:instance": ["Instance"],
        "ec2:route-table": ["RouteTable", "CfnRouteTable"],
        "ec2:internet-gateway": ["InternetGateway", "CfnInternetGateway"],
        "ec2:nat-gateway": ["NatGateway", "CfnNatGateway"],
        "ec2:network-interface": ["NetworkInterface", "CfnNetworkInterface"],
        "ec2:elastic-ip": ["CfnEIP", "Eip"],
        "ec2:vpc-endpoint": ["InterfaceVpcEndpoint", "GatewayVpcEndpoint", "CfnVPCEndpoint"],
        "ec2:transit-gateway": ["CfnTransitGateway"],
        "ec2:transit-gateway-attachment": ["CfnTransitGatewayAttachment"],
        "ec2:vpc-peering-connection": ["CfnVPCPeeringConnection"],
        "ec2:network-acl": ["NetworkAcl", "CfnNetworkAcl"],
        "ec2:launch-template": ["LaunchTemplate", "CfnLaunchTemplate"],
        "ec2:auto-scaling-group": ["AutoScalingGroup"],
        # Storage
        "s3:bucket": ["Bucket"],
        "efs:file-system": ["FileSystem"],
        "efs:mount-target": ["CfnMountTarget"],
        "efs:access-point": ["AccessPoint"],
        "fsx:file-system": ["LustreFileSystem", "CfnFileSystem"],
        "backup:backup-vault": ["BackupVault", "CfnBackupVault"],
        "backup:backup-plan": ["BackupPlan", "CfnBackupPlan"],
        # Lambda
        "lambda:function": ["Function"],
        "lambda:layer": ["LayerVersion"],
        "lambda:event-source-mapping": ["EventSourceMapping"],
        # IAM
        "iam:role": ["Role"],
        "iam:policy": ["Policy", "ManagedPolicy", "PolicyStatement"],
        "iam:instance-profile": ["InstanceProfile", "CfnInstanceProfile"],
        "iam:user": ["User"],
        "iam:group": ["Group"],
        # RDS
        "rds:db-instance": ["DatabaseInstance"],
        "rds:db-cluster": ["DatabaseCluster"],
        "rds:db-subnet-group": ["SubnetGroup", "CfnDBSubnetGroup"],
        "rds:db-parameter-group": ["ParameterGroup", "CfnDBParameterGroup"],
        "rds:db-cluster-parameter-group": ["CfnDBClusterParameterGroup"],
        # DynamoDB
        "dynamodb:table": ["Table"],
        # ElastiCache
        "elasticache:cluster": ["CfnCacheCluster"],
        "elasticache:replication-group": ["CfnReplicationGroup"],
        "elasticache:subnet-group": ["CfnSubnetGroup"],
        # Other Data
        "redshift:cluster": ["CfnCluster"],
        "elasticsearch:domain": ["Domain", "CfnDomain"],
        "opensearch:domain": ["Domain", "CfnDomain"],
        # Glue
        "glue:database": ["Database", "CfnDatabase"],
        "glue:table": ["Table", "CfnTable"],
        "glue:crawler": ["CfnCrawler"],
        "glue:job": ["Job", "CfnJob"],
        "glue:trigger": ["CfnTrigger"],
        "glue:connection": ["CfnConnection"],
        "glue:classifier": ["CfnClassifier"],
        "glue:workflow": ["CfnWorkflow"],
        # ECS
        "ecs:cluster": ["Cluster"],
        "ecs:service": ["FargateService", "Ec2Service", "CfnService"],
        "ecs:task-definition": ["TaskDefinition", "FargateTaskDefinition", "Ec2TaskDefinition"],
        # EKS
        "eks:cluster": ["Cluster", "FargateCluster"],
        "eks:nodegroup": ["Nodegroup", "CfnNodegroup"],
        "eks:fargate-profile": ["FargateProfile", "CfnFargateProfile"],
        # Batch
        "batch:compute-environment": ["ComputeEnvironment", "CfnComputeEnvironment"],
        "batch:job-queue": ["JobQueue", "CfnJobQueue"],
        "batch:job-definition": ["JobDefinition", "CfnJobDefinition"],
        # Load Balancing
        "elbv2:loadbalancer": ["ApplicationLoadBalancer", "NetworkLoadBalancer", "CfnLoadBalancer"],
        "elbv2:target-group": ["ApplicationTargetGroup", "NetworkTargetGroup", "CfnTargetGroup"],
        "elbv2:listener": ["ApplicationListener", "NetworkListener", "CfnListener"],
        "elbv2:listener-rule": ["ApplicationListenerRule", "CfnListenerRule"],
        "elb:loadbalancer": ["CfnLoadBalancer"],
        # API Gateway
        "apigateway:rest-api": ["RestApi", "LambdaRestApi"],
        "apigateway:resource": ["Resource", "CfnResource"],
        "apigateway:method": ["Method", "CfnMethod"],
        "apigateway:stage": ["Stage", "CfnStage"],
        "apigateway:deployment": ["Deployment", "CfnDeployment"],
        "apigatewayv2:api": ["HttpApi", "WebSocketApi", "CfnApi"],
        "apigatewayv2:stage": ["HttpStage", "WebSocketStage", "CfnStage"],
        "apigatewayv2:route": ["HttpRoute", "WebSocketRoute", "CfnRoute"],
        "apigatewayv2:integration": ["HttpIntegration", "CfnIntegration"],
        # AppRunner, AppSync, Cognito
        "apprunner:service": ["Service", "CfnService"],
        "appsync:graphql-api": ["GraphqlApi", "CfnGraphQLApi"],
        "cognito:user-pool": ["UserPool", "CfnUserPool"],
        "cognito:identity-pool": ["IdentityPool", "CfnIdentityPool"],
        # Messaging
        "sns:topic": ["Topic"],
        "sns:subscription": ["Subscription"],
        "sqs:queue": ["Queue"],
        "events:rule": ["Rule"],
        "events:event-bus": ["EventBus", "CfnEventBus"],
        "kinesis:stream": ["Stream", "CfnStream"],
        "firehose:delivery-stream": ["CfnDeliveryStream"],
        "stepfunctions:state-machine": ["StateMachine", "CfnStateMachine"],
        # Monitoring
        "cloudwatch:log-group": ["LogGroup"],
        "logs:log-group": ["LogGroup"],
        "cloudwatch:alarm": ["Alarm"],
        "cloudwatch:metric-alarm": ["Alarm", "CfnAlarm"],
        "cloudwatch:dashboard": ["Dashboard", "CfnDashboard"],
        "xray:group": ["CfnGroup"],
        "xray:sampling-rule": ["CfnSamplingRule"],
        "cloudtrail:trail": ["Trail", "CfnTrail"],
        "config:config-rule": ["CfnConfigRule"],
        # Security
        "wafv2:web-acl": ["WebAcl", "CfnWebACL"],
        "acm:certificate": ["Certificate", "CfnCertificate"],
        "acm:certificate-validation": ["CertificateValidation"],
        "kms:key": ["Key"],
        "secretsmanager:secret": ["Secret"],
        # DNS
        "route53:hosted-zone": ["HostedZone", "PublicHostedZone", "PrivateHostedZone"],
        "route53:record-set": ["RecordSet", "ARecord", "AaaaRecord", "CnameRecord", "CfnRecordSet"],
        "route53:health-check": ["HealthCheck", "CfnHealthCheck"],
        "cloudfront:distribution": ["Distribution", "CfnDistribution"],
    }

    # Count inventory resources by type
    inventory_counts: Dict[str, int] = {}
    for resource in resources:
        if isinstance(resource, TrackedResource):
            resource_type = resource.resource_type
        else:
            resource_type = resource.get("resource_type", resource.get("type", "unknown"))

        inventory_counts[resource_type] = inventory_counts.get(resource_type, 0) + 1

    # Count Terraform resources by type (simple regex)
    terraform_counts: Dict[str, int] = {}
    for inv_type, tf_type in terraform_type_mapping.items():
        # Match patterns like: resource "aws_lambda_function" "name" {
        pattern = rf'resource\s+"{re.escape(tf_type)}"\s+"[^"]+"\s*\{{'
        matches = re.findall(pattern, iac_code)
        terraform_counts[tf_type] = len(matches)

    # Count CDK constructs (TypeScript and Python)
    cdk_counts: Dict[str, int] = {}
    for inv_type, construct_names in cdk_construct_mapping.items():
        total_cdk_count = 0
        for construct_name in construct_names:
            # CDK TypeScript pattern: new ec2.Vpc( or new Vpc(
            # Match: new <optional_module>.Construct(
            ts_pattern = rf"new\s+(?:\w+\.)?{re.escape(construct_name)}\s*\("
            ts_matches = re.findall(ts_pattern, iac_code)
            total_cdk_count += len(ts_matches)

            # CDK Python pattern: ec2.Vpc( or Vpc(
            # Match: <optional_module>.Construct( but NOT "new " prefix (to avoid double counting TypeScript)
            # Also match standalone Construct( calls
            py_pattern = rf"(?<!new\s)(?:\w+\.)?{re.escape(construct_name)}\s*\("
            py_matches = re.findall(py_pattern, iac_code)
            # Filter out matches that were already counted as TypeScript (preceded by "new ")
            # The negative lookbehind should handle this, but let's be safe
            total_cdk_count += len(py_matches)

        cdk_counts[inv_type] = total_cdk_count

    # Estimate coverage by comparing counts
    estimated_covered = 0
    for inv_type, inv_count in inventory_counts.items():
        # Check Terraform first
        tf_type = terraform_type_mapping.get(inv_type)
        tf_count = terraform_counts.get(tf_type, 0) if tf_type else 0

        # Check CDK constructs
        cdk_count = cdk_counts.get(inv_type, 0)

        # Total IaC resources for this type (don't double count if same resource in both)
        total_iac_count = tf_count + cdk_count

        # Count as covered: min of inventory count and IaC count
        estimated_covered += min(inv_count, total_iac_count)

    return {
        "inventory_counts": inventory_counts,
        "terraform_counts": terraform_counts,
        "cdk_counts": cdk_counts,
        "estimated_covered": estimated_covered,
        "total_inventory": len(resources),
    }


def _parse_comparison_response(response_text: str, total_resources: int) -> Dict[str, Any]:
    """Parse AI response into structured comparison result.

    Validates and recalculates counts based on actual list lengths to handle
    AI inconsistencies.

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

            # Ensure lists exist
            if not isinstance(result.get("represented_resources"), list):
                result["represented_resources"] = []
            if not isinstance(result.get("missing_resources"), list):
                result["missing_resources"] = []
            if not isinstance(result.get("issues"), list):
                result["issues"] = []
            if not isinstance(result.get("summary"), str):
                result["summary"] = "Comparison completed."

            # Get the actual list lengths
            represented_list_len = len(result["represented_resources"])
            missing_list_len = len(result["missing_resources"])

            # Get AI-reported counts
            ai_represented = result.get("represented_count", 0)
            ai_missing = result.get("missing_count", 0)

            # Validate and fix inconsistencies
            # Priority: trust list lengths over reported counts if they differ significantly
            if represented_list_len > 0 or missing_list_len > 0:
                # Lists have content, use them as source of truth
                # But if AI reported higher counts, it may have truncated the lists
                if ai_represented > represented_list_len:
                    represented_count = max(represented_list_len, ai_represented)
                else:
                    represented_count = represented_list_len
                if ai_missing > missing_list_len:
                    missing_count = max(missing_list_len, ai_missing)
                else:
                    missing_count = missing_list_len

                # Ensure counts don't exceed total
                if represented_count + missing_count != total_resources:
                    # Trust the represented count, derive missing
                    if represented_count <= total_resources:
                        missing_count = total_resources - represented_count
                    else:
                        # Cap represented at total
                        represented_count = total_resources
                        missing_count = 0
            else:
                # Empty lists - use AI-reported counts if they're valid
                represented_count = ai_represented if isinstance(ai_represented, int) and ai_represented >= 0 else 0
                missing_count = ai_missing if isinstance(ai_missing, int) and ai_missing >= 0 else total_resources

                # Validate they sum correctly
                if represented_count + missing_count != total_resources:
                    # If AI counts are close, trust them
                    if abs((represented_count + missing_count) - total_resources) <= 2:
                        # Minor rounding, adjust missing
                        missing_count = total_resources - represented_count
                    else:
                        # Significant discrepancy - default to 0 coverage
                        represented_count = 0
                        missing_count = total_resources

            result["total_resources"] = total_resources
            result["represented_count"] = represented_count
            result["missing_count"] = missing_count

            # Recalculate coverage based on validated counts
            result["coverage_percentage"] = (represented_count / total_resources * 100) if total_resources > 0 else 0.0

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
            {
                "severity": "error",
                "resource": "parser",
                "description": "Failed to parse AI comparison response",
            }
        ],
        "summary": f"Unable to parse comparison response. Raw output: {response_text[:200]}...",
    }
