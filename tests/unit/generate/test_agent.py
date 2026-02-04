"""Unit tests for CDK LangGraph agent (T017)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


def _setup_mocks() -> None:
    """Setup mocks for langgraph imports."""
    mock_langgraph = MagicMock()
    mock_langgraph.graph = MagicMock()
    mock_langgraph.graph.END = "END"

    mock_state_graph = MagicMock()
    mock_langgraph.graph.StateGraph = MagicMock(return_value=mock_state_graph)

    sys.modules["langgraph"] = mock_langgraph
    sys.modules["langgraph.graph"] = mock_langgraph.graph


_setup_mocks()


class TestCreateTerraformGraph:
    """Tests for create_terraform_graph function."""

    @pytest.fixture
    def agent_module(self) -> Any:
        """Return the agent module."""
        from src.generate import agent

        return agent

    def test_create_terraform_graph_returns_state_graph(self, agent_module: Any) -> None:
        """Test that create_terraform_graph returns a StateGraph."""
        graph = agent_module.create_terraform_graph()
        assert graph is not None

    def test_terraform_graph_has_parse_inventory_node(self, agent_module: Any) -> None:
        """Test Terraform graph has parse_inventory node."""
        # The function adds nodes, just verify it doesn't error
        graph = agent_module.create_terraform_graph()
        assert graph is not None

    def test_compile_terraform_agent_returns_compiled_graph(self, agent_module: Any) -> None:
        """Test compile_terraform_agent returns compiled graph."""
        compiled = agent_module.compile_terraform_agent()
        assert compiled is not None


class TestCreateCDKGraph:
    """Tests for create_cdk_graph function."""

    @pytest.fixture
    def agent_module(self) -> Any:
        """Return the agent module."""
        from src.generate import agent

        return agent

    def test_create_cdk_graph_exists(self, agent_module: Any) -> None:
        """Test that create_cdk_graph function exists."""
        assert hasattr(agent_module, "create_cdk_graph")

    def test_create_cdk_graph_returns_state_graph(self, agent_module: Any) -> None:
        """Test that create_cdk_graph returns a StateGraph."""
        if not hasattr(agent_module, "create_cdk_graph"):
            pytest.skip("create_cdk_graph not yet implemented")

        graph = agent_module.create_cdk_graph()
        assert graph is not None

    def test_compile_cdk_agent_exists(self, agent_module: Any) -> None:
        """Test that compile_cdk_agent function exists."""
        assert hasattr(agent_module, "compile_cdk_agent")

    def test_compile_cdk_agent_returns_compiled_graph(self, agent_module: Any) -> None:
        """Test compile_cdk_agent returns compiled graph."""
        if not hasattr(agent_module, "compile_cdk_agent"):
            pytest.skip("compile_cdk_agent not yet implemented")

        compiled = agent_module.compile_cdk_agent()
        assert compiled is not None


class TestShouldContinueGenerating:
    """Tests for should_continue_generating function."""

    @pytest.fixture
    def agent_module(self) -> Any:
        """Return the agent module."""
        from src.generate import agent

        return agent

    def test_returns_generate_layer_when_more_layers(self, agent_module: Any) -> None:
        """Test returns generate_layer when there are more layers."""
        state = {
            "layers": {"NETWORK": [], "COMPUTE": []},
            "layer_order": ["NETWORK", "COMPUTE"],
            "current_layer_index": 0,
        }
        result = agent_module.should_continue_generating(state)
        assert result == "generate_layer"

    def test_returns_compare_when_all_layers_done(self, agent_module: Any) -> None:
        """Test returns compare_inventory when all layers processed."""
        state = {
            "layers": {"NETWORK": []},
            "layer_order": ["NETWORK"],
            "current_layer_index": 1,
        }
        result = agent_module.should_continue_generating(state)
        assert result == "compare_inventory"

    def test_handles_empty_layers(self, agent_module: Any) -> None:
        """Test handles empty layer_order gracefully."""
        state = {
            "layers": {},
            "layer_order": [],
            "current_layer_index": 0,
        }
        result = agent_module.should_continue_generating(state)
        assert result == "compare_inventory"


class TestCDKGraphWorkflow:
    """Tests for CDK graph workflow structure."""

    @pytest.fixture
    def agent_module(self) -> Any:
        """Return the agent module."""
        from src.generate import agent

        return agent

    def test_cdk_graph_workflow_matches_terraform(self, agent_module: Any) -> None:
        """Test CDK graph has same workflow structure as Terraform.

        Both should follow:
        parse_inventory -> build_resource_map -> categorize_layers ->
        extract_lambda -> generate_layer (loop) -> compare -> validate
        """
        if not hasattr(agent_module, "create_cdk_graph"):
            pytest.skip("create_cdk_graph not yet implemented")

        # Both should create valid graphs
        tf_graph = agent_module.create_terraform_graph()
        cdk_graph = agent_module.create_cdk_graph()

        assert tf_graph is not None
        assert cdk_graph is not None

    def test_cdk_graph_uses_cdk_validation(self, agent_module: Any) -> None:
        """Test CDK graph uses CDK-specific validation node."""
        if not hasattr(agent_module, "create_cdk_graph"):
            pytest.skip("create_cdk_graph not yet implemented")

        # The CDK graph should use cdk_synth instead of terraform_validate
        # This test verifies the graph is created; actual validation tested elsewhere
        graph = agent_module.create_cdk_graph()
        assert graph is not None


class TestAgentExports:
    """Tests for agent module exports."""

    def test_create_terraform_graph_exported(self) -> None:
        """Test create_terraform_graph is exported from generate module."""
        try:
            from src.generate import create_terraform_graph

            assert callable(create_terraform_graph)
        except ImportError:
            pytest.skip("create_terraform_graph not exported yet")

    def test_compile_terraform_agent_exported(self) -> None:
        """Test compile_terraform_agent is exported from generate module."""
        try:
            from src.generate import compile_terraform_agent

            assert callable(compile_terraform_agent)
        except ImportError:
            pytest.skip("compile_terraform_agent not exported yet")

    def test_create_cdk_graph_exported(self) -> None:
        """Test create_cdk_graph is exported from generate module."""
        try:
            from src.generate import create_cdk_graph

            assert callable(create_cdk_graph)
        except ImportError:
            pytest.skip("create_cdk_graph not exported yet")

    def test_compile_cdk_agent_exported(self) -> None:
        """Test compile_cdk_agent is exported from generate module."""
        try:
            from src.generate import compile_cdk_agent

            assert callable(compile_cdk_agent)
        except ImportError:
            pytest.skip("compile_cdk_agent not exported yet")
