"""
Streamlit UI for Bridge Engineering Multi-Agent System.

Uses SmartOrchestrator with Direct A2A orchestration patterns.
"""

import asyncio

import streamlit as st

from smart_orchestrator import SmartOrchestrator

# Import observability
from observability import configure_observability, get_tracer

# Configure observability for Streamlit frontend
configure_observability(
    service_name="streamlit-frontend",
    enable_httpx_instrumentation=True  # Trace calls to orchestrator/agents
)

# Get tracer for distributed tracing
tracer = get_tracer(__name__)

# Page configuration
st.set_page_config(
    page_title="Bridge Engineering Orchestrator",
    page_icon="🌉",
    layout="wide",
)

# Title and description
st.title("🌉 Bridge Engineering Multi-Agent System")
st.markdown("""
**Intelligent Multi-Agent Orchestration with Direct A2A Protocol**

Smart routing with support for all agent combinations:
- 🔗 **SQL Foundry Agent** - Bridge 1001 structural data queries
- 💎 **Databricks Agent** - Georgia DOT standards and specifications
- 🐍 **Python Tool Agent** - Data visualization and chart generation
- 🔍 **Bing Grounding Agent** - Construction costing and market pricing with real-time search
- 🎯 **Smart Routing** - Automatic workflow selection based on query analysis
""")

# Predefined queries with metadata
QUERY_CATEGORIES = {
    "📊 Visualizations (SQL → Python)": {
        "icon": "📊",
        "description": "Generate charts from bridge data",
        "queries": {
            "Span Lengths Bar Chart": "Show me Bridge 1001 span lengths as a bar chart",
            "Beam Types Chart": "Create a chart showing beam types for Bridge 1001",
            "Span Comparison": "Visualize span lengths across all spans in Bridge 1001",
            "Strand Count Chart": "Create a bar chart of strand counts for Bridge 1001 beams",
        }
    },
    "🔗 Bridge Data (SQL Agent)": {
        "icon": "🔗",
        "description": "Query Bridge 1001 structural information",
        "queries": {
            "All Span Lengths": "Show me span lengths for Bridge 1001",
            "Beam Details": "What are the beam types for Bridge 1001?",
            "All Structural Data": "Show me all structural details for Bridge 1001",
            "Strand Information": "What are the strand counts for Bridge 1001?",
            "End Bent Details": "Show me end bent information for Bridge 1001",
            "Construction Timeline": "What are the construction dates for Bridge 1001?",
        }
    },
    "💎 GDOT Standards (Databricks)": {
        "icon": "💎",
        "description": "Georgia DOT standards and specifications",
        "queries": {
            "Material Types": "What material types are in material_standards_georgia?",
            "Available Tables": "List all tables in the bridge catalog",
            "Standard Beam Types": "Show me standard beam types from standard_beam_types_georgia",
            "Design Parameters": "What design parameters are in the design_parameters table?",
            "Compliance Checklist": "Show me code compliance checklist items",
            "Environmental Factors": "What environmental factors are in environmental_factors_georgia?",
            "Concrete Materials": "What GDOT-approved concrete materials are available?",
        }
    },
    "🔄 Parallel Data (SQL + Databricks)": {
        "icon": "🔄",
        "description": "Gather data from multiple sources simultaneously",
        "queries": {
            "Bridge + Standards": "Get Bridge 1001 structural data and GDOT material standards",
            "Materials Comparison": "Show me Bridge 1001 materials and GDOT approved materials",
            "Design + Structure": "Get Bridge 1001 spans and GDOT design parameters",
            "Full Analysis": "Analyze Bridge 1001 with GDOT compliance requirements",
        }
    },
    "🎯 Three-Agent Workflow (SQL + Databricks + Python)": {
        "icon": "🎯",
        "description": "Compare bridge data with GDOT standards and visualize",
        "queries": {
            "Compare Materials Chart": "Compare Bridge 1001 materials with GDOT standards as a chart",
            "Compliance Visualization": "Visualize Bridge 1001 compliance with GDOT design parameters as a chart",
            "Standards Comparison": "Show Bridge 1001 beam types versus GDOT standard beam types as a comparison chart",
            "Full Comparison Chart": "Compare all Bridge 1001 structural data with GDOT standards and create a visualization",
        }
    },
    "🔍 Costing & Market Pricing (Bing Grounding)": {
        "icon": "🔍",
        "description": "Real-time market prices and construction costing information",
        "queries": {
            "Steel Prices": "What is the current market price for structural steel in the United States?",
            "Concrete Costs": "What are typical costs for concrete bridge construction per square foot?",
            "Rebar Pricing": "What are the latest prices for rebar and reinforcement materials?",
            "Material Trends": "How do construction material costs compare between 2023 and 2024?",
            "Prestressed Concrete Costs": "What are the current costs for prestressed concrete beams?",
            "Labor Cost Trends": "What are labor cost trends in bridge construction for 2024?",
            "Vendor Information": "Who are the major structural steel suppliers in the United States?",
            "Compliance Costs": "What are the costs for material testing and certification?",
        }
    }
}


