import json
import httpx
import config
from erpnext.adapter import ERPNextAdapter
from erpnext import setup_tools, ongoing_tools


# Maps tool name → function(adapter, **kwargs) → str
_TOOL_DISPATCH: dict[str, callable] = {
    "create_company": setup_tools.create_company,
    "enable_modules": setup_tools.enable_modules,
    "setup_chart_of_accounts": setup_tools.setup_chart_of_accounts,
    "set_tax_rate": setup_tools.set_tax_rate,
    "create_customer": setup_tools.create_customer,
    "create_customers_bulk": setup_tools.create_customers_bulk,
    "create_item": setup_tools.create_item,
    "create_items_bulk": setup_tools.create_items_bulk,
    "create_supplier": setup_tools.create_supplier,
    "get_sales_summary": ongoing_tools.get_sales_summary,
    "get_top_customers": ongoing_tools.get_top_customers,
    "get_inventory_status": ongoing_tools.get_inventory_status,
    "get_low_stock_items": ongoing_tools.get_low_stock_items,
    "get_customer_history": ongoing_tools.get_customer_history,
    "create_invoice": ongoing_tools.create_invoice,
    "create_purchase_order": ongoing_tools.create_purchase_order,
    "update_item_price": ongoing_tools.update_item_price,
}

MAX_LOOP_ITERATIONS = 10


def validate_tool_call(tool_call: dict) -> bool:
    """Return True if tool_call has the required fields and valid JSON arguments."""
    try:
        fn = tool_call.get("function", {})
        if not tool_call.get("id") or not fn.get("name") or "arguments" not in fn:
            return False
        json.loads(fn["arguments"])
        return True
    except (json.JSONDecodeError, AttributeError):
        return False


def execute_tool_call(tool_call: dict, adapter: ERPNextAdapter) -> str:
    """Execute a validated tool call and return a plain-text result."""
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])

    # draft_content is handled by the LLM itself — no ERPNext call needed
    if name == "draft_content":
        return f"[Draft content request: {args.get('context', '')}]"

    fn = _TOOL_DISPATCH.get(name)
    if fn is None:
        return f"Unknown tool: {name}"

    try:
        return fn(adapter, **args)
    except Exception as e:
        return f"Tool '{name}' failed: {str(e)}"


def _call_lm_studio(messages: list[dict], tools: list[dict]) -> dict:
    body: dict = {
        "model": config.LM_STUDIO_MODEL,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{config.LM_STUDIO_URL}/v1/chat/completions",
            json=body,
        )
    resp.raise_for_status()
    return resp.json()


def run_tool_loop(
    messages: list[dict],
    tools: list[dict],
    adapter: ERPNextAdapter,
    system_prompt: str,
) -> str:
    """
    Run the LM Studio tool call loop synchronously.
    Returns the final text response from the LLM.
    """
    loop_messages = [{"role": "system", "content": system_prompt}] + messages
    # Ensure the first non-system message is a user turn — some models reject assistant-first conversations.
    non_system = [m for m in loop_messages if m["role"] != "system"]
    if not non_system or non_system[0]["role"] != "user":
        # Insert placeholder user message right after the system message
        loop_messages = loop_messages[:1] + [{"role": "user", "content": "Go ahead."}] + loop_messages[1:]

    for _ in range(MAX_LOOP_ITERATIONS):
        try:
            response = _call_lm_studio(loop_messages, tools)
        except httpx.ConnectError:
            return "The AI model isn't running. Please open LM Studio and load the model."
        except Exception as e:
            return f"Could not reach the AI model: {str(e)}"

        choice = response["choices"][0]
        finish_reason = choice.get("finish_reason", "stop")
        message = choice["message"]

        if finish_reason == "stop" or not message.get("tool_calls"):
            return message.get("content") or "I couldn't generate a response. Please try again."

        # Process tool calls
        tool_calls = message["tool_calls"]
        loop_messages.append({"role": "assistant", "tool_calls": tool_calls, "content": None})

        tool_results = []
        retry_triggered = False
        for tc in tool_calls:
            if not validate_tool_call(tc):
                # Remove the malformed assistant message before adding correction prompt,
                # so the model doesn't see tool_calls without corresponding tool results.
                loop_messages.pop()
                loop_messages.append({
                    "role": "user",
                    "content": "Your last response had an invalid tool call format. Please try again with valid JSON arguments.",
                })
                retry_triggered = True
                break
            result = execute_tool_call(tc, adapter)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        if not retry_triggered:
            loop_messages.extend(tool_results)

    return "I'm having trouble completing that request. Please try again."


def is_lm_studio_reachable() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{config.LM_STUDIO_URL}/v1/models")
        return resp.is_success
    except Exception:
        return False
