import datetime
import json

import ollama
import requests

TOOL_GREY = "\033[90m"    # dark grey for tool calls
THINK_GREY = "\033[2;37m" # dim light grey for thinking
RESET = "\033[0m"

BASE_URL = "http://raspberrypi4.tailad9f80.ts.net:8502"

SYSTEM_PROMPT = """\
You are Penny, a personal budget assistant. You help the user check their budgets, transactions, and spending summaries.

TOOLS:
- get_current_date(): Get today's date, month, and year.
- get_summary(month, year): Get budget vs actual spending for a month.
- get_budget(month, year): Get budget allocations for a month.
- get_transactions(month, year): Get transactions for a month.
- run_query(sql): Run a read-only SQL SELECT on the budget database.

RULES:
- Only call tools when the user asks about budgets, spending, transactions, or the date/time. For greetings, casual chat, or general questions, just reply normally without calling any tool.
- Do NOT guess or make up numbers. Always call a tool to get real data.
- Use ₹ for currency (never INR or Rs). Use Indian comma format: ₹1,23,456.00
- Keep answers short. Summarize tool results in 1-3 sentences.
- month is an integer 1-12, year is a 4-digit integer like 2025 or 2026.
- Use get_current_date to find today's date when the user says "this month", "today", etc.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_summary",
            "description": "Returns a budget vs actual spending summary per category for a given month and year. Includes a totals row at the end. All amounts are formatted in INR (₹).",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Month number (1-12)"},
                    "year": {"type": "integer", "description": "Full year, e.g. 2025"},
                },
                "required": ["month", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget",
            "description": "Return budget allocations for each category for a given month and year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Month number (1-12)"},
                    "year": {"type": "integer", "description": "Full year, e.g. 2025"},
                },
                "required": ["month", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Return all transactions (expenditures) for a given month and year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Month number (1-12)"},
                    "year": {"type": "integer", "description": "Full year, e.g. 2025"},
                },
                "required": ["month", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Get today's date. Call this when the user says 'this month', 'today', 'current month', etc.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_query",
            "description": (
                "Execute a read-only SQL SELECT query against the budget database and return results as a list of objects.\n\n"
                "Use this tool when you need to answer questions that require cross-month analysis, aggregations, trends, "
                "filtering, or any query that the single-month lookup tools cannot satisfy on their own.\n\n"
                "Database schema:\n\n"
                "budget_set\n"
                "- id INTEGER PRIMARY KEY\n"
                "- MonthYear TEXT  Budget month in \"MM/YY\" format (e.g. \"01/25\" for Jan 2025)\n"
                "- Category TEXT  Spending category name (e.g. \"Groceries\", \"Dining\", \"Rent\")\n"
                "- Budget REAL  Allocated budget amount in INR\n\n"
                "budget_tracker\n"
                "- id INTEGER PRIMARY KEY\n"
                "- Date TEXT  Transaction date as \"DD/MM/YYYY\"\n"
                "- Description TEXT  Free-text description of the transaction\n"
                "- Category TEXT  Spending category (matches categories in budget_set)\n"
                "- Expenditure REAL  Amount spent in INR\n"
                "- Year INTEGER  4-digit year (e.g. 2025)\n"
                "- Month INTEGER  Month number 1-12\n"
                "- Day INTEGER  Day of month 1-31\n\n"
                "Example queries:\n\n"
                "-- Total spending per category for a full year\n"
                "SELECT Category, ROUND(SUM(Expenditure), 2) AS total FROM budget_tracker WHERE Year = 2025 GROUP BY Category ORDER BY total DESC\n\n"
                "-- Monthly spending trend\n"
                "SELECT Month, ROUND(SUM(Expenditure), 2) AS total FROM budget_tracker WHERE Year = 2025 GROUP BY Month ORDER BY Month\n\n"
                "-- Search transactions by description keyword\n"
                "SELECT * FROM budget_tracker WHERE Description LIKE '%Swiggy%' ORDER BY Year DESC, Month DESC, Day DESC\n\n"
                "-- Top 10 largest single transactions\n"
                "SELECT Date, Description, Category, Expenditure FROM budget_tracker ORDER BY Expenditure DESC LIMIT 10\n\n"
                "Rules:\n"
                "- Only SELECT statements are permitted; INSERT, UPDATE, DELETE, DROP will be rejected.\n"
                "- Always use Year and Month integer columns for date filtering — do not parse the Date text column.\n"
                "- MonthYear in budget_set uses \"MM/YY\" format; join to budget_tracker using printf('%02d/%02d', Month, Year % 100)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "A SELECT SQL query to run"},
                },
                "required": ["sql"],
            },
        },
    },
]


def call_tool(name, args):
    """Dispatch a tool call to the appropriate API endpoint."""
    try:
        if name == "get_summary":
            month = str(args["month"]).zfill(2)
            resp = requests.get(f"{BASE_URL}/summary/{month}/{args['year']}")
        elif name == "get_budget":
            month = str(args["month"]).zfill(2)
            resp = requests.get(f"{BASE_URL}/budget/{month}/{args['year']}")
        elif name == "get_transactions":
            month = str(args["month"]).zfill(2)
            resp = requests.get(f"{BASE_URL}/transactions/{month}/{args['year']}")
        elif name == "get_current_date":
            now = datetime.datetime.now()
            return json.dumps({"date": now.strftime("%Y-%m-%d"), "month": now.month, "year": now.year})
        elif name == "run_query":
            resp = requests.post(f"{BASE_URL}/query", json={"sql": args["sql"]})
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

        return json.dumps(resp.json())
    except requests.RequestException as e:
        return json.dumps({"error": str(e)})


def stream_response(messages):
    accumulated_thinking = ""
    accumulated_content = ""
    tool_calls = None
    thinking_started = False
    content_started = False

    stream = ollama.chat(
        model="qwen3.5:4b",
        messages=messages,
        tools=tools,
        think=True,
        stream=True,
    )

    for chunk in stream:
        msg = chunk.message

        if msg.thinking:
            if not thinking_started:
                print(f"\n{THINK_GREY}[thinking] ", end="", flush=True)
                thinking_started = True
            print(msg.thinking, end="", flush=True)
            accumulated_thinking += msg.thinking

        if msg.content:
            if not content_started:
                if thinking_started:
                    print(RESET)  # end thinking color + newline
                content_started = True
            print(msg.content, end="", flush=True)
            accumulated_content += msg.content

        if msg.tool_calls:
            tool_calls = msg.tool_calls

    if content_started:
        print()
    elif thinking_started:
        print(RESET)

    return {
        "role": "assistant",
        "content": accumulated_content,
        "thinking": accumulated_thinking or None,
        "tool_calls": tool_calls,
    }


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("Penny — Budget Assistant (qwen3.5:4b) — Ctrl+C or Ctrl+D to exit")

    while True:
        try:
            user_input = input("\n> ")
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input.strip():
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            msg = stream_response(messages)

            if not msg["tool_calls"]:
                messages.append(msg)
                break

            for tool_call in msg["tool_calls"]:
                name = tool_call.function.name
                args = tool_call.function.arguments
                print(f"{TOOL_GREY}  [calling {name}({args})]{RESET}")
                result = call_tool(name, args)
                print(f"{TOOL_GREY}  [result: {result}]{RESET}")

            messages.append(msg)
            messages.append({"role": "tool", "content": result})


if __name__ == "__main__":
    main()
