from llm.tools import get_all_tools, TOOL_NAMES


def test_all_tools_are_valid_openai_schema():
    tools = get_all_tools()
    assert len(tools) > 0
    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_tool_names_match_definitions():
    tools = get_all_tools()
    defined_names = {t["function"]["name"] for t in tools}
    for name in TOOL_NAMES:
        assert name in defined_names, f"Tool {name} in TOOL_NAMES but not in get_all_tools()"


def test_write_tools_are_marked():
    from llm.tools import WRITE_TOOLS
    assert "create_invoice" in WRITE_TOOLS
    assert "create_purchase_order" in WRITE_TOOLS
    assert "update_item_price" in WRITE_TOOLS
    assert "get_sales_summary" not in WRITE_TOOLS


def test_setup_tools_are_marked():
    from llm.tools import SETUP_TOOLS
    assert "create_company" in SETUP_TOOLS
    assert "enable_modules" in SETUP_TOOLS
    assert "create_invoice" not in SETUP_TOOLS
