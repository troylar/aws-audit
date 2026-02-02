"""LangGraph agent for Terraform generation."""

from typing import Literal

from langgraph.graph import END, StateGraph

from .nodes.build_resource_map import build_resource_map
from .nodes.categorize_layers import categorize_layers
from .nodes.compare_inventory import compare_inventory
from .nodes.extract_lambda import extract_lambda_code
from .nodes.generate_layer import generate_layer
from .nodes.parse_inventory import parse_inventory
from .nodes.validate_terraform import terraform_init, terraform_validate
from .state import GenerationState


def should_continue_generating(state: GenerationState) -> Literal["generate_layer", "compare_inventory"]:
    """Check if there are more layers to generate."""
    state.get("layers", {})
    layer_order = state.get("layer_order", [])
    current_index = state.get("current_layer_index", 0)

    if current_index < len(layer_order):
        return "generate_layer"
    return "compare_inventory"


def create_terraform_graph() -> StateGraph:
    """Create the LangGraph StateGraph for Terraform generation.

    Workflow:
    1. parse_inventory - Load snapshot and extract resources
    2. build_resource_map - Create AWS ID -> Terraform ref mapping
    3. categorize_layers - Group resources by layer
    4. extract_lambda - Extract Lambda code to files
    5. generate_layer - Generate Terraform for each layer (loops)
    6. compare_inventory - Compare inventory against generated code (AI)
    7. terraform_init - Run terraform init
    8. terraform_validate - Run terraform validate

    Returns:
        Configured StateGraph ready to compile
    """
    graph = StateGraph(GenerationState)

    graph.add_node("parse_inventory", parse_inventory)
    graph.add_node("build_resource_map", build_resource_map)
    graph.add_node("categorize_layers", categorize_layers)
    graph.add_node("extract_lambda", extract_lambda_code)
    graph.add_node("generate_layer", generate_layer)
    graph.add_node("compare_inventory", compare_inventory)
    graph.add_node("terraform_init", terraform_init)
    graph.add_node("terraform_validate", terraform_validate)

    graph.set_entry_point("parse_inventory")
    graph.add_edge("parse_inventory", "build_resource_map")
    graph.add_edge("build_resource_map", "categorize_layers")
    graph.add_edge("categorize_layers", "extract_lambda")
    graph.add_edge("extract_lambda", "generate_layer")

    graph.add_conditional_edges(
        "generate_layer",
        should_continue_generating,
        {
            "generate_layer": "generate_layer",
            "compare_inventory": "compare_inventory",
        },
    )

    graph.add_edge("compare_inventory", "terraform_init")
    graph.add_edge("terraform_init", "terraform_validate")
    graph.add_edge("terraform_validate", END)

    return graph


def compile_terraform_agent():
    """Compile the Terraform generation agent.

    Returns:
        Compiled LangGraph agent ready to invoke
    """
    graph = create_terraform_graph()
    return graph.compile()
