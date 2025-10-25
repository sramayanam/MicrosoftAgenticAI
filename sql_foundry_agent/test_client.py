"""Simple test client for the SQL Foundry Agent.

This client demonstrates how to interact with the SQL agent using the A2A protocol.
"""

import asyncio

from uuid import uuid4

import click
import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    SendStreamingMessageRequest,
    TaskStatusUpdateEvent,
    TextPart,
)
from dotenv import load_dotenv


load_dotenv()


@click.command()
@click.option('--agent-url', default='http://localhost:10008')
@click.option('--query', required=True, help='SQL query in natural language')
async def test_sql_agent(agent_url: str, query: str) -> None:
    """Test the SQL Foundry Agent with a natural language query."""
    # Increase timeout for Azure AI Foundry operations
    timeout = httpx.Timeout(timeout=120.0, read=120.0, write=30.0)
    async with httpx.AsyncClient(timeout=timeout) as httpx_client:
        try:
            # Get the agent card using resolver
            print(f'Connecting to SQL agent at {agent_url}...')
            card_resolver = A2ACardResolver(httpx_client, agent_url)
            agent_card = await card_resolver.get_agent_card()

            print('✅ Successfully connected to SQL agent')
            print(f'Agent: {agent_card.name}')
            print(f'Description: {agent_card.description}')
            print(f'Skills: {[skill.name for skill in agent_card.skills]}')
            print()

            # Create A2A client
            client = A2AClient(httpx_client, agent_card=agent_card)

            # Send the query
            print(f'Sending query: {query}')
            print('=' * 50)

            # Use streaming if supported
            if agent_card.capabilities.streaming:
                # Create message with text part (let server handle task creation)
                context_id = str(uuid4())
                message = Message(
                    role='user',
                    parts=[TextPart(text=query)],
                    message_id=str(uuid4()),
                    context_id=context_id,
                )

                # Create streaming request
                payload = MessageSendParams(
                    id=str(uuid4()),
                    message=message,
                    configuration=MessageSendConfiguration(
                        accepted_output_modes=['text']
                    ),
                )
                response_stream = client.send_message_streaming(
                    SendStreamingMessageRequest(
                        id=str(uuid4()),
                        params=payload,
                    )
                )

                # Process streaming response
                async for result in response_stream:
                    if isinstance(result.root, JSONRPCErrorResponse):
                        print(f'❌ Error: {result.root.error}')
                        break

                    event = result.root.result
                    if isinstance(event, Message):
                        print(f'[DEBUG] Message event: {event}')
                        for part in event.parts:
                            print(f'[DEBUG] Message part: {part}')
                            if hasattr(part, 'content'):
                                print(part.content, end='', flush=True)
                    elif isinstance(event, TaskStatusUpdateEvent):
                        # Extract and print message content from status updates
                        if event.status.message:
                            for part in event.status.message.parts:
                                if hasattr(part.root, 'text'):
                                    print(part.root.text)
                        if event.status.state == 'completed':
                            break
            else:
                # Fallback to non-streaming (not implemented in this example)
                print('Non-streaming not implemented in this test client')

            print('\n' + '=' * 50)
            print('✅ Query completed')

        except Exception as e:
            print(f'❌ Error: {e}')
            raise


def main() -> None:
    """Main function to run the test client."""
    asyncio.run(test_sql_agent.main(standalone_mode=False))


if __name__ == '__main__':
    main()
