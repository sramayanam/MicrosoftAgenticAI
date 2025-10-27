"""
Smart Orchestrator using Microsoft Agent Framework Sequential + Concurrent Workflows.

This orchestrator uses native workflow patterns instead of Magentic:
- Sequential workflow for SQL → Python visualization pipeline
- Concurrent workflow for parallel data gathering (SQL + Databricks)
- Direct A2A protocol for reliable file attachment handling

Architecture:
1. Query Analysis: Detect visualization, SQL, or Databricks requests
2. Sequential Workflow: SQL → Python for charts (guaranteed order)
3. Concurrent Workflow: SQL + Databricks for parallel data gathering
4. Direct A2A: Fallback for simple single-agent queries
"""

import asyncio
import base64
import os
from typing import Any

import httpx
from a2a.client import A2ACardResolver
from agent_framework import SequentialBuilder, ConcurrentBuilder
from agent_framework.a2a import A2AAgent
from dotenv import load_dotenv

# Import observability
from observability import configure_observability, get_tracer, inject_trace_context

load_dotenv()

# Configure observability for orchestrator
configure_observability(
    service_name="smart-orchestrator",
    enable_httpx_instrumentation=True  # Trace A2A agent calls
)

# Get tracer for distributed tracing
tracer = get_tracer(__name__)


