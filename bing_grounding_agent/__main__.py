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
from .bing_grounding_agent_executor import create_bing_grounding_agent_executor
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
@click.option('--port', 'port', default=10011)
def main(host: str, port: int) -> None:
    """Run the Bing Grounding A2A Agent server."""
    # Configure observability for the Bing Grounding Agent
    configure_observability(
        service_name="bing-grounding-agent",
        enable_logging=True,
        enable_tracing=True,
        enable_httpx_instrumentation=True,
    )

    # Verify required environment variables
    required_env_vars = [
        'PROJECT_ENDPOINT',
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f'Missing required environment variables: {", ".join(missing_vars)}'
        )

    # Define agent skills for costing and market price analysis
    skills = [
        AgentSkill(
            id='construction_material_pricing',
            name='Construction Material Pricing',
            description='Query current market prices and costs for construction materials including steel, concrete, rebar, and other building materials',
            tags=[
                'pricing',
                'materials',
                'steel',
                'concrete',
                'rebar',
                'cost',
                'market',
            ],
            examples=[
                'What is the current market price for structural steel in the United States?',
                'What are typical costs for concrete per cubic yard?',
                'What are the latest prices for rebar and reinforcement materials?',
                'How much does prestressed concrete cost per square foot?',
                'What are current prices for bridge construction materials?',
            ],
        ),
        AgentSkill(
            id='construction_cost_analysis',
            name='Construction Cost Analysis',
            description='Analyze construction costs, budgeting, and cost comparisons for bridge engineering projects',
            tags=[
                'cost',
                'budget',
                'analysis',
                'comparison',
                'estimation',
                'bridge',
            ],
            examples=[
                'What are typical costs for bridge construction per square foot?',
                'How do construction material costs compare between 2023 and 2024?',
                'What is the cost breakdown for a prestressed concrete bridge?',
                'Compare costs between steel and concrete bridge construction',
                'What are labor cost trends in bridge construction?',
            ],
        ),
        AgentSkill(
            id='market_trends_forecasting',
            name='Market Trends and Forecasting',
            description='Research market trends, price forecasts, and economic factors affecting construction costs',
            tags=[
                'trends',
                'forecast',
                'market',
                'economic',
                'inflation',
                'supply',
            ],
            examples=[
                'What are the price trends for construction materials in 2024?',
                'How is inflation affecting bridge construction costs?',
                'What are the supply chain impacts on material pricing?',
                'What is the forecast for steel prices in the next quarter?',
                'How do commodity prices affect bridge construction budgets?',
            ],
        ),
        AgentSkill(
            id='vendor_supplier_information',
            name='Vendor and Supplier Information',
            description='Find information about construction material vendors, suppliers, and availability',
            tags=[
                'vendors',
                'suppliers',
                'availability',
                'sourcing',
                'procurement',
            ],
            examples=[
                'Who are the major structural steel suppliers in the United States?',
                'What suppliers provide GDOT-approved materials?',
                'Which vendors offer prestressed concrete beams?',
                'What are lead times for bridge construction materials?',
                'Who manufactures high-strength concrete for bridges?',
            ],
        ),
        AgentSkill(
            id='regulatory_compliance_costs',
            name='Regulatory Compliance and Certification Costs',
            description='Research costs related to regulatory compliance, certifications, and standards for construction materials',
            tags=[
                'compliance',
                'certification',
                'regulations',
                'standards',
                'testing',
            ],
            examples=[
                'What are the costs for material testing and certification?',
                'How much does GDOT material approval cost?',
                'What are compliance costs for bridge construction standards?',
                'What are testing requirements and costs for concrete strength?',
                'How much does environmental compliance add to project costs?',
            ],
        ),
    ]

    # Create agent card
    agent_card = AgentCard(
        name='Bing Grounding Costing Agent',
        description='An intelligent costing and market pricing agent powered by Azure AI Foundry with Bing search grounding. '
        'I specialize in researching current market prices, construction costs, material pricing trends, '
        'vendor information, and economic factors affecting bridge construction projects. '
        'I use real-time Bing search to provide up-to-date pricing information and market intelligence '
        'for construction materials, labor costs, and project budgeting.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    # Create agent executor
    agent_executor = create_bing_grounding_agent_executor(agent_card)

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
        return PlainTextResponse('Bing Grounding Costing Agent is running!')

    routes.append(Route(path='/health', methods=['GET'], endpoint=health_check))

    # Create Starlette app
    app = Starlette(routes=routes)

    # Log startup information
    logger.info('Starting Bing Grounding Costing Agent on %s:%s', host, port)
    logger.info('Agent card: %s', agent_card.name)
    logger.info('Agent ID: %s', os.getenv('BING_GROUNDING_AGENT_ID', 'asst_QZZuly3q633MzDQyWUphMfgw'))
    logger.info('Endpoint: %s', os.getenv('PROJECT_ENDPOINT'))
    logger.info('Skills: %s', [skill.name for skill in skills])
    logger.info('Health check available at: http://%s:%s/health', host, port)

    # Run the server
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()
