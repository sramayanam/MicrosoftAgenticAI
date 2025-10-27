import logging
import os
import sys
from pathlib import Path

import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from .databricks_agent_executor import create_databricks_agent_executor
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

# Import shared observability configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from observability import configure_observability

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10010)
def main(host: str, port: int) -> None:
    """Run the Databricks A2A Agent server."""
    # Configure observability for the Databricks Agent
    configure_observability(
        service_name="databricks-agent",
        enable_logging=True,
        enable_tracing=True,
        enable_httpx_instrumentation=True,
    )

    # Verify required environment variables
    required_env_vars = [
        'DATABRICKS_MCP_SERVER_URL',
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME',
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f'Missing required environment variables: {", ".join(missing_vars)}'
        )

    # Define agent skills for Databricks Unity Catalog - Bridge Engineering Focus
    skills = [
        AgentSkill(
            id='bridge_standards_query',
            name='Georgia Bridge Standards and Specifications',
            description='Query Georgia DOT bridge design standards, parameters, and compliance requirements from engineeringconn_catalog.bridge schema',
            tags=[
                'bridge',
                'georgia',
                'gdot',
                'standards',
                'design',
                'compliance',
                'specifications',
            ],
            examples=[
                'What are the GDOT bridge design standards?',
                'Show me design parameters for prestressed concrete beams',
                'List all compliance checklist items',
                'What are the design validation rules?',
                'Get design standards for a specific component type',
            ],
        ),
        AgentSkill(
            id='bridge_materials_analysis',
            name='Bridge Materials and Specifications',
            description='Query GDOT-approved materials, specifications, and strength requirements',
            tags=[
                'materials',
                'concrete',
                'steel',
                'gdot',
                'specifications',
                'strength',
            ],
            examples=[
                'What materials are GDOT-approved?',
                'Show me concrete strength specifications',
                'List steel grade specifications',
                'What are the material cover requirements?',
                'Get material properties for corrosive environments',
            ],
        ),
        AgentSkill(
            id='georgia_environmental_factors',
            name='Georgia Regional Environmental Requirements',
            description='Query environmental factors by Georgia region/county including wind, snow, seismic, and frost requirements',
            tags=[
                'environmental',
                'georgia',
                'regional',
                'wind',
                'seismic',
                'frost',
                'salt',
            ],
            examples=[
                'What are the environmental requirements for Fulton County?',
                'Show me design wind speeds by Georgia region',
                'Which regions have salt exposure?',
                'What is the frost line depth for North Georgia?',
                'List all counties with their seismic categories',
            ],
        ),
        AgentSkill(
            id='beam_types_analysis',
            name='Bridge Beam Types and Recommendations',
            description='Query standard Georgia beam types, span recommendations, and specifications',
            tags=[
                'beams',
                'girders',
                'prestressed',
                'span',
                'recommendations',
            ],
            examples=[
                'Show me all standard Georgia beam types',
                'What is the recommended span range for beam type X?',
                'List beams suitable for 100 ft spans',
                'Get typical strand counts for different beam types',
                'What concrete strength is required for beam Y?',
            ],
        ),
        AgentSkill(
            id='bridge_inventory_query',
            name='Bridge Inventory and Engineering Data',
            description='Query bridge inventory, catalog exploration, and general SQL analysis on engineering data',
            tags=[
                'bridges',
                'inventory',
                'catalog',
                'sql',
                'analysis',
            ],
            examples=[
                'List all bridges in the system',
                'Show me tables in the bridge schema',
                'What catalogs are available?',
                'Execute a custom SQL query on bridge data',
                'Get metadata for bridge engineering tables',
            ],
        ),
    ]

    # Create agent card
    agent_card = AgentCard(
        name='Georgia Bridge Engineering Data Agent',
        description='An intelligent bridge engineering agent powered by Microsoft Agent Framework and MCP, '
        'specializing in Georgia DOT bridge standards and specifications. '
        'I provide access to comprehensive bridge engineering data in Databricks Unity Catalog '
        '(engineeringconn_catalog.bridge schema) including: '
        '• GDOT design standards and compliance requirements '
        '• Material specifications and strength requirements '
        '• Georgia regional environmental factors (wind, seismic, frost) '
        '• Standard beam types and span recommendations '
        '• Design parameters and validation rules. '
        'I connect to Databricks through a secure MCP server deployed on Azure via API Management '
        'with JWT authentication. Ask me about Georgia bridge standards, materials, environmental '
        'requirements, or beam specifications.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    # Create agent executor
    agent_executor = create_databricks_agent_executor(agent_card)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor, task_store=InMemoryTaskStore()
    )

    # Create A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    # Get routes
    routes = a2a_app.routes()

    # Add health check endpoint
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse('Databricks Unity Catalog Agent is running!')

    routes.append(Route(path='/health', methods=['GET'], endpoint=health_check))

    # Create Starlette app
    app = Starlette(routes=routes)

    # Log startup information
    logger.info('Starting Databricks Unity Catalog Agent on %s:%s', host, port)
    logger.info('Agent card: %s', agent_card.name)
    logger.info('MCP Server URL: %s', os.getenv('DATABRICKS_MCP_SERVER_URL'))
    logger.info('Skills: %s', [skill.name for skill in skills])
    logger.info('Health check available at: http://%s:%s/health', host, port)

    # Run the server
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()