import logging
import os

import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from .sql_foundry_agent_executor import create_sql_foundry_agent_executor
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10008)
def main(host: str, port: int) -> None:
    """Run the SQL Foundry A2A Agent server."""
    # Verify required environment variables
    required_env_vars = [
        'PROJECT_ENDPOINT',
        'AZURE_AI_FOUNDRY_AGENT_ID',
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f'Missing required environment variables: {", ".join(missing_vars)}'
        )

    # Define agent skills for bridge engineering database
    skills = [
        AgentSkill(
            id='bridge_beam_analysis',
            name='Bridge Beam Analysis',
            description='Query and analyze bridge beam specifications, including strand counts, concrete strengths, and span lengths',
            tags=[
                'bridge',
                'beam',
                'girder',
                'prestressed',
                'concrete',
                'strands',
            ],
            examples=[
                'Show me all beams for Bridge 1001',
                'What is the total span length for Bridge 1001?',
                'Are there any beams with release strength less than 5000 psi?',
                'Which spans have more than 72 strands?',
                'Calculate strand efficiency for all Bridge 1001 spans',
                'Which Bridge 1001 spans have draped strands?',
            ],
        ),
        AgentSkill(
            id='bridge_structural_components',
            name='Bridge Structural Components Analysis',
            description='Query end bents, interior bents, and deck information for bridge structures',
            tags=['bridge', 'bent', 'abutment', 'deck', 'rebar', 'concrete'],
            examples=[
                'Show me all end bent information for Bridge 1001',
                'List all interior bents for Bridge 1001',
                'Calculate rebar density for all interior bents in Bridge 1001',
                'Show deck information for all spans in Bridge 1001',
                'What is the total concrete volume needed for Bridge 1001?',
                'Compare cap beam depths across all bents in Bridge 1001',
            ],
        ),
        AgentSkill(
            id='design_standards_compliance',
            name='Design Standards and Compliance',
            description='Query design standards, compliance checklists, validation rules, and material specifications',
            tags=[
                'standards',
                'compliance',
                'validation',
                'materials',
                'gdot',
                'regulations',
            ],
            examples=[
                'Show all design standards loaded',
                'Show all CRITICAL severity compliance items',
                'What materials are GDOT-approved?',
                'Show all concrete specifications',
                'What are all design parameters?',
                'Show all design validation rules',
            ],
        ),
        AgentSkill(
            id='bridge_engineering_analytics',
            name='Bridge Engineering Analytics and Reporting',
            description='Provide comprehensive analytics, comparisons, and reports for bridge engineering data',
            tags=[
                'analytics',
                'reporting',
                'comparison',
                'efficiency',
                'cost',
                'optimization',
            ],
            examples=[
                'Compare Bridge 1001 and Bridge 1002 span counts',
                'Show Bridge 1001 material requirements summary',
                'What is the most economical beam type?',
                'Show environmental requirements for all Georgia regions',
                'Compare all interior bents in Bridge 1001 by rebar density',
                'Get minimum and maximum values for key bridge parameters',
            ],
        ),
        AgentSkill(
            id='environmental_factors',
            name='Environmental Factors and Regional Requirements',
            description='Query environmental factors, regional design requirements, and location-specific standards',
            tags=[
                'environment',
                'regional',
                'wind',
                'seismic',
                'salt',
                'frost',
                'georgia',
            ],
            examples=[
                'What are the design requirements for Atlanta (Fulton County)?',
                'Which Georgia regions have salt exposure?',
                'What is the frost line depth requirement for North Georgia?',
                'Show environmental requirements for all Georgia regions',
                'Which regions require the deepest frost line depth?',
            ],
        ),
    ]

    # Create agent card
    agent_card = AgentCard(
        name='Bridge Engineering SQL Agent',
        description='An intelligent bridge engineering SQL agent powered by Azure AI Foundry. '
        'I specialize in querying bridge engineering databases including beam specifications, '
        'structural components, design standards, compliance requirements, and GDOT materials. '
        'I can analyze bridge data, calculate engineering metrics, and provide comprehensive '
        'reports for bridge design and construction projects using natural language queries.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    # Create agent executor
    agent_executor = create_sql_foundry_agent_executor(agent_card)

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
        return PlainTextResponse('Bridge Engineering SQL Agent is running!')

    routes.append(Route(path='/health', methods=['GET'], endpoint=health_check))

    # Create Starlette app
    app = Starlette(routes=routes)

    # Log startup information
    logger.info('Starting Bridge Engineering SQL Agent on %s:%s', host, port)
    logger.info('Agent card: %s', agent_card.name)
    logger.info('Agent ID: %s', os.getenv('AZURE_AI_FOUNDRY_AGENT_ID'))
    logger.info('Endpoint: %s', os.getenv('PROJECT_ENDPOINT'))
    logger.info('Skills: %s', [skill.name for skill in skills])
    logger.info('Health check available at: http://%s:%s/health', host, port)

    # Run the server
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()
