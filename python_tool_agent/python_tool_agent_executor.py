"""Python Tool Agent Executor for A2A framework.

Wraps a Semantic Kernel Python Tool Agent to work with the A2A protocol.
"""

import base64
import logging

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils.message import new_agent_text_message

from .python_tool_agent import PythonToolAgent


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PythonToolAgentExecutor(AgentExecutor):
    """An AgentExecutor that runs Semantic Kernel Python Tool agents.

    Wraps a Python visualization agent to work with the A2A protocol.
    """

    def __init__(self, card: AgentCard) -> None:
        self._card = card
        self._tool_agent: PythonToolAgent | None = None
        self._active_contexts: set[str] = set()

    async def _get_or_create_agent(self) -> PythonToolAgent:
        """Get or create the Python Tool Agent."""
        if not self._tool_agent:
            from .python_tool_agent import create_python_tool_agent

            self._tool_agent = await create_python_tool_agent()
        return self._tool_agent

    async def _process_request(
        self,
        message_parts: list[Part],
        context_id: str,
        task_updater: TaskUpdater,
    ) -> None:
        """Process a user request through the Python Tool Agent."""
        try:
            # Convert A2A parts to text message
            user_message = self._convert_parts_to_text(message_parts)

            # Get agent
            agent = await self._get_or_create_agent()

            # Update status
            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    'Processing your request...', context_id=context_id
                ),
            )

            # Process the message
            response = await agent.process_message(context_id, user_message)

            # Send text response
            if response['text']:
                await task_updater.update_status(
                    TaskState.working,
                    message=new_agent_text_message(
                        response['text'], context_id=context_id
                    ),
                )

            # Send any images as file attachments
            if response.get('images'):
                for idx, image in enumerate(response['images']):
                    # Create a file part with the image data
                    # FileWithBytes expects 'bytes' field to be a base64-encoded STRING, not raw bytes
                    image_data = image['data']  # Already base64 string from python_tool_agent.py

                    file_part = FilePart(
                        file=FileWithBytes(
                            name=f'visualization_{idx + 1}.png',
                            mime_type=image.get('mime_type', 'image/png'),
                            bytes=image_data,  # Keep as base64 string
                        )
                    )

                    # Send as a message with file attachment
                    from a2a.types import Message
                    from uuid import uuid4

                    image_message = Message(
                        role='agent',  # A2A uses 'agent' not 'assistant'
                        parts=[file_part],
                        context_id=context_id,
                        message_id=str(uuid4()),  # Required field
                    )

                    await task_updater.update_status(
                        TaskState.working,
                        message=image_message,
                    )

            # Mark as complete
            final_message = response['text'] if response['text'] else 'Processing completed.'
            await task_updater.complete(
                message=new_agent_text_message(final_message, context_id=context_id)
            )

        except Exception as e:
            logger.error('Error processing Python Tool request: %s', e, exc_info=True)
            await task_updater.failed(
                message=new_agent_text_message(
                    f'Error: {str(e)}', context_id=context_id
                )
            )

    def _convert_parts_to_text(self, parts: list[Part]) -> str:
        """Convert A2A message parts to a text string."""
        text_parts = []

        for part in parts:
            part = part.root
            if isinstance(part, TextPart):
                text_parts.append(part.text)
            elif isinstance(part, FilePart):
                # For files, indicate they're attached
                if isinstance(part.file, FileWithUri):
                    text_parts.append(f'[Attached file: {part.file.uri}]')
                elif isinstance(part.file, FileWithBytes):
                    text_parts.append(
                        f'[Attached file: {part.file.name or "unnamed"}, {len(part.file.bytes)} bytes]'
                    )
            else:
                logger.warning('Unsupported part type: %s', type(part))

        return ' '.join(text_parts)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the Python Tool agent request."""
        logger.info(
            'Executing Python Tool request for context: %s', context.context_id
        )

        # Create task updater
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        # Notify task submission
        if not context.current_task:
            await updater.submit()

        # Start working
        await updater.start_work()

        # Track active context
        self._active_contexts.add(context.context_id)

        # Process the request
        await self._process_request(
            context.message.parts,
            context.context_id,
            updater,
        )

        # Remove from active contexts
        self._active_contexts.discard(context.context_id)

        logger.debug(
            'Python Tool agent execution completed for %s', context.context_id
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel the ongoing execution."""
        logger.info(
            'Cancelling Python Tool execution for context: %s', context.context_id
        )

        # Remove from active contexts
        self._active_contexts.discard(context.context_id)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.failed(
            message=new_agent_text_message(
                'Task cancelled by user', context_id=context.context_id
            )
        )

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._tool_agent:
            await self._tool_agent.cleanup()
            self._tool_agent = None
        self._active_contexts.clear()
        logger.info('Python Tool agent executor cleaned up')


def create_python_tool_agent_executor(
    card: AgentCard,
) -> PythonToolAgentExecutor:
    """Factory function to create a Python Tool agent executor."""
    return PythonToolAgentExecutor(card)
