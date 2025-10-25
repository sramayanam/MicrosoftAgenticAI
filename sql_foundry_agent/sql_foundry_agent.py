"""SQL Foundry Agent implementation that wraps an existing Azure AI Foundry agent.

This agent converts natural language to SQL queries and executes them using Azure SDK with DefaultAzureCredential.
"""

import asyncio
import logging
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SQLFoundryAgent:
    """SQL Foundry Agent that wraps an existing Azure AI Foundry agent.

    This agent specializes in converting natural language to SQL queries and executing them.
    """

    def __init__(self) -> None:
        # Get configuration from environment - use PROJECT_ENDPOINT like the example
        project_endpoint = os.environ.get('PROJECT_ENDPOINT')
        if not project_endpoint:
            raise ValueError(
                'PROJECT_ENDPOINT environment variable is required'
            )

        self.agent_id = os.environ.get('AZURE_AI_FOUNDRY_AGENT_ID')
        if not self.agent_id:
            raise ValueError(
                'AZURE_AI_FOUNDRY_AGENT_ID environment variable is required'
            )

        # Create Azure credential with proper error handling
        logger.info(
            'Initializing Azure DefaultAzureCredential - you may need to authenticate...'
        )
        try:
            self.credential = DefaultAzureCredential()
            # Test the credential by getting a token (this will trigger auth flow)
            logger.info('Testing Azure authentication...')
            token = self.credential.get_token('https://ml.azure.com/.default')
            logger.info('Azure authentication successful!')
        except Exception as e:
            logger.error(f'Azure authentication failed: {e}')
            logger.info(
                "Please ensure you are logged in with 'az login' or provide proper credentials"
            )
            raise

        # Create Azure AI Project client with authenticated credential
        self.client = AIProjectClient(
            endpoint=project_endpoint,
            credential=self.credential,
        )

        self.agent = None
        self.threads: dict[str, str] = {}  # context_id -> thread_id mapping

    async def get_agent(self) -> dict:
        """Get the existing AI Foundry agent by ID."""
        if self.agent:
            return self.agent

        # Get agent using Azure SDK
        agent = self.client.agents.get_agent(self.agent_id)
        self.agent = (
            agent.model_dump()
            if hasattr(agent, 'model_dump')
            else agent.__dict__
        )
        logger.info('Retrieved AI Foundry SQL agent: %s', self.agent_id)
        return self.agent

    async def create_thread(self, context_id: str | None = None) -> dict:
        """Create a new thread for conversation."""
        thread_id = context_id or f'thread_{asyncio.current_task().get_name()}'

        if thread_id in self.threads:
            return {'id': self.threads[thread_id]}

        # Create thread using Azure SDK - correct API path
        thread = self.client.agents.threads.create()

        # Get the thread ID from the object
        actual_thread_id = getattr(thread, 'id', None)
        if not actual_thread_id:
            # Try alternative ways to get the ID
            if hasattr(thread, 'model_dump'):
                thread_dict = thread.model_dump()
            else:
                thread_dict = thread.__dict__
            actual_thread_id = thread_dict.get('id') or thread_dict.get(
                'thread_id'
            )

        if not actual_thread_id:
            raise ValueError(
                'Could not extract thread ID from Azure SDK response'
            )

        # Store the mapping and create return data
        self.threads[thread_id] = actual_thread_id
        thread_data = {'id': actual_thread_id}
        logger.info('Created thread: %s', actual_thread_id)
        return thread_data

    async def send_message(self, thread_id: str, message: str) -> dict:
        """Send a message to the agent in the specified thread."""
        # Send message using Azure SDK
        message_obj = self.client.agents.messages.create(
            thread_id=thread_id, role='user', content=message
        )
        message_data = (
            message_obj.model_dump()
            if hasattr(message_obj, 'model_dump')
            else message_obj.__dict__
        )
        logger.info('Sent message to thread %s: %s', thread_id, message[:100])
        return message_data

    async def run_conversation(
        self, thread_id: str, user_message: str
    ) -> list[str]:
        """Run a complete conversation cycle with the SQL agent."""
        if not self.agent:
            await self.get_agent()

        # Send user message
        await self.send_message(thread_id, user_message)

        # Create and run the agent using Azure SDK
        run = self.client.agents.runs.create(
            thread_id=thread_id, agent_id=self.agent_id
        )

        # Poll until completion
        max_iterations = 60  # Increased timeout for SQL operations
        iterations = 0

        while (
            run.status in ['queued', 'in_progress', 'requires_action']
            and iterations < max_iterations
        ):
            iterations += 1
            await asyncio.sleep(2)  # Slightly longer wait for SQL operations

            # Get run status using Azure SDK
            run = self.client.agents.runs.get(
                thread_id=thread_id, run_id=run.id
            )

            logger.debug(
                'Run status: %s (iteration %d)',
                run.status,
                iterations,
            )

            if run.status == 'failed':
                logger.error('Run failed during polling: %s', run.last_error)
                break

            # Handle tool calls if needed (your SQL agent might use tools)
            if run.status == 'requires_action':
                logger.info(
                    'SQL agent requires action - letting it handle internally'
                )
                # Your existing SQL agent should handle tool calls internally
                continue

        if run.status == 'failed':
            error_msg = run.last_error or 'Unknown error'
            logger.error('SQL Run failed: %s', error_msg)
            return [f'Error executing SQL query: {error_msg}']

        logger.info('Final run status: %s', run.status)

        if iterations >= max_iterations:
            logger.error(
                'SQL Run timed out after %d iterations', max_iterations
            )
            return [
                'Error: SQL query execution timed out. Please try a simpler query.'
            ]

        # Get response messages using Azure SDK
        logger.info('About to fetch messages from thread: %s', thread_id)
        messages = self.client.agents.messages.list(thread_id=thread_id)
        logger.info('Fetched messages, type: %s', type(messages))

        responses = []
        all_messages = []

        # ItemPaged object needs to be iterated directly
        for msg in messages:
            all_messages.append(f'Role: {msg.role}, Content: {msg.content}')
            if msg.role == 'assistant' and msg.content:
                for content_item in msg.content:
                    if hasattr(content_item, 'text') and hasattr(
                        content_item.text, 'value'
                    ):
                        responses.append(content_item.text.value)
                        logger.debug(
                            'Found assistant response: %s',
                            content_item.text.value,
                        )

        logger.debug('All messages in thread: %s', all_messages)
        logger.debug('Assistant responses found: %s', responses)

        return (
            responses
            if responses
            else ['No SQL results received from Azure AI Foundry agent']
        )

    async def cleanup_agent(self):
        """Clean up the agent resources."""
        # Note: We don't delete the agent since it's an existing one
        # Just clear our local references
        self.agent = None
        self.threads.clear()
        logger.info('SQL Foundry agent wrapper cleaned up')


async def create_sql_foundry_agent() -> SQLFoundryAgent:
    """Factory function to create and initialize a SQL Foundry agent wrapper."""
    agent = SQLFoundryAgent()
    await agent.get_agent()
    return agent


# Example usage for testing
async def demo_sql_agent_interaction():
    """Demo function showing how to use the SQL Foundry agent."""
    agent = await create_sql_foundry_agent()

    try:
        # Create a conversation thread
        thread = await agent.create_thread()

        # Example bridge engineering SQL queries
        test_messages = [
            'Hello! Can you help me with bridge engineering queries?',
            'Show me all beams for Bridge 1001',
            'What is the total span length for Bridge 1001?',
            'Which spans have more than 72 strands?',
            'Show me all end bent information for Bridge 1001',
        ]

        for message in test_messages:
            print(f'\nUser: {message}')
            responses = await agent.run_conversation(thread.id, message)
            for response in responses:
                print(f'Assistant: {response}')

    finally:
        await agent.cleanup_agent()


if __name__ == '__main__':
    import asyncio

    asyncio.run(demo_sql_agent_interaction())
