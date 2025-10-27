"""Databricks Agent implementation using Microsoft Agent Framework with MCP tools.

This agent connects to Databricks Unity Catalog through an MCP server deployed
on Azure via API Management (APIM) with JWT authentication.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from agent_framework import ChatAgent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential, ClientSecretCredential
from opentelemetry import trace

# Import shared observability configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from observability import get_tracer, inject_trace_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Get tracer for distributed tracing
tracer = get_tracer(__name__)


class DatabricksAgent:
    """Databricks Agent for querying Unity Catalog through MCP server.

    This agent specializes in:
    - Listing Databricks catalogs, schemas, tables, and functions
    - Executing SQL queries on Databricks
    - Getting table metadata and statistics
    - Analyzing data in Databricks Unity Catalog
    """

    def __init__(self) -> None:
        """Initialize the Databricks Agent with MCP tools."""
        # Get MCP configuration from environment
        self.mcp_url = os.environ.get('DATABRICKS_MCP_SERVER_URL')
        if not self.mcp_url:
            raise ValueError('DATABRICKS_MCP_SERVER_URL environment variable is required')

        self.mcp_name = os.environ.get('DATABRICKS_MCP_NAME', 'Databricks MCP')

        # Get Azure OpenAI configuration
        azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
        if not azure_openai_endpoint:
            raise ValueError('AZURE_OPENAI_ENDPOINT environment variable is required')

        # Get JWT configuration for APIM
        self.backend_app_id = os.environ.get('DATABRICKS_BACKEND_APP_ID')
        self.agent_client_id = os.environ.get('DATABRICKS_AGENT_CLIENT_ID')
        self.agent_client_secret = os.environ.get('DATABRICKS_AGENT_CLIENT_SECRET')
        self.tenant_id = os.environ.get('DATABRICKS_TENANT_ID')

        # Create Azure credential for Azure OpenAI
        logger.info('Initializing Azure credentials for OpenAI...')
        try:
            # Use AzureCliCredential for Azure OpenAI
            self.credential = AzureCliCredential()
            logger.info('Using AzureCliCredential for Azure OpenAI')
        except Exception as e:
            logger.error(f'Azure authentication failed: {e}')
            raise

        # Create chat client
        self.chat_client = AzureOpenAIChatClient(credential=self.credential)

        # Create chat agent
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            name="DatabricksAgent",
            instructions=(
                "You are a helpful assistant specializing in bridge engineering data analysis using Databricks Unity Catalog. "
                "You have access to a Databricks Unity Catalog through MCP tools that allow you to: "
                "- List catalogs, schemas, tables, and functions "
                "- Execute SQL queries to analyze data "
                "- Get table metadata and statistics "
                "\n"
                "**Bridge Engineering Data Location:**\n"
                "- Catalog: `engineeringconn_catalog`\n"
                "- Schema: `bridge`\n"
                "- Tables contain Georgia bridge standards and engineering specifications\n"
                "\n"
                "**Available Bridge Engineering Tables:**\n"
                "1. **beam_types** - Standard beam types with specifications\n"
                "   - beam_type_id, name, system, typical_beam_max_span_ft, notes\n"
                "\n"
                "2. **bridges** - Bridge inventory and basic information\n"
                "   - bridge_id, bridge_no, pi_no, pi_no_raw, pi_no_norm\n"
                "\n"
                "3. **code_compliance_checklist** - Compliance requirements\n"
                "   - checklist_id, standard_id, component_type, check_number, check_description, acceptance_criteria, severity, created_at\n"
                "\n"
                "4. **design_parameters** - Design parameter specifications\n"
                "   - param_id, standard_id, component_type, parameter_name, value, unit, min_value, max_value, notes, created_at\n"
                "\n"
                "5. **design_standards** - Georgia DOT design standards\n"
                "   - standard_id, standard_code, standard_name, issuing_authority, effective_date, description, applicability, created_at, updated_at\n"
                "\n"
                "6. **design_validation_rules** - Validation rules for designs\n"
                "   - rule_id, rule_name, component_type, parameter_name, operator, threshold_value, severity, error_message, created_at\n"
                "\n"
                "7. **environmental_factors_georgia** - Georgia regional environmental factors\n"
                "   - env_id, region, county, design_wind_mph, design_snow_psf, seismic_category, salt_exposure, frost_line_depth_ft, notes, created_at\n"
                "\n"
                "8. **material_standards_georgia** - GDOT-approved materials\n"
                "   - material_id, material_type, grade_specification, yield_strength_psi, ultimate_strength_psi, modulus_elasticity_psi, unit_weight_pcf, min_cover_top_inches, min_cover_bottom_inches, corrosion_environment, gdot_approved, notes, created_at\n"
                "\n"
                "9. **materials** - Material catalog\n"
                "   - material_code, description\n"
                "\n"
                "10. **standard_beam_types_georgia** - Standard Georgia beam specifications\n"
                "    - beam_type_id, beam_name, gdot_code, depth_inches, recommended_span_min_ft, recommended_span_max_ft, typical_strand_count, typical_concrete_psi, notes, created_at\n"
                "\n"
                "**Query Guidelines:**\n"
                "- Always prefix table names with `engineeringconn_catalog.bridge.{table_name}`\n"
                "- For bridge standards questions, query `design_standards` and `design_parameters`\n"
                "- For Georgia-specific data, use tables with `_georgia` suffix\n"
                "- For material specifications, query `material_standards_georgia`\n"
                "- For environmental requirements by region/county, use `environmental_factors_georgia`\n"
                "- For compliance checks, use `code_compliance_checklist`\n"
                "\n"
                "**Example Queries:**\n"
                "- List Georgia regions: `SELECT DISTINCT region, county FROM engineeringconn_catalog.bridge.environmental_factors_georgia`\n"
                "- Get beam types: `SELECT * FROM engineeringconn_catalog.bridge.standard_beam_types_georgia`\n"
                "- Find design standards: `SELECT * FROM engineeringconn_catalog.bridge.design_standards WHERE issuing_authority = 'GDOT'`\n"
                "- Material specifications: `SELECT * FROM engineeringconn_catalog.bridge.material_standards_georgia WHERE gdot_approved = true`\n"
                "\n"
                "When users ask about bridge engineering, standards, materials, or Georgia-specific requirements, "
                "use these tools to explore the data and provide clear, accurate insights. "
                "Always explain what you're doing and format results clearly."
            ),
        )

        # Initialize MCP tool (will be connected when needed)
        self.mcp_tool = None
        self.conversations: dict[str, list[dict]] = {}

        logger.info('Databricks Agent initialized successfully')

    def _get_jwt_token(self) -> str:
        """Get JWT token for calling APIM with backend API audience."""
        if not all([self.agent_client_id, self.agent_client_secret, self.tenant_id]):
            raise ValueError(
                "Missing required environment variables for JWT: "
                "DATABRICKS_AGENT_CLIENT_ID, DATABRICKS_AGENT_CLIENT_SECRET, DATABRICKS_TENANT_ID"
            )

        # Create credential for agent service principal
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.agent_client_id,
            client_secret=self.agent_client_secret
        )

        # Get token for backend API (synchronous call)
        token_result = credential.get_token(f"api://{self.backend_app_id}/.default")
        return token_result.token

    async def _ensure_mcp_connected(self) -> MCPStreamableHTTPTool:
        """Ensure MCP tool is connected and return it."""
        if self.mcp_tool is None:
            with tracer.start_as_current_span("databricks_agent.connect_mcp") as span:
                span.set_attribute("mcp.url", self.mcp_url)
                span.set_attribute("mcp.name", self.mcp_name)

                # Get JWT token for APIM authentication
                jwt_token = self._get_jwt_token()
                logger.info('Obtained JWT token for APIM access')

                # Prepare headers with JWT and trace context
                headers = {"Authorization": f"Bearer {jwt_token}"}
                inject_trace_context(headers)

                # Create MCP tool
                self.mcp_tool = MCPStreamableHTTPTool(
                    name=self.mcp_name,
                    url=self.mcp_url,
                    headers=headers
                )
                await self.mcp_tool.__aenter__()
                logger.info('Connected to MCP server at %s', self.mcp_url)

        return self.mcp_tool

    async def get_or_create_history(self, context_id: str) -> list[dict]:
        """Get or create conversation history for a context."""
        with tracer.start_as_current_span("databricks_agent.get_or_create_history") as span:
            span.set_attribute("context.id", context_id)
            if context_id not in self.conversations:
                self.conversations[context_id] = []
                logger.info(f'Created new conversation history for context: {context_id}')
                span.set_attribute("history.created", True)
            else:
                span.set_attribute("history.created", False)
            return self.conversations[context_id]

    async def process_message(self, context_id: str, user_message: str) -> dict[str, Any]:
        """Process a user message and return the response.

        Returns:
            dict with 'text' (response text) and optionally other data
        """
        with tracer.start_as_current_span("databricks_agent.process_message") as span:
            span.set_attribute("context.id", context_id)
            span.set_attribute("user_message", user_message[:200])
            span.set_attribute("message.length", len(user_message))

            history = await self.get_or_create_history(context_id)
            logger.info(f'Processing message for context {context_id}: {user_message[:100]}')

            try:
                # Ensure MCP is connected
                mcp_tool = await self._ensure_mcp_connected()

                # Run the agent with MCP tools
                with tracer.start_as_current_span("databricks_agent.invoke_agent") as invoke_span:
                    result = await self.agent.run(user_message, tools=mcp_tool)

                    # Extract response text
                    response_text = result.text if hasattr(result, 'text') else str(result)

                    invoke_span.set_attribute("response.length", len(response_text))
                    span.set_attribute("execution.status", "success")

                    logger.info(f'Generated response for context {context_id}')

                    return {
                        'text': response_text,
                    }

            except Exception as e:
                logger.error(f'Error processing message: {e}', exc_info=True)
                span.set_attribute("execution.status", "error")
                span.set_attribute("error.message", str(e))
                return {
                    'text': f'Error: {str(e)}',
                }

    async def cleanup(self):
        """Clean up agent resources."""
        if self.mcp_tool:
            try:
                await self.mcp_tool.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f'Error closing MCP tool: {e}')
            self.mcp_tool = None

        self.conversations.clear()
        logger.info('Databricks Agent cleaned up')


async def create_databricks_agent() -> DatabricksAgent:
    """Factory function to create and initialize a Databricks Agent."""
    agent = DatabricksAgent()
    return agent


# Example usage for testing
async def demo_databricks_agent():
    """Demo function showing how to use the Databricks Agent."""
    agent = await create_databricks_agent()

    try:
        # Example: Query Databricks
        context_id = 'demo-session'

        test_messages = [
            "What catalogs are available in Databricks?",
            "Can you show me what schemas and tables are in the main catalog?",
            "Can you analyze some sample data from any available tables?",
        ]

        for message in test_messages:
            print(f'\nUser: {message}')
            response = await agent.process_message(context_id, message)
            print(f'Assistant: {response["text"]}')

    finally:
        await agent.cleanup()


if __name__ == '__main__':
    asyncio.run(demo_databricks_agent())