def extract_images_from_result(result: dict) -> list:
    """Extract images from orchestrator result."""
    images = []
    if "images" in result and result["images"]:
        for img_info in result["images"]:
            if isinstance(img_info, dict) and "data" in img_info:
                images.append(img_info["data"])
            elif isinstance(img_info, bytes):
                images.append(img_info)
    return images


async def run_query(user_query: str):
    """Run query through the orchestrator."""
    # Start distributed trace for Streamlit request
    with tracer.start_as_current_span("streamlit.run_query") as span:
        span.set_attribute("user_query", user_query)

        async with SmartOrchestrator() as orchestrator:
            result = await orchestrator.run(user_query)

        span.set_attribute("success", "error" not in result)
        if "error" in result:
            span.set_attribute("error", result["error"])

        return result


def main():
    """Main Streamlit interface."""

    st.markdown("---")

    # Two-column layout for better organization
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.header("🎯 Query Selection")

        # Category selection
        selected_category = st.selectbox(
            "Select Query Category:",
            options=list(QUERY_CATEGORIES.keys()),
            index=0,
            help="Choose the type of query you want to run"
        )

        # Get queries for selected category
        category_info = QUERY_CATEGORIES[selected_category]
        st.markdown(f"**{category_info['icon']} {category_info['description']}**")

        # Query selection
        query_options = list(category_info['queries'].keys())
        selected_query_name = st.selectbox(
            "Select Query:",
            options=query_options,
            index=0,
            help="Choose a predefined query or write custom below"
        )

        # Get the actual query text
        selected_query = category_info['queries'][selected_query_name]

        # Custom query option
        st.markdown("### ✏️ Custom Query")
        use_custom = st.checkbox("Use custom query instead", value=False)

        if use_custom:
            user_query = st.text_area(
                "Enter your custom query:",
                value=selected_query,
                height=120,
                help="Type any question about bridge data, standards, or request visualizations"
            )
        else:
            user_query = selected_query
            st.info(f"📝 **Selected Query:**\n\n{user_query}")

        # Run button
        run_clicked = st.button(
            "🚀 Run Query",
            type="primary",
            use_container_width=True,
            help="Execute the query through the smart orchestrator"
        )

    with col_right:
        st.header("📋 Query Preview")

        # Show routing preview
        st.markdown("### 🎯 Expected Routing")

        query_lower = user_query.lower()
        is_viz = any(kw in query_lower for kw in ['chart', 'graph', 'plot', 'visualiz'])
        is_db = any(kw in query_lower for kw in ['gdot', 'standard', 'material', 'databricks'])
        is_sql = any(kw in query_lower for kw in ['bridge', 'span', 'beam', '1001'])
        is_costing = any(kw in query_lower for kw in ['cost', 'price', 'pricing', 'market', 'budget', 'vendor', 'supplier', 'economic', 'forecast', 'trend', 'inflation'])

        # Check for costing queries first
        if is_costing:
            st.success("**Strategy:** Direct Bing Grounding Agent")
            st.markdown("**Flow:** Bing Grounding Agent only")
            st.markdown("**Expected Output:** Real-time market pricing and costing information")
        # Three-agent workflow check (most complex first)
        elif is_viz and is_db and is_sql:
            st.success("**Strategy:** Three-Agent Workflow")
            st.markdown("**Flow:** (SQL + Databricks in parallel) → Python")
            st.markdown("**Expected Output:** Comparison data + Visualization")
        elif is_viz and is_sql:
            st.success("**Strategy:** Sequential Chart Workflow")
            st.markdown("**Flow:** SQL Agent → Python Agent")
            st.markdown("**Expected Output:** Data + Chart Image")
        elif is_db and is_sql:
            st.info("**Strategy:** Parallel Data Workflow")
            st.markdown("**Flow:** SQL Agent + Databricks Agent (concurrent)")
            st.markdown("**Expected Output:** Combined data from both sources")
        elif is_db:
            st.info("**Strategy:** Direct Databricks Agent")
            st.markdown("**Flow:** Databricks Agent only")
            st.markdown("**Expected Output:** GDOT standards data")
        else:
            st.info("**Strategy:** Direct SQL Agent")
            st.markdown("**Flow:** SQL Agent only")
            st.markdown("**Expected Output:** Bridge structural data")

        # Category info
        st.markdown("### 📚 Category Info")
        st.markdown(f"**{selected_category}**")
        st.markdown(f"_{category_info['description']}_")

        # Available queries in category
        with st.expander("📖 All queries in this category"):
            for name, query in category_info['queries'].items():
                st.markdown(f"**{name}:**")
                st.code(query, language=None)

    # Results section
    if run_clicked:
        if not user_query.strip():
            st.error("❌ Please enter a query")
            return

        st.markdown("---")
        st.header("🔄 Execution Results")

        try:
            with st.spinner("🔄 Initializing orchestrator and processing query..."):
                result = asyncio.run(run_query(user_query))

            # Check for errors
            if "error" in result:
                st.error(f"❌ Error: {result['error']}")
                with st.expander("📋 Error Details"):
                    st.code(result.get('error', 'Unknown error'))
                return

            # Display orchestration info
            st.subheader("🎯 Orchestration Details")
            routing = result.get("routing", {}) if "routing" in result else {}

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                strategy = routing.get("strategy", "unknown")
                st.metric("Strategy", strategy.replace("_", " ").title())
            with col_b:
                workflow = routing.get("workflow") or "Direct A2A"
                st.metric("Workflow Type", workflow.replace("_", " ").title())
            with col_c:
                agents = routing.get("agents", [])
                st.metric("Agents Used", len(agents))

            # Agent details
            with st.expander("🤖 Agent Details"):
                st.markdown(f"**Agents:** {', '.join(agents)}")
                for key, value in routing.items():
                    if key not in ['strategy', 'workflow', 'agents']:
                        st.markdown(f"- **{key}:** {value}")

            # Display response text
            if result.get("text"):
                st.subheader("📝 Response")

                # If multiple agents, show separated responses
                if "agent_responses" in result and len(result["agent_responses"]) > 1:
                    for agent_name, response_text in result["agent_responses"].items():
                        if agent_name != "workflow" and response_text:
                            with st.expander(f"🤖 {agent_name.upper()} Response", expanded=True):
                                st.text_area(
                                    f"{agent_name}_response",
                                    value=response_text,
                                    height=200,
                                    disabled=True,
                                    label_visibility="collapsed"
                                )
                else:
                    st.text_area(
                        "Full Response:",
                        value=result["text"],
                        height=300,
                        disabled=True
                    )

            # Display images
            images = extract_images_from_result(result)
            if images:
                st.subheader("📊 Generated Visualizations")

                # Display images in columns if multiple
                if len(images) > 1:
                    img_cols = st.columns(min(len(images), 2))
                    for i, img_bytes in enumerate(images):
                        with img_cols[i % 2]:
                            st.image(img_bytes, caption=f"Chart {i+1}", use_container_width=True)
                else:
                    st.image(images[0], caption="Generated Chart", use_container_width=True)

                st.success(f"✅ Successfully generated {len(images)} chart(s)!")
            elif routing.get("is_visualization"):
                st.warning("⚠️ Visualization was requested but no charts were generated.")

            # Success message
            st.success("✅ Query executed successfully!")

            # Download options
            if images:
                st.markdown("### 💾 Download")
                for i, img_bytes in enumerate(images):
                    st.download_button(
                        label=f"📥 Download Chart {i+1}",
                        data=img_bytes,
                        file_name=f"bridge_chart_{i+1}.png",
                        mime="image/png"
                    )

        except Exception as e:
            st.error(f"❌ Execution Error: {e}")
            with st.expander("📋 Full Error Traceback"):
                import traceback
                st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
