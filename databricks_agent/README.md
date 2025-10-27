# Databricks Agent

An intelligent A2A-compliant agent for querying Databricks Unity Catalog using the Microsoft Agent Framework and MCP (Model Context Protocol) tools.

## Overview

The Databricks Agent connects to Databricks Unity Catalog through an MCP server deployed as a containerized service on Azure, exposed via Azure API Management (APIM) with JWT authentication. It provides natural language interface to:

- List and explore Databricks catalogs, schemas, tables, and functions
- Execute SQL queries against Databricks
- Get table metadata and statistics
- Analyze data and provide insights

## Architecture

```
┌─────────────────┐
│ Databricks Agent│
│  (A2A Server)   │
└────────┬────────┘
         │
         │ JWT Token (via Service Principal)
         ▼
┌─────────────────┐
│  Azure APIM     │ ◄─── JWT Validation
│  (API Gateway)  │
└────────┬────────┘
         │
         │ Managed Identity
         ▼
┌─────────────────┐
│  MCP Server     │ ◄─── Container App
│  (Databricks)   │
└────────┬────────┘
         │
         │ Managed Identity
         ▼
┌─────────────────┐
│   Databricks    │
│ Unity Catalog   │
└─────────────────┘
```

## Components

### 1. databricks_agent.py
Core agent implementation using Microsoft Agent Framework:
- `DatabricksAgent`: Main agent class with MCP tool integration
- Handles JWT authentication for APIM
- Manages MCP connection lifecycle
- Integrates with shared observability for distributed tracing

### 2. databricks_agent_executor.py
A2A protocol executor:
- `DatabricksAgentExecutor`: Wraps the agent for A2A compatibility
- Converts A2A messages to agent requests
- Handles task lifecycle (submit, working, complete, failed)

### 3. __main__.py
A2A server entry point:
- Creates A2A Starlette application
- Defines agent skills and capabilities
- Exposes AgentCard at `/.well-known/agent.json`
- Runs HTTP server on port 10010

## Configuration

Add to your `.env` file:

```bash
# Databricks Agent Configuration
DATABRICKS_MCP_SERVER_URL=https://apim-xxxxx.azure-api.net/databricksmcp
DATABRICKS_MCP_NAME=Databricks MCP

# Authentication (Service Principal for APIM)
DATABRICKS_BACKEND_APP_ID=your-backend-app-id
DATABRICKS_AGENT_CLIENT_ID=your-agent-client-id
DATABRICKS_AGENT_CLIENT_SECRET=your-agent-client-secret
DATABRICKS_TENANT_ID=your-tenant-id

# Azure OpenAI (for chat completions)
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4

# Observability (optional)
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
```

## Running the Agent

### Standalone Mode

```bash
# Start the agent server
uv run python -m databricks_agent

# Or with custom host/port
uv run python -m databricks_agent --host 0.0.0.0 --port 10010
```

The agent will be available at:
- A2A endpoint: `http://localhost:10010/`
- Agent card: `http://localhost:10010/.well-known/agent.json`
- Health check: `http://localhost:10010/health`

### Integration with Orchestrator

The agent is integrated into the multi-agent orchestrator ([agent_orchestrator_a2a.py](../agent_orchestrator_a2a.py)):

```python
# In orchestrator
databricks_agent_url = "http://localhost:10010"
databricks_resolver = A2ACardResolver(httpx_client=http_client, base_url=databricks_agent_url)
databricks_card = await databricks_resolver.get_agent_card(relative_card_path="/.well-known/agent.json")

databricks_agent = A2AAgent(
    name=databricks_card.name,
    description=databricks_card.description,
    agent_card=databricks_card,
    url=databricks_agent_url,
)

# Query Databricks
response = await databricks_agent.run("What catalogs are available?")
```

## Skills

The agent provides four main skills:

### 1. Catalog Exploration
- List catalogs, schemas, tables, and functions
- Explore Unity Catalog structure
- Get metadata for catalog objects

**Examples:**
- "What catalogs are available in Databricks?"
- "Show me the schemas in the main catalog"
- "List all tables in the default schema"

### 2. SQL Query Execution
- Execute SQL queries against Unity Catalog
- Retrieve and analyze data
- Perform aggregations and filtering

**Examples:**
- "Run a SQL query to get the top 10 rows from table X"
- "Count the number of records in table Y"
- "Get the sum of column Z grouped by category"

### 3. Table Metadata and Statistics
- Get detailed schema information
- View column types and properties
- Access table statistics

**Examples:**
- "Get the schema for table X"
- "Show me column types for table Y"
- "What are the statistics for table Z?"

### 4. Data Analysis and Insights
- Analyze data distributions
- Find trends and patterns
- Summarize key metrics

**Examples:**
- "Analyze the data distribution in table X"
- "Find trends in the sales data"
- "Summarize the key metrics from table Y"

## Authentication Flow

1. **Agent authenticates with APIM**:
   - Uses Service Principal credentials (`DATABRICKS_AGENT_CLIENT_ID`, `DATABRICKS_AGENT_CLIENT_SECRET`)
   - Requests JWT token with audience `api://{DATABRICKS_BACKEND_APP_ID}/.default`
   - Token is added to Authorization header

2. **APIM validates JWT**:
   - Verifies token signature and claims
   - Checks token audience matches backend API
   - Forwards request to MCP server

3. **MCP server accesses Databricks**:
   - Uses Managed Identity to authenticate with Databricks
   - Executes MCP tool calls (list, query, metadata)
   - Returns results to agent

## Observability

The agent integrates with the shared observability system ([observability.py](../observability.py)):

- **Service Name**: `databricks-agent`
- **Distributed Tracing**: Enabled via OpenTelemetry + HTTPX instrumentation
- **Trace Context Propagation**: W3C traceparent/tracestate headers
- **Application Insights**: All traces sent to Azure Application Insights

**Traced Operations:**
- `databricks_agent.connect_mcp` - MCP server connection
- `databricks_agent.get_or_create_history` - Conversation management
- `databricks_agent.process_message` - Message processing
- `databricks_agent.invoke_agent` - Agent invocation with MCP tools

View traces in Azure Portal → Application Insights → Transaction search.

## Example Usage

### Direct Python Usage

```python
from databricks_agent import create_databricks_agent

async def main():
    agent = await create_databricks_agent()

    try:
        context_id = "session-123"

        # Query catalogs
        response = await agent.process_message(
            context_id,
            "What catalogs are available in Databricks?"
        )
        print(response["text"])

        # Execute SQL
        response = await agent.process_message(
            context_id,
            "SELECT * FROM main.default.my_table LIMIT 10"
        )
        print(response["text"])

    finally:
        await agent.cleanup()
```

### A2A Protocol Usage

```bash
# Send request via HTTP
curl -X POST http://localhost:10010/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "session-123",
    "message": {
      "role": "user",
      "parts": [{
        "text": "What catalogs are available?"
      }]
    }
  }'
```

## Troubleshooting

### "Authentication failed for APIM"
- Verify `DATABRICKS_AGENT_CLIENT_ID` and `DATABRICKS_AGENT_CLIENT_SECRET`
- Check that Service Principal has access to backend API
- Ensure `DATABRICKS_BACKEND_APP_ID` is correct

### "MCP server not accessible"
- Verify `DATABRICKS_MCP_SERVER_URL` is correct
- Check APIM is deployed and configured
- Ensure MCP server container is running

### "Databricks connection failed"
- Verify MCP server has Managed Identity assigned
- Check Managed Identity has Databricks access
- Review MCP server logs for authentication errors

### "No traces in Application Insights"
- Verify `APPLICATIONINSIGHTS_CONNECTION_STRING` is set
- Check network connectivity to ingestion endpoint
- Look for observability configuration output on startup

---

## 📊 Bridge Engineering Data Schema

This section describes the bridge engineering tables available in Databricks Unity Catalog.

__Location:__ `engineeringconn_catalog.bridge` schema

### Tables Overview

| Table Name | Purpose | Key Fields |
|------------|---------|------------|
| `beam_types` | Standard beam type specifications | beam_type_id, name, system, typical_beam_max_span_ft |
| `bridges` | Bridge inventory | bridge_id, bridge_no, pi_no |
| `code_compliance_checklist` | Compliance requirements | checklist_id, standard_id, component_type, check_description |
| `design_parameters` | Design parameter specs | param_id, standard_id, parameter_name, value, unit |
| `design_standards` | GDOT design standards | standard_id, standard_code, standard_name, issuing_authority |
| `design_validation_rules` | Design validation rules | rule_id, rule_name, component_type, operator, threshold_value |
| `environmental_factors_georgia` | GA regional environmental factors | env_id, region, county, design_wind_mph, seismic_category |
| `material_standards_georgia` | GDOT-approved materials | material_id, material_type, grade_specification, yield_strength_psi |
| `materials` | Material catalog | material_code, description |
| `standard_beam_types_georgia` | GA standard beam types | beam_type_id, beam_name, gdot_code, depth_inches, recommended_span_min_ft |

### Common Query Examples

#### Find Beams for a Specific Span

```sql
SELECT beam_name, gdot_code,
       recommended_span_min_ft, recommended_span_max_ft
FROM engineeringconn_catalog.bridge.standard_beam_types_georgia
WHERE 100 BETWEEN recommended_span_min_ft AND recommended_span_max_ft;
```

#### Get Environmental Requirements by County

```sql
SELECT county, design_wind_mph, design_snow_psf,
       seismic_category, frost_line_depth_ft
FROM engineeringconn_catalog.bridge.environmental_factors_georgia
WHERE county = 'Fulton';
```

#### List GDOT-Approved Concrete Materials

```sql
SELECT material_type, grade_specification,
       yield_strength_psi, ultimate_strength_psi
FROM engineeringconn_catalog.bridge.material_standards_georgia
WHERE material_type LIKE '%Concrete%'
  AND gdot_approved = true;
```

#### Check Compliance Requirements

```sql
SELECT component_type, check_description,
       acceptance_criteria, severity
FROM engineeringconn_catalog.bridge.code_compliance_checklist
WHERE severity IN ('CRITICAL', 'HIGH')
ORDER BY component_type, check_number;
```

### Natural Language Queries

The Databricks agent understands natural language questions like:

- "What GDOT-approved materials are available for prestressed concrete?"
- "Show me environmental requirements for Fulton County"
- "Which beam types are suitable for a 100-foot span?"
- "List all design standards from GDOT"
- "What are the critical compliance checks for beams?"

The agent will automatically query the appropriate tables and provide formatted results.

---

## Related Documentation

- [Main README](../README.md) - Complete system overview and observability
- [Agent Orchestrator](../agent_orchestrator_a2a.py) - Multi-agent orchestration
- [A2A Protocol](https://a2a-protocol.org/latest/) - A2A specification
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) - Agent Framework docs
- [MCP Protocol](https://modelcontextprotocol.io/) - MCP specification
