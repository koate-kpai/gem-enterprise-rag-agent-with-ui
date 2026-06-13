# app.py

import streamlit as st
import uuid
from graph_agent import get_agent_executor  # updated import

# Page setup
st.set_page_config(page_title="Corporate AI Agent", page_icon="🤖", layout="centered")
st.title("🤖 Enterprise LangGraph Assistant")
st.caption("Connected to: Web Search, Employee SQLite DB, System Clock, Math Engine")

# ------------------ Session State ------------------
# Persist the agent and its config across reruns
if "agent_executor" not in st.session_state:
    agent, config, tools = get_agent_executor()
    st.session_state.agent_executor = agent
    st.session_state.agent_config = config
    st.session_state.tools = tools
    st.session_state.thread_id = config["configurable"]["thread_id"]

# Chat history for the UI
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------ Render chat history ------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------ Handle user input ------------------
if prompt := st.chat_input("Ask me anything..."):
    # Add user message to history and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Now call the agent and stream the response
    with st.chat_message("assistant"):
        # Placeholder for the streaming response
        response_placeholder = st.empty()
        full_response = ""
        tool_icons_shown = set()  # avoid duplicate icons for the same tool call

        # Stream the agent
        for event in st.session_state.agent_executor.stream(
            {"messages": [("user", prompt)]}, config=st.session_state.agent_config
        ):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    last_msg = node_data["messages"][-1]
                    # If it's an AIMessage
                    from langchain_core.messages import AIMessage

                    if isinstance(last_msg, AIMessage):
                        if last_msg.tool_calls:
                            # Show tool calls as a nicely formatted text
                            for tc in last_msg.tool_calls:
                                tool_name = tc["name"]
                                # Only show each tool call once
                                call_id = tc.get("id")
                                if call_id not in tool_icons_shown:
                                    tool_icons_shown.add(call_id)
                                    with st.chat_message("assistant"):
                                        st.caption(f"🔧 Using **{tool_name}**")
                        elif last_msg.content:
                            # Final answer – accumulate and display
                            full_response += last_msg.content
                            response_placeholder.markdown(full_response)

        # If we never got a final answer, show an error
        if not full_response:
            full_response = "I'm sorry, I couldn't process that request."
            response_placeholder.markdown(full_response)

        # Save the final assistant response to history
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )
