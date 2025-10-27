# Bing Grounding Agent

An intelligent construction costing and market pricing agent powered by Azure AI Foundry with Bing search grounding capabilities.

## Overview

The Bing Grounding Agent specializes in answering questions about construction costs, material prices, market trends, vendor information, and economic factors affecting bridge construction projects. It uses real-time Bing search to provide up-to-date pricing information and market intelligence.

## Features

- **Real-time Market Data**: Uses Bing search grounding for current pricing information
- **Construction Costing**: Provides cost estimates for materials, labor, and projects
- **Market Trends**: Analyzes pricing trends and economic forecasts
- **Vendor Information**: Finds suppliers and manufacturers
- **Compliance Costs**: Research certification and testing costs
- **Built-in Observability**: Full distributed tracing with Azure Application Insights
- **A2A Protocol**: Compatible with Microsoft Agent Framework A2A orchestration

## Agent Capabilities

### Construction Material Pricing
Query current market prices for:
- Structural steel
- Concrete (various grades)
- Rebar and reinforcement materials
- Prestressed concrete components
- Bridge construction materials

### Cost Analysis
Analyze and compare:
- Bridge construction costs per square foot
- Material cost trends (year-over-year)
- Cost breakdowns by component
- Steel vs. concrete construction costs
- Labor cost trends

### Market Intelligence
Research:
- Price forecasts and trends
- Economic factors affecting costs
- Supply chain impacts
- Commodity price influences
- Regional cost variations

### Vendor & Supplier Information
Find:
- Major suppliers by category
- GDOT-approved vendors
- Lead times and availability
- Material sourcing options
- Manufacturer information

### Regulatory & Compliance
Understand costs for:
- Material testing and certification
- GDOT approval processes
- Compliance with standards
- Environmental requirements
- Quality assurance

## Architecture

```
User Query
    ↓
Bing Grounding Agent (A2A Server)
    ↓
Azure AI Foundry Agent
    ↓
Bing Search Grounding Tool
    ↓
Real-time Market Data
```

## Configuration

### Required Environment Variables

```bash
# Azure AI Foundry Configuration
PROJECT_ENDPOINT="https://your-project.services.ai.azure.com/api/projects/your-project"
BING_GROUNDING_AGENT_ID="asst_QZZuly3q633MzDQyWUphMfgw"

# Azure Application Insights (for observability)
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=xxx;IngestionEndpoint=https://..."

# A2A Server Configuration
BING_AGENT_URL="http://localhost:10011"
BING_AGENT_PORT=10011
```

### Azure AI Foundry Setup

1. Create an Azure AI Foundry project
2. Create a new agent with Bing search grounding enabled
3. Configure the agent with instructions for construction costing
4. Note the agent ID (format: `asst_xxxxxxxxxxxxx`)
5. Ensure Bing connection is configured in your project

## Usage

### Running as A2A Server

```bash
# Install dependencies
uv sync

# Run the agent server
uv run python -m bing_grounding_agent --host localhost --port 10011
```

### Direct Usage (Programmatic)

```python
import asyncio
from bing_grounding_agent import create_bing_grounding_agent

async def main():
    # Create the agent
    agent = await create_bing_grounding_agent()

    # Create a conversation thread
    thread = await agent.create_thread()

    # Send a query
    query = "What is the current market price for structural steel in the United States?"
    responses = await agent.run_conversation(thread['id'], query)

    for response in responses:
        print(f"Agent: {response}")

    # Cleanup
    await agent.cleanup_agent()

asyncio.run(main())
```

### Integration with Smart Orchestrator

The agent is automatically integrated with the Smart Orchestrator and routes costing-related queries:

```python
# Queries containing cost/price keywords are automatically routed
queries = [
    "What is the current market price for structural steel?",
    "How do construction costs compare between 2023 and 2024?",
    "What are the latest prices for rebar?",
    "Who are the major steel suppliers in the US?",
]
```

## Example Queries

### Material Pricing
- "What is the current market price for structural steel in the United States?"
- "What are typical costs for concrete per cubic yard?"
- "What are the latest prices for rebar and reinforcement materials?"
- "How much does prestressed concrete cost per square foot?"

