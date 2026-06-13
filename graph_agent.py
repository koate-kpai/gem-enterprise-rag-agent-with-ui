# graph_agent.py

import os
import sys
import sqlite3
import uuid
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# 🔑 Guard: ensure API key is present
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# ==========================================
# 🛠️ TOOL DEFINITIONS
# ==========================================

# Instantiate the search tool once at module level (efficiency)
_search_engine = DuckDuckGoSearchRun()


@tool
def get_system_time(format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Returns the current date and time from the system clock."""
    return datetime.now().strftime(format_string)


@tool
def calculate_multiplication(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


@tool
def web_search(query: str) -> str:
    """Search the web for current events, news, or general information."""
    return _search_engine.invoke(query)


# --- SQLite Employee Database ---
_conn = sqlite3.connect(":memory:", check_same_thread=False)
_conn.execute(
    "CREATE TABLE employees (id INT, name TEXT, department TEXT, location TEXT)"
)
_conn.execute(
    "INSERT INTO employees VALUES (1, 'Alice Smith', 'Engineering', 'New York')"
)
_conn.execute("INSERT INTO employees VALUES (2, 'Bob Jones', 'Marketing', 'London')")
_conn.execute("INSERT INTO employees VALUES (3, 'Charlie Brown', 'HR', 'Berlin')")
_conn.commit()


@tool
def query_employee_database(sql_query: str) -> str:
    """Run a SQL query against the employee database. Use only SELECT statements.
    The table 'employees' has columns: id, name, department, location.
    Example: SELECT name, location FROM employees WHERE department = 'Engineering'
    """
    try:
        cursor = _conn.execute(sql_query)
        rows = cursor.fetchall()
        if not rows:
            return "No results found."
        return "\n".join([", ".join(map(str, row)) for row in rows])
    except Exception as e:
        return f"Error: {str(e)}"


# ==========================================
# 🧠 AGENT ORCHESTRATION
# ==========================================


def run_agent(verbose=True, conversation_mode=False):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    tools = [
        get_system_time,
        calculate_multiplication,
        web_search,
        query_employee_database,
    ]

    # Use MemorySaver for proper LangGraph persistence
    memory = MemorySaver()

    # Modern agent creation (LangChain v0.3+)
    agent_executor = create_agent(llm, tools, checkpointer=memory)

    # Unique thread ID per session to avoid memory leaks between runs
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    if conversation_mode:
        print("🤖 Multi-turn Agent Chat (type 'exit' to stop)\n")
        while True:
            user_input = input("👤 You: ")
            if user_input.lower() in ("exit", "quit"):
                break

            print("\n🧠 Agent thinking...")
            final_answer = ""

            # Stream using persistent memory
            for event in agent_executor.stream(
                {"messages": [("user", user_input)]}, config=config
            ):
                for node_name, node_data in event.items():
                    if "messages" in node_data:
                        last_msg = node_data["messages"][-1]
                        # Robust final answer extraction: look for AIMessage with content
                        if isinstance(last_msg, AIMessage):
                            if last_msg.tool_calls:
                                if verbose:
                                    print(
                                        f"   🔧 Using tool: {last_msg.tool_calls[0]['name']}"
                                    )
                            elif last_msg.content:
                                final_answer = last_msg.content

            if not final_answer:
                final_answer = "I'm sorry, I couldn't generate a response."
            print(f"🤖 Agent: {final_answer}")
            print("-" * 50)

    else:
        # Single query mode (Demo)
        question = input("👤 Enter your complex query: ")
        print("\n🧠 Processing Graph State...\n")

        final_answer = ""
        for event in agent_executor.stream(
            {"messages": [("user", question)]}, config=config
        ):
            for node_name, node_data in event.items():
                if verbose:
                    print(f"🧠 [{node_name}]")
                if "messages" in node_data:
                    last_msg = node_data["messages"][-1]
                    if isinstance(last_msg, AIMessage):
                        if last_msg.tool_calls:
                            if verbose:
                                print(f"   🔧 Tool: {last_msg.tool_calls[0]['name']}")
                        elif last_msg.content:
                            final_answer = last_msg.content
                if verbose:
                    print("-" * 40)

        if not final_answer:
            final_answer = "I'm sorry, I couldn't generate a response."
        print(f"\n🤖 Final Answer: {final_answer}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if mode == "chat":
        run_agent(verbose=True, conversation_mode=True)
    else:
        run_agent(verbose=True, conversation_mode=False)


def get_agent_executor():
    """Create and return an agent executor ready for streaming conversations."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    tools = [
        get_system_time,
        calculate_multiplication,
        web_search,
        query_employee_database,
    ]
    memory = MemorySaver()
    agent_executor = create_agent(llm, tools, checkpointer=memory)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    return agent_executor, config, tools
