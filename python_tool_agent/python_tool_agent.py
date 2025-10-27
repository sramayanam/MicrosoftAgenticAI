"""Python Tool Agent implementation using Semantic Kernel.

This agent creates visualizations (charts/graphs) from tabular data using Python code execution
via Azure Container Apps Dynamic Sessions.
"""

import asyncio
import base64
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from opentelemetry import trace
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.core_plugins import SessionsPythonTool
from semantic_kernel.kernel import Kernel

# Import shared observability configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from observability import get_tracer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Get tracer for distributed tracing
tracer = get_tracer(__name__)


class PythonToolAgent:
    """Python Tool Agent that creates visualizations using Semantic Kernel.

    This agent specializes in:
    - Creating charts and graphs from tabular data
    - Executing Python code in a sandboxed environment
    - Returning visualizations as base64-encoded images
    - Generating pandas DataFrames for data analysis
    """

    def __init__(self) -> None:
        """Initialize the Python Tool Agent with Semantic Kernel."""
        # Get Azure OpenAI configuration from environment (for Semantic Kernel)
        self.azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
        if not self.azure_openai_endpoint:
            raise ValueError('AZURE_OPENAI_ENDPOINT environment variable is required')

        self.azure_openai_deployment = os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')
        if not self.azure_openai_deployment:
            raise ValueError('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME environment variable is required')

        self.azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
        if not self.azure_openai_api_key:
            raise ValueError('AZURE_OPENAI_API_KEY environment variable is required')

        session_pool_endpoint = os.environ.get('AZURE_CONTAINER_APP_SESSION_POOL_ENDPOINT')
        if not session_pool_endpoint:
            raise ValueError(
                'AZURE_CONTAINER_APP_SESSION_POOL_ENDPOINT environment variable is required'
            )

        # Create Azure credential for session pool
        logger.info('Initializing Azure credentials for session pool...')
        try:
            # Use DefaultAzureCredential which tries multiple auth methods
            logger.info('Using DefaultAzureCredential (tries multiple auth methods)')
            self.credential = DefaultAzureCredential()

            # Test the credential with appropriate scope for Container Apps
            logger.info('Testing Azure authentication...')
            self.credential.get_token('https://management.azure.com/.default')
            logger.info('✅ Azure authentication successful!')
        except Exception as e:
            logger.error(f'❌ Azure authentication failed: {e}')
            logger.info("Please ensure proper credentials are configured (az login, service principal, managed identity, etc.)")
            raise

        # Create Semantic Kernel
        self.kernel = Kernel()

        # Add Azure OpenAI chat completion service using API key
        self.chat_service = AzureChatCompletion(
            endpoint=self.azure_openai_endpoint,
            deployment_name=self.azure_openai_deployment,
            api_key=self.azure_openai_api_key
        )
        self.kernel.add_service(self.chat_service)

        # Initialize SessionsPythonTool for code execution
        self.python_tool = SessionsPythonTool(
            pool_management_endpoint=session_pool_endpoint,
            credential=self.credential
        )

        # Create ChatCompletionAgent
        self.agent = ChatCompletionAgent(
            name="PythonToolAgent",
            description="Creates visualizations (charts/graphs) from tabular data using Python code execution",
            instructions=(
                "You are a visualization specialist with Python code execution capabilities.\n\n"
                "**Your Capabilities:**\n"
                "1. Create charts and graphs from data using matplotlib, pandas, seaborn\n"
                "2. Execute Python code in a secure sandboxed environment\n"
                "3. Perform data analysis and transformations\n"
                "4. Generate tables and statistics\n\n"
                "**When creating visualizations:**\n"
                "1. Extract data from the user's message (markdown tables, CSV, or raw data)\n"
                "2. Write clean Python code using matplotlib/pandas\n"
                "3. ALWAYS EXECUTE the code using the Python tool (don't just show code)\n"
                "4. Save charts to /mnt/data/ with descriptive filenames\n"
                "5. The chart will be automatically captured and returned\n\n"
                "**Example code structure:**\n"
                "```python\n"
                "import matplotlib.pyplot as plt\n"
                "import pandas as pd\n\n"
                "# Your data here\n"
                "data = {'x': [1,2,3], 'y': [4,5,6]}\n"
                "df = pd.DataFrame(data)\n\n"
                "# Create visualization\n"
                "plt.figure(figsize=(10,6))\n"
                "plt.plot(df['x'], df['y'])\n"
                "plt.xlabel('X Label')\n"
                "plt.ylabel('Y Label')\n"
                "plt.title('Chart Title')\n"
                "plt.grid(True, alpha=0.3)\n"
                "plt.savefig('/mnt/data/output.png', dpi=150, bbox_inches='tight')\n"
                "plt.show()\n"
                "```\n\n"
                "**Output Modes:**\n"
                "- If user asks for visualization: Execute code and return the image\n"
                "- If user asks for code: Show the Python code\n"
                "- If user asks for analysis: Execute code and return results/tables\n\n"
                "**Important:**\n"
                "- ALWAYS execute code unless user explicitly asks to see code only\n"
                "- Use descriptive filenames for saved charts\n"
                "- Handle errors gracefully and suggest fixes\n"
                "- For complex visualizations, break into steps if needed"
            ),
            kernel=self.kernel,
            arguments=None,
        )

        # Add the Python tool as a plugin
        self.kernel.add_plugin(self.python_tool, plugin_name="SessionsPythonTool")

        # Initialize chat history
        self.conversations: dict[str, ChatHistory] = {}

        logger.info('Python Tool Agent initialized successfully')

    async def get_or_create_history(self, context_id: str) -> ChatHistory:
        """Get or create chat history for a context."""
        with tracer.start_as_current_span("python_tool_agent.get_or_create_history") as span:
            span.set_attribute("context.id", context_id)
            if context_id not in self.conversations:
                self.conversations[context_id] = ChatHistory()
                logger.info(f'Created new chat history for context: {context_id}')
                span.set_attribute("history.created", True)
            else:
                span.set_attribute("history.created", False)
            return self.conversations[context_id]

    async def process_message(self, context_id: str, user_message: str) -> dict[str, Any]:
        """Process a user message and return the response.

        Returns:
            dict with 'text' (response text) and optionally 'image' (base64 encoded image)
        """
        with tracer.start_as_current_span("python_tool_agent.process_message") as span:
            span.set_attribute("context.id", context_id)
            span.set_attribute("user_message", user_message[:200])
            span.set_attribute("message.length", len(user_message))

            history = await self.get_or_create_history(context_id)

            # Add user message to history
            history.add_user_message(user_message)
            logger.info(f'Processing message for context {context_id}: {user_message[:100]}')

            try:
                # Invoke the agent - returns an async generator
                response_messages = []
                with tracer.start_as_current_span("python_tool_agent.invoke_agent") as invoke_span:
                    async for message in self.agent.invoke(history):
                        response_messages.append(message)
                        # Only add properly formatted messages to history
                        if isinstance(message, ChatMessageContent):
                            history.add_message(message)
                        elif isinstance(message, str):
                            # Convert string responses to proper ChatMessageContent
                            history.add_assistant_message(message)
                        else:
                            logger.warning(f'Unexpected message type: {type(message)}')
                        logger.debug(f'Received message from agent: {type(message)}')

                    invoke_span.set_attribute("response.message_count", len(response_messages))

                # Get the last message as the primary response
                last_message = response_messages[-1] if response_messages else None

                # Extract response content
                result = {
                    'text': '',
                    'images': [],
                    'code': None,
                }

                if last_message:
                    # Extract text content - handle AgentResponseItem
                    if isinstance(last_message, str):
                        result['text'] = last_message
                    elif hasattr(last_message, 'content') and isinstance(last_message.content, str):
                        result['text'] = last_message.content
                    elif hasattr(last_message, 'text'):
                        result['text'] = last_message.text
                    elif hasattr(last_message, 'items'):
                        # AgentResponseItem has items list with text content
                        text_parts = []
                        for item in last_message.items:
                            if hasattr(item, 'text'):
                                text_parts.append(item.text)
                        result['text'] = '\n'.join(text_parts) if text_parts else str(last_message)
                    else:
                        result['text'] = str(last_message)

                    # Log the full message structure for debugging
                    logger.debug(f'Last message type: {type(last_message)}')
                    logger.debug(f'Last message content: {result["text"][:200] if result["text"] else "empty"}')

                    # Extract any images from items
                    if hasattr(last_message, 'items'):
                        for item in last_message.items:
                            logger.debug(f'Item type: {type(item)}, attributes: {dir(item)}')
                            # Check for file items from SessionsPythonTool
                            if hasattr(item, 'get') and callable(item.get):
                                # Dictionary-like item
                                if 'mime_type' in item and 'data' in item:
                                    if 'image' in item.get('mime_type', ''):
                                        result['images'].append({
                                            'data': item['data'],
                                            'mime_type': item['mime_type'],
                                        })
                            elif hasattr(item, 'data') and hasattr(item, 'mime_type'):
                                if 'image' in item.mime_type:
                                    result['images'].append({
                                        'data': item.data,
                                        'mime_type': item.mime_type,
                                    })

                    # Also check for file annotations in content
                    if hasattr(last_message, 'annotations'):
                        for annotation in last_message.annotations:
                            logger.debug(f'Annotation: {annotation}')

                # Extract files from SessionsPythonTool execution (look for /mnt/data/ paths)
                file_paths = []

                # Search through response_messages (agent responses) not history
                logger.info(f'Searching through {len(response_messages)} response messages for file paths')
                for idx, msg in enumerate(response_messages):
                    msg_content = ''
                    msg_name = ''
                    msg_role = ''

                    # Handle different message types
                    if isinstance(msg, str):
                        msg_content = msg
                    elif hasattr(msg, 'content'):
                        msg_content = str(msg.content)
                    elif hasattr(msg, 'text'):
                        msg_content = str(msg.text)

                    if hasattr(msg, 'name'):
                        msg_name = str(msg.name)
                    if hasattr(msg, 'role'):
                        msg_role = str(msg.role)

                    # Debug: Log all messages to understand structure
                    logger.debug(f'Response message {idx}: role={msg_role}, name={msg_name}, has_content={bool(msg_content)}, content_length={len(msg_content)}')

                    # Look for /mnt/data/ paths in tool outputs or any message
                    if '/mnt/data/' in msg_content:
                        logger.info(f'✨ Found /mnt/data/ in response message {idx} (name={msg_name}, role={msg_role})')
                        logger.debug(f'Message content: {msg_content[:500]}')
                        # Find file paths in the output
                        file_path_pattern = r'/mnt/data/([a-zA-Z0-9_\-.]+\.(?:png|jpg|jpeg|gif|svg|pdf))'
                        found_filenames = re.findall(file_path_pattern, msg_content)
                        for filename in found_filenames:
                            if filename not in file_paths:
                                file_paths.append(filename)
                                logger.info(f'📊 Detected generated file: {filename}')

                logger.info(f'Total files to download: {file_paths}')

                # Download files from the session with retry logic
                for file_path in file_paths:
                    try:
                        logger.info(f'Attempting to download file: {file_path}')
                        # Use SessionsPythonTool to download the file
                        # file_path should just be the filename (not full path)
                        file_name = file_path  # Already just the filename from regex

                        # Retry logic for file download (handle timing issues with session storage)
                        max_retries = 3
                        retry_delay = 1.0  # seconds
                        file_data_io = None

                        for attempt in range(max_retries):
                            try:
                                # download_file returns BytesIO | None
                                file_data_io = await self.python_tool.download_file(remote_file_name=file_name)
                                if file_data_io:
                                    logger.info(f'✅ File downloaded successfully on attempt {attempt + 1}')
                                    break
                            except Exception as download_error:
                                if attempt < max_retries - 1:
                                    logger.warning(f'Download attempt {attempt + 1} failed for {file_name}: {download_error}. Retrying in {retry_delay}s...')
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                else:
                                    logger.error(f'Failed to download {file_name} after {max_retries} attempts: {download_error}')
                                    raise

                        if file_data_io:
                            # Read bytes from BytesIO
                            file_bytes = file_data_io.read() if hasattr(file_data_io, 'read') else file_data_io

                            # Determine mime type from extension
                            if file_name.endswith('.png'):
                                mime_type = 'image/png'
                            elif file_name.endswith(('.jpg', '.jpeg')):
                                mime_type = 'image/jpeg'
                            elif file_name.endswith('.gif'):
                                mime_type = 'image/gif'
                            elif file_name.endswith('.svg'):
                                mime_type = 'image/svg+xml'
                            elif file_name.endswith('.pdf'):
                                mime_type = 'application/pdf'
                            else:
                                mime_type = 'image/png'

                            # Convert bytes to base64
                            image_b64 = base64.b64encode(file_bytes).decode('utf-8')

                            result['images'].append({
                                'data': image_b64,
                                'mime_type': mime_type,
                            })
                            logger.info(f'✅ Successfully downloaded file: {file_name} ({len(file_bytes)} bytes)')
                        else:
                            logger.warning(f'download_file returned None for {file_name}')
                    except Exception as e:
                        logger.error(f'Failed to download file {file_path}: {e}', exc_info=True)

                logger.info(f'Generated response with {len(result["images"])} images')
                span.set_attribute("result.image_count", len(result["images"]))
                span.set_attribute("result.has_code", bool(result.get("code")))
                span.set_attribute("result.text_length", len(result.get("text", "")))
                span.set_attribute("execution.status", "success")
                return result

            except Exception as e:
                logger.error(f'Error processing message: {e}', exc_info=True)
                span.set_attribute("execution.status", "error")
                span.set_attribute("error.message", str(e))
                return {
                    'text': f'Error: {str(e)}',
                    'images': [],
                    'code': None,
                }

    async def cleanup(self):
        """Clean up agent resources."""
        self.conversations.clear()
        logger.info('Python Tool Agent cleaned up')


async def create_python_tool_agent() -> PythonToolAgent:
    """Factory function to create and initialize a Python Tool Agent."""
    agent = PythonToolAgent()
    return agent


# Example usage for testing
async def demo_python_tool_agent():
    """Demo function showing how to use the Python Tool Agent."""
    agent = await create_python_tool_agent()

    try:
        # Example: Create a simple visualization
        context_id = 'demo-session'

        test_messages = [
            "Create a bar chart showing these values: Category A: 25, Category B: 40, Category C: 30, Category D: 35",
            "Now create a pie chart with the same data",
            "Show me the Python code you would use to create a line chart",
        ]

        for message in test_messages:
            print(f'\nUser: {message}')
            response = await agent.process_message(context_id, message)
            print(f'Assistant: {response["text"]}')
            if response['images']:
                print(f'Generated {len(response["images"])} image(s)')
                for idx, img in enumerate(response['images']):
                    print(f'  - Image {idx + 1}: {img["mime_type"]}')

    finally:
        await agent.cleanup()


if __name__ == '__main__':
    asyncio.run(demo_python_tool_agent())
