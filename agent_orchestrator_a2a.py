# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

import httpx
from a2a.client import A2ACardResolver
from agent_framework.a2a import A2AAgent

"""
Agent2Agent (A2A) Protocol Integration Sample

This sample demonstrates how to connect to and communicate with external agents using
the A2A protocol. A2A is a standardized communication protocol that enables interoperability
between different agent systems, allowing agents built with different frameworks and
technologies to communicate seamlessly.

For more information about the A2A protocol specification, visit: https://a2a-protocol.org/latest/

Key concepts demonstrated:
- Discovering A2A-compliant agents using AgentCard resolution
- Creating A2AAgent instances to wrap external A2A endpoints
- Converting Agent Framework messages to A2A protocol format
- Handling A2A responses (Messages and Tasks) back to framework types

To run this sample:
1. Set the A2A_AGENT_HOST environment variable to point to an A2A-compliant agent endpoint
   Example: export A2A_AGENT_HOST="https://your-a2a-agent.example.com"
2. Ensure the target agent exposes its AgentCard at /.well-known/agent.json
3. Run: uv run python agent_with_a2a.py

The sample will:
- Connect to the specified A2A agent endpoint
- Retrieve and parse the agent's capabilities via its AgentCard
- Send a message using the A2A protocol
- Display the agent's response

Visit the README.md for more details on setting up and running A2A agents.
"""


async def main():
    """Demonstrates orchestrating multiple A2A agents: SQL Foundry + Python Tool."""
    # Agent endpoints
    sql_agent_url = "http://localhost:10008"  # SQL Foundry Agent
    python_tool_url = "http://localhost:10009"  # Python Tool Agent

    print("=" * 80)
    print("Multi-Agent Orchestration: Bridge Engineering Data + Visualization")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180.0) as http_client:

        # ========== STEP 1: Connect to SQL Foundry Agent ==========
        print(f"\n📊 STEP 1: Connecting to SQL Foundry Agent at {sql_agent_url}")
        sql_resolver = A2ACardResolver(httpx_client=http_client, base_url=sql_agent_url)
        sql_card = await sql_resolver.get_agent_card(relative_card_path="/.well-known/agent.json")
        print(f"   ✅ Found: {sql_card.name}")

        sql_agent = A2AAgent(
            name=sql_card.name,
            description=sql_card.description,
            agent_card=sql_card,
            url=sql_agent_url,
        )

        # ========== STEP 2: Query bridge data from SQL Agent ==========
        print(f"\n🔍 STEP 2: Querying bridge span data...")
        sql_query = "Show me the span length for all spans in Bridge 1001"
        print(f"   Query: '{sql_query}'")

        sql_response = await sql_agent.run(sql_query)

        # Extract SQL response
        sql_result_text = ""
        if hasattr(sql_response, "raw_representation") and sql_response.raw_representation:
            for task in sql_response.raw_representation:
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            if hasattr(part, "root") and hasattr(part.root, "text"):
                                sql_result_text += part.root.text + "\n"

        print(f"\n   SQL Agent Response:")
        print("   " + "-" * 70)
        print("   " + sql_result_text.strip().replace("\n", "\n   "))
        print("   " + "-" * 70)

        # ========== STEP 3: Connect to Python Tool Agent ==========
        print(f"\n📈 STEP 3: Connecting to Python Tool Agent at {python_tool_url}")
        python_resolver = A2ACardResolver(httpx_client=http_client, base_url=python_tool_url)
        python_card = await python_resolver.get_agent_card(relative_card_path="/.well-known/agent.json")
        print(f"   ✅ Found: {python_card.name}")

        python_agent = A2AAgent(
            name=python_card.name,
            description=python_card.description,
            agent_card=python_card,
            url=python_tool_url,
        )

        # ========== STEP 4: Create visualization from SQL data ==========
        print(f"\n🎨 STEP 4: Creating visualization from SQL data...")
        viz_query = f"""
Based on this bridge span data, create a bar chart visualization:

{sql_result_text}

Create a bar chart showing the span length for each span. Label the x-axis as "Span Number" and y-axis as "Length (ft)".
"""
        print(f"   Sending data to Python Tool Agent for visualization...")

        python_response = await python_agent.run(viz_query)

        # Extract Python Tool response
        print(f"\n   Python Tool Agent Response:")
        print("   " + "-" * 70)
        if hasattr(python_response, "raw_representation") and python_response.raw_representation:
            for task in python_response.raw_representation:
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            if hasattr(part, "root") and hasattr(part.root, "text"):
                                print("   " + part.root.text.replace("\n", "\n   "))
        print("   " + "-" * 70)

        # ========== SUMMARY ==========
        print("\n" + "=" * 80)
        print("✅ Multi-Agent Orchestration Complete!")
        print("=" * 80)
        print(f"1. SQL Foundry Agent retrieved bridge span data")
        print(f"2. Python Tool Agent created visualization from the data")
        print(f"3. Both agents communicated via A2A protocol")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