### Cost Analysis
- "What are typical costs for bridge construction per square foot?"
- "How do construction material costs compare between 2023 and 2024?"
- "What is the cost breakdown for a prestressed concrete bridge?"
- "Compare costs between steel and concrete bridge construction"

### Market Trends
- "What are the price trends for construction materials in 2024?"
- "How is inflation affecting bridge construction costs?"
- "What are the supply chain impacts on material pricing?"
- "What is the forecast for steel prices in the next quarter?"

### Vendor Information
- "Who are the major structural steel suppliers in the United States?"
- "What suppliers provide GDOT-approved materials?"
- "Which vendors offer prestressed concrete beams?"
- "What are lead times for bridge construction materials?"

### Compliance Costs
- "What are the costs for material testing and certification?"
- "How much does GDOT material approval cost?"
- "What are compliance costs for bridge construction standards?"
- "What are testing requirements and costs for concrete strength?"

## Observability

The agent includes built-in observability with Azure Application Insights:

- **Distributed Tracing**: Full end-to-end trace correlation
- **Agent Metrics**: Request counts, latency, success rates
- **Search Analytics**: Bing search performance and results
- **Error Tracking**: Automatic error logging and diagnostics

### Viewing Traces

1. Open Azure Portal
2. Navigate to your Application Insights resource
3. Go to "Transaction search" or "Application map"
4. Filter by service name: `bing-grounding-agent`
5. View detailed traces with timing and dependencies

## Integration with Streamlit UI

The Bing Grounding Agent is integrated into the Streamlit UI with a dedicated category:

- Category: "🔍 Costing & Market Pricing (Bing Grounding)"
- 8 predefined queries covering common use cases
- Automatic routing based on cost/price keywords
- Real-time search results displayed in UI

## Health Check

Verify the agent is running:

```bash
curl http://localhost:10011/health
```

Expected response:
```
Bing Grounding Costing Agent is running!
```

## Troubleshooting

### Common Issues

1. **Agent not found**
   - Verify `BING_GROUNDING_AGENT_ID` is correct
   - Check agent exists in Azure AI Studio
   - Ensure agent has Bing grounding enabled

2. **Authentication failed**
   - Run `az login`
   - Verify credentials have access to AI Foundry project
   - Check `PROJECT_ENDPOINT` is correct

3. **Bing search not working**
   - Verify Bing connection is configured in AI Foundry project
   - Check agent instructions include Bing search guidance
   - Ensure Bing resource is properly connected

4. **Traces not appearing**
   - Verify `APPLICATIONINSIGHTS_CONNECTION_STRING` is set
   - Wait 2-3 minutes for telemetry to appear
   - Check Application Insights resource permissions

## Development

### Project Structure

```
bing_grounding_agent/
├── __init__.py                          # Package exports
├── __main__.py                          # A2A server entry point
├── bing_grounding_agent.py              # Core agent logic
├── bing_grounding_agent_executor.py     # A2A executor implementation
└── README.md                            # This file
```

### Testing

Run the demo interaction:

```bash
uv run python -m bing_grounding_agent.bing_grounding_agent
```

This will run several test queries and display responses.

### Extending the Agent

To add new capabilities:

1. Update agent instructions in Azure AI Foundry
2. Add new skills in `__main__.py`
3. Update query categories in Streamlit app
4. Add keyword detection in Smart Orchestrator

## Performance

- **Average Query Time**: 3-5 seconds (including Bing search)
- **Concurrent Requests**: Supports multiple concurrent threads
- **Rate Limits**: Subject to Bing API rate limits
- **Caching**: Results are not cached (ensures fresh data)

## Security

- Uses Azure DefaultAzureCredential for authentication
- No API keys stored in code
- Supports managed identity in production
- Bing search results are not stored

## Related Components

- **Smart Orchestrator**: Automatically routes costing queries to this agent
- **Streamlit UI**: Provides user-friendly interface with predefined queries
- **Observability Module**: Shared tracing infrastructure
- **SQL Foundry Agent**: Complements with bridge data
- **Databricks Agent**: Provides GDOT standards context

## License

Part of the Microsoft Agentic AI project.

## Support

For issues or questions:
1. Check Azure AI Foundry agent configuration
2. Review Application Insights traces
3. Verify environment variables
4. Check agent health endpoint
