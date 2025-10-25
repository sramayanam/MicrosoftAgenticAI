"""Simple test client for the Python Tool Agent.

This client demonstrates how to interact with the Python Tool agent using the A2A protocol.
"""

import asyncio
import base64
from pathlib import Path
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
@click.option('--agent-url', default='http://localhost:10009')
@click.option('--query', required=True, help='Request for Python Tool Agent (e.g., "Create a bar chart...")')
@click.option('--save-images', is_flag=True, help='Save generated images to disk')
async def test_python_tool_agent(agent_url: str, query: str, save_images: bool) -> None:
    """Test the Python Tool Agent with a visualization request."""
    # Increase timeout for code execution operations
    timeout = httpx.Timeout(timeout=180.0, read=180.0, write=30.0)
    async with httpx.AsyncClient(timeout=timeout) as httpx_client:
        try:
            # Get the agent card using resolver
            print(f'Connecting to Python Tool agent at {agent_url}...')
            card_resolver = A2ACardResolver(httpx_client, agent_url)
            agent_card = await card_resolver.get_agent_card()

            print('✅ Successfully connected to Python Tool agent')
            print(f'Agent: {agent_card.name}')
            print(f'Description: {agent_card.description}')
            print(f'Skills: {[skill.name for skill in agent_card.skills]}')
            print()

            # Create A2A client
            client = A2AClient(httpx_client, agent_card=agent_card)

            # Send the query
            print(f'Sending request: {query}')
            print('=' * 70)

            # Use streaming if supported
            if agent_card.capabilities.streaming:
                # Create message with text part
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
                        accepted_output_modes=['text', 'image']
                    ),
                )
                response_stream = client.send_message_streaming(
                    SendStreamingMessageRequest(
                        id=str(uuid4()),
                        params=payload,
                    )
                )

                # Process streaming response
                image_count = 0
                async for result in response_stream:
                    if isinstance(result.root, JSONRPCErrorResponse):
                        print(f'❌ Error: {result.root.error}')
                        break

                    event = result.root.result
                    if isinstance(event, Message):
                        # Process message parts
                        for part in event.parts:
                            part_root = part.root
                            # Text content
                            if hasattr(part_root, 'text'):
                                print(part_root.text)
                            # Image content
                            elif hasattr(part_root, 'file'):
                                file_obj = part_root.file
                                if hasattr(file_obj, 'bytes'):
                                    image_count += 1
                                    mime_type = getattr(file_obj, 'mime_type', 'image/png')
                                    file_name = getattr(file_obj, 'name', f'image_{image_count}.png')

                                    print(f'\n📊 Generated visualization: {file_name} ({mime_type})')

                                    if save_images:
                                        # Save image to disk
                                        output_path = Path(f'output_{file_name}')
                                        # file_obj.bytes is a base64 string, need to decode it
                                        image_bytes = base64.b64decode(file_obj.bytes) if isinstance(file_obj.bytes, str) else file_obj.bytes
                                        output_path.write_bytes(image_bytes)
                                        print(f'💾 Saved to: {output_path.absolute()}')

                    elif isinstance(event, TaskStatusUpdateEvent):
                        # Extract and print message content from status updates
                        if event.status.message:
                            for part in event.status.message.parts:
                                part_root = part.root
                                if hasattr(part_root, 'text'):
                                    print(part_root.text)
                                elif hasattr(part_root, 'file'):
                                    # Handle images in status updates
                                    file_obj = part_root.file
                                    if hasattr(file_obj, 'bytes'):
                                        image_count += 1
                                        mime_type = getattr(file_obj, 'mime_type', 'image/png')
                                        file_name = getattr(file_obj, 'name', f'image_{image_count}.png')

                                        print(f'\n📊 Generated visualization: {file_name} ({mime_type})')

                                        if save_images:
                                            output_path = Path(f'output_{file_name}')
                                            # file_obj.bytes is a base64 string, need to decode it
                                            image_bytes = base64.b64decode(file_obj.bytes) if isinstance(file_obj.bytes, str) else file_obj.bytes
                                            output_path.write_bytes(image_bytes)
                                            print(f'💾 Saved to: {output_path.absolute()}')

                        if event.status.state == 'completed':
                            break
            else:
                # Fallback to non-streaming
                print('Non-streaming not implemented in this test client')

            print('\n' + '=' * 70)
            print('✅ Request completed')
            if image_count > 0:
                print(f'📊 Generated {image_count} visualization(s)')

        except Exception as e:
            print(f'❌ Error: {e}')
            import traceback
            traceback.print_exc()
            raise


def main() -> None:
    """Main function to run the test client."""
    asyncio.run(test_python_tool_agent.main(standalone_mode=False))


if __name__ == '__main__':
    main()
