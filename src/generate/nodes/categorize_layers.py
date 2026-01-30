"""Categorize layers node for LangGraph workflow."""

from collections import defaultdict
from typing import Any, Dict, List

from ...models.generation import Layer, TrackedResource
from ..layers import RESOURCE_TYPE_TO_LAYER, LayerOrder, LayerStatus
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

    layers: List[Layer] = []
    for layer_order in sorted(layer_resources.keys()):
        layer = Layer(
            order=layer_order,
            name=LAYER_NAMES.get(layer_order, f"Layer {layer_order}"),
            resources=layer_resources[layer_order],
            status=LayerStatus.PENDING,
        )
        layers.append(layer)

    return {"layers": layers}
