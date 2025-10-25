import logging
import os

import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from .python_tool_agent_executor import create_python_tool_agent_executor
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10009)
def main(host: str, port: int) -> None:
    """Run the Python Tool A2A Agent server."""
    # Verify required environment variables
    required_env_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME',
        'AZURE_OPENAI_API_KEY',
        'AZURE_CONTAINER_APP_SESSION_POOL_ENDPOINT',
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f'Missing required environment variables: {", ".join(missing_vars)}'
        )

    # Define agent skills for Python visualization and data analysis
    skills = [
        AgentSkill(
            id='data_visualization',
            name='Data Visualization',
            description='Create charts, graphs, and plots from tabular data using Python (matplotlib, seaborn, pandas)',
            tags=[
                'visualization',
                'charts',
                'graphs',
                'matplotlib',
                'pandas',
                'plotting',
            ],
            examples=[
                'Create a bar chart showing sales by region',
                'Generate a line graph of monthly revenue trends',
                'Make a pie chart of market share distribution',
                'Plot a scatter chart correlating price vs demand',
                'Create a histogram of age distribution',
                'Draw a heatmap showing correlation between variables',
            ],
        ),
        AgentSkill(
            id='data_analysis',
            name='Data Analysis and Transformation',
            description='Perform data analysis, statistical calculations, and transformations using pandas and numpy',
            tags=[
                'analysis',
                'statistics',
                'pandas',
                'numpy',
                'dataframe',
                'transformation',
            ],
            examples=[
                'Calculate mean, median, and standard deviation',
                'Group data by category and compute aggregates',
                'Filter and sort data based on conditions',
                'Merge and join multiple datasets',
                'Compute correlations between variables',
                'Generate summary statistics for the dataset',
            ],
        ),
        AgentSkill(
            id='code_generation',
            name='Python Code Generation',
            description='Generate Python code snippets for data manipulation, analysis, and visualization',
            tags=['python', 'code', 'snippets', 'generation', 'examples'],
            examples=[
                'Show me the Python code to create this chart',
                'Generate code to read CSV and create a DataFrame',
                'Write Python code to calculate moving averages',
                'Create a code example for data normalization',
                'Show code for creating interactive plots',
            ],
        ),
        AgentSkill(
            id='advanced_visualizations',
            name='Advanced Visualizations',
            description='Create complex multi-panel visualizations, subplots, and advanced chart types',
            tags=[
                'advanced',
                'subplots',
                'multi-panel',
                'complex',
                'dashboard',
            ],
            examples=[
                'Create a dashboard with 4 different charts',
                'Generate subplots comparing multiple metrics',
                'Build a multi-panel visualization grid',
                'Create a chart with dual Y-axes',
                'Make a combined bar and line chart',
                'Generate a time series plot with annotations',
            ],
        ),
    ]

    # Create agent card
    agent_card = AgentCard(
        name='Python Tool Visualization Agent',
        description='An intelligent Python-powered visualization agent using Semantic Kernel. '
        'I specialize in creating charts, graphs, and plots from data using Python code execution '
        'in a secure sandboxed environment. I can generate bar charts, line graphs, pie charts, '
        'scatter plots, heatmaps, and more. I can also perform data analysis, transformations, '
        'and statistical calculations using pandas and numpy. All code runs in Azure Container Apps '
        'Dynamic Sessions for secure, isolated execution.',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text', 'image'],
        capabilities=AgentCapabilities(streaming=True),
        skills=skills,
    )

    # Create agent executor
    agent_executor = create_python_tool_agent_executor(agent_card)

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
        return PlainTextResponse('Python Tool Visualization Agent is running!')

    routes.append(Route(path='/health', methods=['GET'], endpoint=health_check))

    # Create Starlette app
    app = Starlette(routes=routes)

    # Log startup information
    logger.info('Starting Python Tool Visualization Agent on %s:%s', host, port)
    logger.info('Agent card: %s', agent_card.name)
    logger.info('Session Pool: %s', os.getenv('AZURE_CONTAINER_APP_SESSION_POOL_ENDPOINT'))
    logger.info('Skills: %s', [skill.name for skill in skills])
    logger.info('Health check available at: http://%s:%s/health', host, port)

    # Run the server
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()
