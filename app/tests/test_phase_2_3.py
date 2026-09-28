from app.agent.planner import build_investigation_plan


def test_symbol_lookup_plan():
    plan = build_investigation_plan(
        intent="symbol_lookup",
        identifiers=["UserService"],
        keywords=["defined"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert "symbol_search" in tools
    assert "repository_search" in tools


def test_reference_search_plan():
    plan = build_investigation_plan(
        intent="reference_search",
        identifiers=["process_order"],
        keywords=["called"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert tools[0] == "symbol_search"
    assert "reference_search" in tools


def test_test_discovery_plan():
    plan = build_investigation_plan(
        intent="test_discovery",
        identifiers=["authenticate"],
        keywords=["tests"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert "symbol_search" in tools
    assert "test_search" in tools


def test_configuration_plan():
    plan = build_investigation_plan(
        intent="configuration",
        identifiers=[],
        keywords=["database", "configuration"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert tools[0] == "configuration_search"
    assert "repository_search" in tools


def test_entrypoint_plan():
    plan = build_investigation_plan(
        intent="entrypoint_discovery",
        identifiers=[],
        keywords=["application", "start"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert "entrypoint_search" in tools


def test_dependency_plan_uses_available_tool():
    plan = build_investigation_plan(
        intent="dependency_search",
        identifiers=[],
        keywords=["dependencies"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert tools == ["repository_search"]


def test_architecture_plan():
    plan = build_investigation_plan(
        intent="architecture",
        identifiers=[],
        keywords=["architecture"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert tools == ["repository_search"]


def test_general_search_plan():
    plan = build_investigation_plan(
        intent="general_search",
        identifiers=[],
        keywords=["database"],
    )

    tools = [step.tool_name for step in plan.steps]

    assert tools == ["repository_search"]


def test_plan_contains_only_registered_tools():
    plan = build_investigation_plan(
        intent="reference_search",
        identifiers=["process_order"],
        keywords=["called"],
    )

    registered_tools = set(
        __import__(
            "app.agent.tools",
            fromlist=["TOOL_REGISTRY"],
        ).TOOL_REGISTRY
    )

    for step in plan.steps:
        assert step.tool_name in registered_tools


def test_plan_has_reasons():
    plan = build_investigation_plan(
        intent="symbol_lookup",
        identifiers=["UserService"],
    )

    for step in plan.steps:
        assert step.reason