class SmartOrchestrator:
    """Intelligent orchestrator using Sequential + Concurrent workflow patterns."""

    def __init__(self):
        """Initialize the smart orchestrator."""
        # Agent URLs
        self.sql_agent_url = os.getenv("SQL_AGENT_URL", "http://localhost:10008")
        self.databricks_agent_url = os.getenv("DATABRICKS_AGENT_URL", "http://localhost:10010")
        self.python_agent_url = os.getenv("PYTHON_AGENT_URL", "http://localhost:10009")

        # HTTP client for A2A communication
        self.http_client: httpx.AsyncClient | None = None

        # A2A agents
        self.sql_agent: A2AAgent | None = None
        self.databricks_agent: A2AAgent | None = None
        self.python_agent: A2AAgent | None = None

        # Workflows
        self.chart_workflow = None  # Sequential: SQL → Python
        self.data_workflow = None   # Concurrent: SQL + Databricks

    async def __aenter__(self):
        """Async context manager entry - initialize HTTP client and agents."""
        self.http_client = httpx.AsyncClient(timeout=60.0)

        print("🔗 Initializing Smart Orchestrator with Sequential + Concurrent workflows...")

        try:
            # Initialize A2A agents
            await self._initialize_agents()

            # Build workflows
            await self._build_workflows()

            print("✅ Smart orchestrator initialized\n")
            return self

        except Exception as e:
            print(f"❌ Failed to initialize orchestrator: {e}")
            if self.http_client:
                await self.http_client.aclose()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()

    async def _initialize_agents(self):
        """Initialize all A2A agents."""
        print("  Connecting to SQL Foundry Agent...")
        self.sql_agent = await self._create_a2a_agent(
            name="SQLFoundryAgent",
            url=self.sql_agent_url
        )

        print("  Connecting to Databricks Agent...")
        self.databricks_agent = await self._create_a2a_agent(
            name="DatabricksAgent",
            url=self.databricks_agent_url
        )

        print("  Connecting to Python Tool Agent...")
        self.python_agent = await self._create_a2a_agent(
            name="PythonToolAgent",
            url=self.python_agent_url
        )

    async def _create_a2a_agent(self, name: str, url: str) -> A2AAgent:
        """Create and initialize an A2A agent.

        Args:
            name: Agent name
            url: Agent endpoint URL

        Returns:
            Initialized A2AAgent
        """
        try:
            resolver = A2ACardResolver(httpx_client=self.http_client, base_url=url)
            card = await asyncio.wait_for(
                resolver.get_agent_card(relative_card_path="/.well-known/agent.json"),
                timeout=10.0
            )

            # IMPORTANT: Pass the instrumented http_client so traces propagate!
            agent = A2AAgent(
                name=card.name,
                description=card.description,
                agent_card=card,
                url=url,
                http_client=self.http_client,  # Use shared instrumented client for trace propagation
            )

            print(f"    ✅ Connected to {card.name}")
            return agent

        except asyncio.TimeoutError:
            raise RuntimeError(f"Timeout connecting to {name} at {url}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to {name} at {url}: {e}")

    async def _build_workflows(self):
        """Build Sequential and Concurrent workflows."""
        print("\n🔧 Building workflows...")

        # Sequential workflow: SQL → Python (for charts)
        print("  Building chart workflow (Sequential: SQL → Python)...")
        self.chart_workflow = (
            SequentialBuilder()
            .participants([self.sql_agent, self.python_agent])
            .build()
        ).as_agent(name="ChartWorkflow")
        print("    ✅ Chart workflow ready")

        # Concurrent workflow: SQL + Databricks (for parallel data gathering)
        print("  Building data workflow (Concurrent: SQL + Databricks)...")
        self.data_workflow = (
            ConcurrentBuilder()
            .participants([self.sql_agent, self.databricks_agent])
            .build()
        ).as_agent(name="DataWorkflow")
        print("    ✅ Data workflow ready")

    def _analyze_query(self, query: str) -> dict[str, Any]:
        """Analyze query to determine routing strategy.

        Args:
            query: User query

        Returns:
            Dictionary with routing information
        """
        query_lower = query.lower()

        # Detect query characteristics
        is_visualization = any(kw in query_lower for kw in [
            'chart', 'graph', 'plot', 'visualiz', 'bar', 'line', 'pie'
        ])
        is_databricks = any(kw in query_lower for kw in [
            'gdot', 'standard', 'material', 'databricks', 'catalog',
            'environmental', 'compliance', 'beam type', 'design parameter'
        ])
        is_sql = any(kw in query_lower for kw in [
            'bridge', 'span', 'beam', '1001', 'structural'
        ])

        # Determine routing strategy
        # Check for three-agent workflow first (most complex)
        if is_visualization and is_databricks and is_sql:
            # SQL + Databricks + Python (compare data and visualize)
            strategy = "three_agent_workflow"
            workflow = "comparison_chart"
            agents = ["SQL", "Databricks", "Python"]
        elif is_visualization and is_sql:
            # SQL + Python (chart from bridge data)
            strategy = "sequential_chart"
            workflow = "chart_workflow"
            agents = ["SQL", "Python"]
        elif is_databricks and is_sql:
            # SQL + Databricks (parallel data gathering)
            strategy = "concurrent_data"
            workflow = "data_workflow"
            agents = ["SQL", "Databricks"]
        elif is_databricks:
            # Databricks only
            strategy = "direct_databricks"
            workflow = None
            agents = ["Databricks"]
        elif is_sql:
            # SQL only
            strategy = "direct_sql"
            workflow = None
            agents = ["SQL"]
        else:
            # Default to SQL
            strategy = "direct_sql"
            workflow = None
            agents = ["SQL"]

        return {
            "strategy": strategy,
            "workflow": workflow,
            "agents": agents,
            "is_visualization": is_visualization,
            "is_databricks": is_databricks,
            "is_sql": is_sql
        }

    def _preprocess_query(self, query: str, routing_info: dict) -> str:
        """Preprocess query based on routing strategy.

        For visualization queries, strip viz keywords before sending to SQL agent.

        Args:
            query: Original user query
            routing_info: Query routing information

        Returns:
            Preprocessed query
        """
        if routing_info["is_visualization"]:
            # Strip visualization keywords for SQL agent
            cleaned_query = query
            viz_keywords = [
                'as a bar chart', 'as a chart', 'as a graph', 'as a plot',
                'visualize', 'visualization', 'create a chart', 'show chart',
                'plot this', 'graph this'
            ]
            for keyword in viz_keywords:
                cleaned_query = cleaned_query.replace(keyword, '')
            return cleaned_query.strip()

        return query

    async def run(self, user_query: str) -> dict[str, Any]:
        """Run the orchestrator on a user query.

        Args:
            user_query: User's natural language query

        Returns:
            Dictionary with results including text, images, and metadata
        """
        # Start distributed trace
        with tracer.start_as_current_span("orchestrator.run") as span:
            span.set_attribute("query", user_query)

            print(f"\n{'='*80}")
            print(f"User Query: {user_query}")
            print(f"{'='*80}\n")

            # Analyze query
            routing_info = self._analyze_query(user_query)
            span.set_attribute("strategy", routing_info['strategy'])
            span.set_attribute("workflow", routing_info['workflow'] or 'Direct A2A')
            span.set_attribute("agents", ', '.join(routing_info['agents']))

            print(f"📊 Query Analysis:")
            print(f"   Strategy: {routing_info['strategy']}")
            print(f"   Workflow: {routing_info['workflow'] or 'Direct A2A'}")
            print(f"   Agents: {', '.join(routing_info['agents'])}\n")

            # Preprocess query
            processed_query = self._preprocess_query(user_query, routing_info)
            if processed_query != user_query:
                print(f"🔧 Preprocessed query: {processed_query}\n")

            result = {
                "query": user_query,
                "routing": routing_info,
                "text": "",
                "images": [],
                "agent_responses": {}
            }

            try:
                # Route based on strategy
                if routing_info["strategy"] == "three_agent_workflow":
                    await self._run_three_agent_workflow(processed_query, user_query, result)

                elif routing_info["strategy"] == "sequential_chart":
                    await self._run_chart_workflow(processed_query, user_query, result)

                elif routing_info["strategy"] == "concurrent_data":
                    await self._run_data_workflow(user_query, result)

                elif routing_info["strategy"] == "direct_databricks":
                    await self._run_direct_agent(self.databricks_agent, user_query, result, "databricks")

                elif routing_info["strategy"] == "direct_sql":
                    await self._run_direct_agent(self.sql_agent, user_query, result, "sql")

                print(f"\n{'='*80}")
                print("✅ Orchestration Complete")
                print(f"{'='*80}\n")

                span.set_attribute("success", True)
                span.set_attribute("image_count", len(result.get("images", [])))

            except Exception as e:
                print(f"\n❌ Orchestration failed: {e}")
                import traceback
                traceback.print_exc()
                result["error"] = str(e)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))

            return result

    async def _run_three_agent_workflow(self, preprocessed_query: str, original_query: str, result: dict):
        """Run three-agent workflow: SQL + Databricks (parallel) → Python.

        Args:
            preprocessed_query: Query with viz keywords stripped
            original_query: Original user query
            result: Result dictionary to populate
        """
        print("🎨 Running Three-Agent Workflow (SQL + Databricks → Python)...\n")

        # Step 1: Get data from SQL and Databricks in parallel
        print("  Step 1: Querying SQL and Databricks agents in parallel...")
        sql_task = self.sql_agent.run(preprocessed_query)
        databricks_task = self.databricks_agent.run(preprocessed_query)

        sql_response, databricks_response = await asyncio.gather(sql_task, databricks_task)

        sql_extracted = self._extract_from_a2a_response(sql_response)
        databricks_extracted = self._extract_from_a2a_response(databricks_response)

        print(f"  ✅ SQL agent: {len(sql_extracted['text'])} chars")
        print(f"  ✅ Databricks agent: {len(databricks_extracted['text'])} chars")

        # Step 2: Combine data and send to Python for visualization
        print("  Step 2: Creating comparison visualization with Python agent...")
        combined_data = f"=== Bridge Data (SQL) ===\n{sql_extracted['text']}\n\n=== GDOT Standards (Databricks) ===\n{databricks_extracted['text']}"
        viz_prompt = f"Create a comparison visualization for this data:\n\n{combined_data}\n\nOriginal request: {original_query}"

        python_response = await self.python_agent.run(viz_prompt)
        python_extracted = self._extract_from_a2a_response(python_response)

        print(f"  ✅ Python agent completed: {len(python_extracted['images'])} image(s)")

        # Combine all results
        result["text"] = f"{combined_data}\n\nVisualization:\n{python_extracted['text']}"
        result["images"] = python_extracted["images"]
        result["agent_responses"]["sql"] = sql_extracted["text"]
        result["agent_responses"]["databricks"] = databricks_extracted["text"]
        result["agent_responses"]["python"] = python_extracted["text"]

        print("\n📊 Three-agent workflow completed:")
        print(f"   Text: {len(result['text'])} chars")
        print(f"   Images: {len(result['images'])} file(s)")

    async def _run_chart_workflow(self, preprocessed_query: str, original_query: str, result: dict):
        """Run sequential chart workflow: SQL → Python.

        Args:
            preprocessed_query: Query with viz keywords stripped
            original_query: Original user query
            result: Result dictionary to populate
        """
        with tracer.start_as_current_span("chart_workflow") as span:
            span.set_attribute("workflow.type", "sequential_chart")

            print("🎨 Running Chart Workflow (Direct A2A: SQL → Python)...\n")

            # Use Direct A2A instead of Sequential workflow to avoid ChatMessage conversion issues
            # Step 1: Get data from SQL agent
            with tracer.start_as_current_span("call_sql_agent") as sql_span:
                sql_span.set_attribute("agent.name", "sql_foundry")
                print("  Step 1: Querying SQL agent...")
                sql_response = await self.sql_agent.run(preprocessed_query)
                sql_extracted = self._extract_from_a2a_response(sql_response)
                sql_span.set_attribute("response.length", len(sql_extracted['text']))

            print(f"  ✅ SQL agent completed: {len(sql_extracted['text'])} chars")

            # Step 2: Send SQL data to Python agent for visualization
            with tracer.start_as_current_span("call_python_agent") as py_span:
                py_span.set_attribute("agent.name", "python_tool")
                print("  Step 2: Creating visualization with Python agent...")
                viz_prompt = f"Create a bar chart for this data:\n\n{sql_extracted['text']}\n\nOriginal request: {original_query}"
                python_response = await self.python_agent.run(viz_prompt)
                python_extracted = self._extract_from_a2a_response(python_response)
                py_span.set_attribute("image.count", len(python_extracted['images']))

            print(f"  ✅ Python agent completed: {len(python_extracted['images'])} image(s)")

            # Combine results
            result["text"] = f"SQL Data:\n{sql_extracted['text']}\n\nVisualization:\n{python_extracted['text']}"
            result["images"] = python_extracted["images"]
            result["agent_responses"]["sql"] = sql_extracted["text"]
            result["agent_responses"]["python"] = python_extracted["text"]

            span.set_attribute("total.images", len(result['images']))

            print(f"\n📊 Chart workflow completed:")
            print(f"   Text: {len(result['text'])} chars")
            print(f"   Images: {len(result['images'])} file(s)")

    async def _run_data_workflow(self, query: str, result: dict):
        """Run concurrent data workflow: SQL + Databricks in parallel.

        Args:
            query: User query
            result: Result dictionary to populate
        """
        print("🔄 Running Parallel Data Workflow (SQL + Databricks concurrently)...\n")

        # Run both agents in parallel using asyncio.gather instead of ConcurrentBuilder
        # This avoids ChatMessage conversion issues
        sql_task = self.sql_agent.run(query)
        databricks_task = self.databricks_agent.run(query)

        sql_response, databricks_response = await asyncio.gather(sql_task, databricks_task)

        # Extract from both responses
        sql_extracted = self._extract_from_a2a_response(sql_response)
        databricks_extracted = self._extract_from_a2a_response(databricks_response)

        print(f"  ✅ SQL agent: {len(sql_extracted['text'])} chars")
        print(f"  ✅ Databricks agent: {len(databricks_extracted['text'])} chars")

        # Combine results
        result["text"] = f"=== SQL Foundry Agent ===\n{sql_extracted['text']}\n\n=== Databricks Agent ===\n{databricks_extracted['text']}"
        result["images"] = sql_extracted["images"] + databricks_extracted["images"]
        result["agent_responses"]["sql"] = sql_extracted["text"]
        result["agent_responses"]["databricks"] = databricks_extracted["text"]

        print(f"\n📊 Parallel data workflow completed:")
        print(f"   Text: {len(result['text'])} chars")
        print(f"   Images: {len(result['images'])} file(s)")

    async def _run_direct_agent(self, agent: A2AAgent, query: str, result: dict, agent_name: str):
        """Run a single agent directly using A2A protocol.

        Args:
            agent: A2A agent to run
            query: User query
            result: Result dictionary to populate
            agent_name: Agent identifier for results
        """
        # Create a span for this agent call
        with tracer.start_as_current_span(f"call_{agent_name}_agent") as span:
            span.set_attribute("agent.name", agent.name)
            span.set_attribute("query", query)

            print(f"🤖 Running {agent.name} directly...\n")

            # Run agent - trace context is automatically propagated via instrumented httpx
            response = await agent.run(query)

            # Extract text and images from A2A response
            extracted = self._extract_from_a2a_response(response)

            result["text"] = extracted["text"]
            result["images"] = extracted["images"]
            result["agent_responses"][agent_name] = extracted["text"]

            span.set_attribute("response.length", len(extracted["text"]))
            span.set_attribute("image.count", len(extracted["images"]))

            print(f"\n📊 {agent.name} completed:")
            print(f"   Text: {len(extracted['text'])} chars")
            print(f"   Images: {len(extracted['images'])} file(s)")

    def _extract_from_response(self, response) -> dict[str, Any]:
        """Extract text and images from framework workflow response.

        Args:
            response: Workflow response (AgentRunResponse)

        Returns:
            Dictionary with 'text' and 'images'
        """
        text_parts = []
        images = []

        # Check if response has messages attribute (workflow response)
        if hasattr(response, "messages"):
            for message in response.messages:
                # Extract text
                if hasattr(message, "text") and message.text:
                    text_parts.append(message.text)

                # Extract images from content
                if hasattr(message, "content") and message.content:
                    for content_item in message.content:
                        # Check for text content
                        if hasattr(content_item, "text") and content_item.text:
                            if content_item.text not in text_parts:
                                text_parts.append(content_item.text)

        # Also try raw_representation for A2A responses
        if hasattr(response, "raw_representation"):
            a2a_extracted = self._extract_from_a2a_response(response)
            if a2a_extracted["text"]:
                text_parts.append(a2a_extracted["text"])
            images.extend(a2a_extracted["images"])

        # Fallback: check if response has text attribute directly
        if not text_parts and hasattr(response, "text") and response.text:
            text_parts.append(response.text)

        return {
            "text": "\n\n".join(text_parts),
            "images": images
        }

    def _extract_from_a2a_response(self, response) -> dict[str, Any]:
        """Extract text and images from A2A response.

        Args:
            response: A2A response object

        Returns:
            Dictionary with 'text' and 'images'
        """
        text_parts = []
        images = []

        if hasattr(response, "raw_representation") and response.raw_representation:
            for task in response.raw_representation:
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            part_root = part.root if hasattr(part, "root") else part

                            # Extract text
                            if hasattr(part_root, "text") and part_root.text:
                                text_parts.append(part_root.text)

                            # Extract images (FilePart with FileWithBytes)
                            elif hasattr(part_root, "file"):
                                file_obj = part_root.file
                                if hasattr(file_obj, "bytes") and file_obj.bytes:
                                    # Decode base64 to bytes
                                    try:
                                        image_bytes = base64.b64decode(file_obj.bytes)
                                        images.append({
                                            'data': image_bytes,
                                            'mime_type': getattr(file_obj, 'mime_type', 'image/png'),
                                            'name': getattr(file_obj, 'name', 'image.png')
                                        })
                                    except Exception as e:
                                        print(f"⚠️  Failed to decode image: {e}")

        return {
            "text": "\n".join(text_parts),
            "images": images
        }


async def main():
    """Demo the smart orchestrator with various query types."""

    print("\n" + "="*80)
    print("Smart Bridge Engineering Orchestrator")
    print("Powered by Sequential + Concurrent Workflows")
    print("="*80)

    async with SmartOrchestrator() as orchestrator:

        # Test queries demonstrating different orchestration patterns
        test_queries = [
            # Sequential workflow: SQL → Python
            "Show me Bridge 1001 span lengths as a bar chart",

            # Concurrent workflow: SQL + Databricks
            # "Get Bridge 1001 data and GDOT material standards",

            # Direct SQL agent
            # "Show me span lengths for Bridge 1001",

            # Direct Databricks agent
            # "What GDOT-approved concrete materials are available?",
        ]

        for query in test_queries:
            result = await orchestrator.run(query)

            print("\n" + "="*80)
            print("RESULT:")
            print("="*80)
            print(f"Strategy: {result['routing']['strategy']}")
            print(f"Text: {result['text'][:200]}..." if len(result['text']) > 200 else f"Text: {result['text']}")
            print(f"Images: {len(result['images'])} file(s)")
            print("="*80)

            input("\nPress Enter to continue to next query...")


if __name__ == "__main__":
    asyncio.run(main())
