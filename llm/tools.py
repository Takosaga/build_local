# Tool definitions in OpenAI function-calling format.
# Sent with every LLM request so the model knows what actions are available.

SETUP_TOOLS = {
    "create_company", "enable_modules", "setup_chart_of_accounts",
    "create_item", "create_items_bulk", "create_customer", "create_customers_bulk",
    "create_supplier", "set_tax_rate",
}

WRITE_TOOLS = {"create_invoice", "create_purchase_order", "update_item_price"}

TOOL_NAMES = SETUP_TOOLS | WRITE_TOOLS | {
    "get_sales_summary", "get_top_customers", "get_inventory_status",
    "get_low_stock_items", "get_customer_history", "draft_content",
}

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_company",
            "description": "Create the company record in ERPNext with name, currency and fiscal year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Legal company name"},
                    "currency": {"type": "string", "description": "ISO currency code, e.g. USD"},
                    "fiscal_year_start": {"type": "string", "description": "Month-day, e.g. 01-01"},
                    "country": {"type": "string", "description": "Full country name, e.g. United States"},
                },
                "required": ["name", "currency", "fiscal_year_start", "country"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_modules",
            "description": "Enable a list of ERPNext modules for the company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Module names, e.g. ['Selling', 'Stock', 'Accounts']",
                    }
                },
                "required": ["modules"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "setup_chart_of_accounts",
            "description": "Configure the chart of accounts for the company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "business_type": {"type": "string"},
                },
                "required": ["company", "business_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_tax_rate",
            "description": "Set the default tax rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rate": {"type": "number", "description": "Tax percentage, e.g. 20.0"},
                    "account_name": {"type": "string", "description": "Tax account name, e.g. 'VAT 20%'"},
                },
                "required": ["rate", "account_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "Create a single customer record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customers_bulk",
            "description": "Create multiple customer records at once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "phone": {"type": "string"},
                                "email": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    }
                },
                "required": ["customers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_item",
            "description": "Create a single product or service item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "item_group": {"type": "string"},
                },
                "required": ["name", "price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_items_bulk",
            "description": "Create multiple items at once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "price": {"type": "number"},
                                "item_group": {"type": "string"},
                            },
                            "required": ["name", "price"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_supplier",
            "description": "Create a supplier record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Get total sales for a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "to_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["from_date", "to_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_customers",
            "description": "Get the top customers by total spend.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of customers to return (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_status",
            "description": "Get current stock levels. Omit item_code to get all items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_items",
            "description": "Get items below a stock threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "integer", "description": "Stock level below which to flag items"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_history",
            "description": "Get order history for a specific customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                },
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invoice",
            "description": "Create a sales invoice. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_code": {"type": "string"},
                                "qty": {"type": "number"},
                                "rate": {"type": "number"},
                            },
                            "required": ["item_code", "qty", "rate"],
                        },
                    },
                },
                "required": ["customer", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_order",
            "description": "Create a purchase order. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_code": {"type": "string"},
                                "qty": {"type": "number"},
                                "rate": {"type": "number"},
                            },
                            "required": ["item_code", "qty", "rate"],
                        },
                    },
                },
                "required": ["supplier", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_item_price",
            "description": "Update the price of an item. Only call after user has confirmed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_code": {"type": "string"},
                    "new_price": {"type": "number"},
                },
                "required": ["item_code", "new_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_content",
            "description": "Generate written content such as emails, product descriptions, or announcements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content_type": {
                        "type": "string",
                        "enum": ["email", "product_description", "announcement"],
                    },
                    "context": {"type": "string", "description": "Details to include in the content"},
                },
                "required": ["content_type", "context"],
            },
        },
    },
]


def get_all_tools() -> list[dict]:
    return _TOOL_DEFINITIONS


def get_setup_tools() -> list[dict]:
    return [t for t in _TOOL_DEFINITIONS if t["function"]["name"] in SETUP_TOOLS]


def get_ongoing_tools() -> list[dict]:
    return [t for t in _TOOL_DEFINITIONS if t["function"]["name"] not in SETUP_TOOLS]
