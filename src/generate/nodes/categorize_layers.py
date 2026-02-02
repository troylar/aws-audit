"""Categorize layers node for LangGraph workflow."""

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
