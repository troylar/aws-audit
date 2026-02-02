"""Categorize layers node for LangGraph workflow."""

import re
from collections import defaultdict
from typing import Any, Dict, List

from ...models.generation import TrackedResource
from ..layers import RESOURCE_TYPE_TO_LAYER, LayerOrder
from ..state import GenerationState

LAYER_NAMES = {
    LayerOrder.NETWORK: "Network Foundation",
    LayerOrder.SECURITY: "Security Groups",
    LayerOrder.IAM: "IAM Resources",
    LayerOrder.DATA: "Data Stores",
    LayerOrder.STORAGE: "Storage",
    LayerOrder.COMPUTE: "Compute",
    LayerOrder.LOADBALANCING: "Load Balancing",
    LayerOrder.APPLICATION: "Application",
    LayerOrder.MESSAGING: "Messaging",
    LayerOrder.MONITORING: "Monitoring",
    LayerOrder.DNS: "DNS & Routing",
}


def _ensure_unique_terraform_names(resources: List[TrackedResource]) -> None:
    """Ensure all resources have unique Terraform names.

    If multiple resources have the same base Terraform name, disambiguate by
    appending a suffix derived from the resource's unique identifier (ARN/ID).

    Args:
        resources: List of resources to process (modified in place)
    """
    # Group resources by their base Terraform name
    name_groups: Dict[str, List[TrackedResource]] = defaultdict(list)
    for resource in resources:
        base_name = resource.get_terraform_name()
        name_groups[base_name].append(resource)

    # For groups with duplicates, disambiguate
    for base_name, group in name_groups.items():
        if len(group) <= 1:
            continue

        # Multiple resources with same name - need to disambiguate
        for i, resource in enumerate(group):
            # Try to extract a unique suffix from ARN or other identifiers
            suffix = _extract_unique_suffix(resource, i)
            unique_name = f"{base_name}_{suffix}"

            # Sanitize the new name
            unique_name = re.sub(r"[^a-z0-9_]", "_", unique_name.lower())
            unique_name = re.sub(r"_+", "_", unique_name)
            unique_name = unique_name.strip("_")

            resource.terraform_name = unique_name


def _extract_unique_suffix(resource: TrackedResource, index: int) -> str:
    """Extract a unique suffix for disambiguating resource names.

    Tries to use meaningful identifiers from the resource before falling back
    to a numeric index.

    Args:
        resource: The resource to extract suffix from
        index: Fallback numeric index

    Returns:
        A suffix string to make the name unique
    """
    # Try to extract VPC ID for security groups
    if "ec2:security-group" in resource.resource_type:
        vpc_id = resource.raw_config.get("VpcId", "")
        if vpc_id:
            # Extract last part of VPC ID (e.g., "vpc-abc123" -> "abc123")
            match = re.search(r"vpc-([a-z0-9]+)$", vpc_id)
            if match:
                return match.group(1)[:8]

    # Try to extract from ARN
    if resource.arn:
        # Get the last part of the ARN after the last / or :
        parts = re.split(r"[/:]", resource.arn)
        if parts:
            last_part = parts[-1]
            # If it looks like an ID, use it
            if re.match(r"^[a-z]+-[a-z0-9]+$", last_part):
                return last_part.split("-")[-1][:8]
            # Otherwise use a hash of the last part
            if len(last_part) > 4:
                return last_part[:8]

    # Fallback to numeric index
    return str(index + 1)


def categorize_layers(state: GenerationState) -> Dict[str, Any]:
    """Group resources into ordered layers.

    Resources are grouped by their layer (1-11) for generation order:
    1. Network (VPCs, subnets, gateways)
    2. Security (security groups)
    3. IAM (roles, policies)
    ...and so on

    Args:
        state: Current state with resources list

    Returns:
        Dict with layers: List[Layer] - Ordered list of resource layers
    """
    resources: List[TrackedResource] = state["resources"]

    # Ensure all resources have unique Terraform names before categorizing
    _ensure_unique_terraform_names(resources)

    layer_resources: Dict[LayerOrder, List[TrackedResource]] = defaultdict(list)

    for resource in resources:
        layer = RESOURCE_TYPE_TO_LAYER.get(resource.resource_type, LayerOrder.COMPUTE)
        layer_resources[layer].append(resource)

    # Build layers dict and layer_order list for generate_layer node
    layers_dict: Dict[str, List[TrackedResource]] = {}
    layer_order_list: List[str] = []

    for layer_ord in sorted(layer_resources.keys()):
        layer_name = LAYER_NAMES.get(layer_ord, f"Layer {layer_ord}")
        layers_dict[layer_name] = layer_resources[layer_ord]
        layer_order_list.append(layer_name)

    return {
        "layers": layers_dict,
        "layer_order": layer_order_list,
        "total_resources": len(resources),
    }
