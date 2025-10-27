"""Streamlit UI for Multi-Agent Bridge Engineering System.

This application provides a web interface to orchestrate SQL Foundry and Python Tool agents
for bridge engineering data analysis and visualization.
"""

import asyncio
import base64
from io import BytesIO

import httpx
import streamlit as st
from a2a.client import A2ACardResolver
from agent_framework.a2a import A2AAgent
from dotenv import load_dotenv
from observability import configure_observability, get_tracer, print_trace_info
from PIL import Image

load_dotenv()

# Configure observability for the Streamlit frontend
configure_observability(
    service_name="streamlit-frontend",
    enable_logging=True,
    enable_tracing=True,
    enable_httpx_instrumentation=True,
)

# Get tracer for distributed tracing
tracer = get_tracer(__name__)


# Page configuration
st.set_page_config(
    page_title="Bridge Engineering Multi-Agent System",
    page_icon="🌉",
    layout="wide",
)

# Title and description
st.title("🌉 Bridge Engineering Multi-Agent System")
st.markdown("""
This application orchestrates multiple AI agents to analyze bridge engineering data and create visualizations:
- **SQL Foundry Agent**: Queries bridge engineering database using natural language
- **Python Tool Agent**: Creates charts and visualizations from the data
- **Databricks Agent**: Queries Georgia DOT bridge standards from Unity Catalog
""")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")
sql_agent_url = st.sidebar.text_input("SQL Agent URL", "http://localhost:10008")
python_agent_url = st.sidebar.text_input("Python Tool Agent URL", "http://localhost:10009")
databricks_agent_url = st.sidebar.text_input("Databricks Agent URL", "http://localhost:10010")
timeout = st.sidebar.slider("Timeout (seconds)", 60, 300, 180)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 Example Queries")

st.sidebar.markdown("**SQL Foundry Agent (Bridge 1001 Data):**")
st.sidebar.markdown("""
- Show me span lengths for Bridge 1001
- List all beams for Bridge 1001
- What are the strand counts by span?
- Show me end bent information
""")

st.sidebar.markdown("**Databricks Agent (GDOT Standards):**")
st.sidebar.markdown("""
- What GDOT-approved materials are available?
- Show me environmental requirements for Fulton County
- List standard Georgia beam types
- What are the design wind speeds by region?
""")


async def query_sql_agent(sql_agent, query):
    """Query the SQL Foundry Agent."""
    with tracer.start_as_current_span("streamlit.query_sql_agent") as span:
        span.set_attribute("sql.query", query[:200])

        response = await sql_agent.run(query)

        # Extract response text
        result_text = ""
        if hasattr(response, "raw_representation") and response.raw_representation:
            for task in response.raw_representation:
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            if hasattr(part, "root") and hasattr(part.root, "text"):
                                result_text += part.root.text + "\n"

        span.set_attribute("sql.response_length", len(result_text))
        span.set_attribute("execution.status", "success")
        return result_text.strip()


async def query_databricks_agent(databricks_agent, query):
    """Query the Databricks Agent."""
    with tracer.start_as_current_span("streamlit.query_databricks_agent") as span:
        span.set_attribute("databricks.query", query[:200])

        response = await databricks_agent.run(query)

        # Extract response text
        result_text = ""
        if hasattr(response, "raw_representation") and response.raw_representation:
            for task in response.raw_representation:
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            if hasattr(part, "root") and hasattr(part.root, "text"):
                                result_text += part.root.text + "\n"

        span.set_attribute("databricks.response_length", len(result_text))
        span.set_attribute("execution.status", "success")
        return result_text.strip()


async def create_visualization(python_agent, data_text, viz_instructions):
    """Create visualization using Python Tool Agent."""
    with tracer.start_as_current_span("streamlit.create_visualization") as span:
        span.set_attribute("viz.instructions", viz_instructions[:200])
        span.set_attribute("viz.data_length", len(data_text))

        viz_query = f"""
Based on this data, create a visualization:

{data_text}

{viz_instructions}
"""

        response = await python_agent.run(viz_query)

        # Extract response text and images
        result_text = ""
        images = []

        if hasattr(response, "raw_representation") and response.raw_representation:
            for task in response.raw_representation:
                # Check task history for images (from working status updates)
                if hasattr(task, "history") and task.history:
                    for msg in task.history:
                        if hasattr(msg, "parts") and msg.parts:
                            for part in msg.parts:
                                part_root = part.root
                                # Extract text
                                if hasattr(part_root, "text"):
                                    result_text += part_root.text + "\n"
                                # Extract images from file parts
                                elif hasattr(part_root, "file"):
                                    file_obj = part_root.file
                                    if hasattr(file_obj, "bytes"):
                                        # Decode base64 image
                                        image_bytes = base64.b64decode(file_obj.bytes) if isinstance(file_obj.bytes, str) else file_obj.bytes
                                        images.append(image_bytes)
                                        st.info(f"Found image in history: {getattr(file_obj, 'name', 'unnamed')}")

                # Also check final status message
                if hasattr(task, "status") and hasattr(task.status, "message"):
                    status_msg = task.status.message
                    if hasattr(status_msg, "parts") and status_msg.parts:
                        for part in status_msg.parts:
                            part_root = part.root
                            # Extract text
                            if hasattr(part_root, "text"):
                                result_text += part_root.text + "\n"
                            # Extract images
                            elif hasattr(part_root, "file"):
                                file_obj = part_root.file
                                if hasattr(file_obj, "bytes"):
                                    # Decode base64 image
                                    image_bytes = base64.b64decode(file_obj.bytes) if isinstance(file_obj.bytes, str) else file_obj.bytes
                                    images.append(image_bytes)
                                    st.info(f"Found image in status: {getattr(file_obj, 'name', 'unnamed')}")

        if not images:
            st.warning(f"No images found. Response structure: {type(response)}")
            st.json({"has_raw_representation": hasattr(response, "raw_representation")})

        span.set_attribute("viz.image_count", len(images))
        span.set_attribute("viz.response_length", len(result_text))
        span.set_attribute("execution.status", "success")
        return result_text.strip(), images


