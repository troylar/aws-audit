"""LangGraph agent for IaC generation (Terraform and CDK)."""

from typing import Literal

from langgraph.graph import END, StateGraph

from .nodes.build_resource_map import build_resource_map
from .nodes.categorize_layers import categorize_layers
from .nodes.compare_inventory import compare_inventory
from .nodes.evaluate_guardrails import evaluate_guardrails
from .nodes.extract_lambda import extract_lambda_code
from .nodes.generate_layer import generate_layer
from .nodes.parse_inventory import parse_inventory
from .nodes.validate_cdk import cdk_synth, npm_build
from .nodes.validate_terraform import terraform_init, terraform_validate
from .state import GenerationState


def should_continue_after_guardrails(
    state: GenerationState,
) -> Literal["categorize_layers", "end"]:
    """Check if generation should continue after guardrails evaluation.

    If guardrails_blocked is True, stop generation early.
    """
    if state.get("guardrails_blocked", False):
        return "end"
    return "categorize_layers"


def should_continue_generating(
    state: GenerationState,
) -> Literal["generate_layer", "compare_inventory"]:
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
    3. evaluate_guardrails - Check resources against policy (optional)
    4. categorize_layers - Group resources by layer
    5. extract_lambda - Extract Lambda code to files
    6. generate_layer - Generate Terraform for each layer (loops)
    7. compare_inventory - Compare inventory against generated code (AI)
    8. terraform_init - Run terraform init
    9. terraform_validate - Run terraform validate

    Returns:
        Configured StateGraph ready to compile
    """
    graph = StateGraph(GenerationState)

    graph.add_node("parse_inventory", parse_inventory)
    graph.add_node("build_resource_map", build_resource_map)
    graph.add_node("evaluate_guardrails", evaluate_guardrails)
    graph.add_node("categorize_layers", categorize_layers)
    graph.add_node("extract_lambda", extract_lambda_code)
    graph.add_node("generate_layer", generate_layer)
    graph.add_node("compare_inventory", compare_inventory)
    graph.add_node("terraform_init", terraform_init)
    graph.add_node("terraform_validate", terraform_validate)

    graph.set_entry_point("parse_inventory")
    graph.add_edge("parse_inventory", "build_resource_map")
    graph.add_edge("build_resource_map", "evaluate_guardrails")

    graph.add_conditional_edges(
        "evaluate_guardrails",
        should_continue_after_guardrails,
        {
            "categorize_layers": "categorize_layers",
            "end": END,
        },
    )

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


def create_cdk_graph() -> StateGraph:
    """Create the LangGraph StateGraph for CDK generation.

    Workflow:
    1. parse_inventory - Load snapshot and extract resources
    2. build_resource_map - Create AWS ID -> CDK ref mapping
    3. evaluate_guardrails - Check resources against policy (optional)
    4. categorize_layers - Group resources by layer
    5. extract_lambda - Extract Lambda code to files
    6. generate_layer - Generate CDK stacks for each layer (loops)
    7. compare_inventory - Compare inventory against generated code (AI)
    8. npm_build - Run npm install and build (TypeScript only)
    9. cdk_synth - Run cdk synth to validate

    Returns:
        Configured StateGraph ready to compile
    """
    graph = StateGraph(GenerationState)

    graph.add_node("parse_inventory", parse_inventory)
    graph.add_node("build_resource_map", build_resource_map)
    graph.add_node("evaluate_guardrails", evaluate_guardrails)
    graph.add_node("categorize_layers", categorize_layers)
    graph.add_node("extract_lambda", extract_lambda_code)
    graph.add_node("generate_layer", generate_layer)
    graph.add_node("compare_inventory", compare_inventory)
    graph.add_node("npm_build", npm_build)
    graph.add_node("cdk_synth", cdk_synth)

    graph.set_entry_point("parse_inventory")
    graph.add_edge("parse_inventory", "build_resource_map")
    graph.add_edge("build_resource_map", "evaluate_guardrails")

    graph.add_conditional_edges(
        "evaluate_guardrails",
        should_continue_after_guardrails,
        {
            "categorize_layers": "categorize_layers",
            "end": END,
        },
    )

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

    graph.add_edge("compare_inventory", "npm_build")
    graph.add_edge("npm_build", "cdk_synth")
    graph.add_edge("cdk_synth", END)

    return graph


def compile_cdk_agent():
    """Compile the CDK generation agent.

    Returns:
        Compiled LangGraph agent ready to invoke
    """
    graph = create_cdk_graph()
    return graph.compile()