async def orchestrate_agents(sql_query, viz_instructions):
    """Orchestrate SQL and Python Tool agents."""
    with tracer.start_as_current_span("streamlit.orchestrate_agents") as span:
        span.set_attribute("sql.query", sql_query[:200])
        span.set_attribute("viz.instructions", viz_instructions[:200])
        print_trace_info()

        async with httpx.AsyncClient(timeout=float(timeout)) as http_client:

            # Connect to SQL Agent
            with st.spinner("🔗 Connecting to SQL Foundry Agent..."):
                sql_resolver = A2ACardResolver(httpx_client=http_client, base_url=sql_agent_url)
                sql_card = await sql_resolver.get_agent_card(relative_card_path="/.well-known/agent.json")

                sql_agent = A2AAgent(
                    name=sql_card.name,
                    description=sql_card.description,
                    agent_card=sql_card,
                    url=sql_agent_url,
                )
                st.success(f"✅ Connected to {sql_card.name}")

            # Query SQL Agent
            with st.spinner("🔍 Querying bridge data..."):
                sql_result = await query_sql_agent(sql_agent, sql_query)
                st.success("✅ Data retrieved")

            # Connect to Python Tool Agent
            with st.spinner("🔗 Connecting to Python Tool Agent..."):
                python_resolver = A2ACardResolver(httpx_client=http_client, base_url=python_agent_url)
                python_card = await python_resolver.get_agent_card(relative_card_path="/.well-known/agent.json")

                python_agent = A2AAgent(
                    name=python_card.name,
                    description=python_card.description,
                    agent_card=python_card,
                    url=python_agent_url,
                )
                st.success(f"✅ Connected to {python_card.name}")

            # Create Visualization
            with st.spinner("🎨 Creating visualization..."):
                viz_result, images = await create_visualization(python_agent, sql_result, viz_instructions)
                st.success("✅ Visualization created")

            span.set_attribute("orchestration.status", "completed")
            span.set_attribute("orchestration.image_count", len(images))
            return sql_result, viz_result, images


# Main interface
st.markdown("---")
st.header("�� Agent Orchestration")

# Input form
with st.form("query_form"):
    col1, col2 = st.columns(2)

    with col1:
        sql_query = st.text_area(
            "SQL Query (Natural Language)",
            value="Show me the span length for all beams in Bridge 1001",
            height=100,
            help="Enter a natural language query for the SQL Foundry Agent"
        )

    with col2:
        viz_instructions = st.text_area(
            "Visualization Instructions",
            value="Create a bar chart showing the span length for each span. Label the x-axis as 'Span Number' and y-axis as 'Length (ft)'.",
            height=100,
            help="Instructions for how to visualize the data"
        )

    submitted = st.form_submit_button("🚀 Run Multi-Agent Workflow", use_container_width=True)

# Process query when submitted
if submitted:
    if not sql_query or not viz_instructions:
        st.error("⚠️ Please provide both a SQL query and visualization instructions")
    else:
        try:
            # Run async orchestration
            sql_result, viz_result, images = asyncio.run(
                orchestrate_agents(sql_query, viz_instructions)
            )

            # Display results
            st.markdown("---")
            st.header("📊 Results")

            # SQL Results
            with st.expander("🗄️ SQL Query Results", expanded=True):
                st.code(sql_result, language="text")

            # Visualization Results
            st.subheader("📈 Visualization")

            if images:
                for idx, image_bytes in enumerate(images):
                    img = Image.open(BytesIO(image_bytes))
                    st.image(img, caption=f"Generated Visualization {idx + 1}", use_container_width=True)
            else:
                st.info("No images were generated")

            # Agent Response
            with st.expander("🤖 Agent Response Details", expanded=False):
                st.markdown(viz_result)

            st.success("✅ Multi-agent workflow completed successfully!")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            with st.expander("🔍 Error Details"):
                st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Bridge Engineering Multi-Agent System | Powered by Microsoft Agent Framework & A2A Protocol</p>
</div>
""", unsafe_allow_html=True)
