"""Databricks Agent Executor for A2A framework.

Wraps a Microsoft Agent Framework Databricks Agent to work with the A2A protocol.
"""

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

from .databricks_agent import DatabricksAgent


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class DatabricksAgentExecutor(AgentExecutor):
    """An AgentExecutor that runs Databricks MCP agents.

    Wraps a Databricks agent to work with the A2A protocol.
    """

    def __init__(self, card: AgentCard) -> None:
        self._card = card
        self._databricks_agent: DatabricksAgent | None = None
        self._active_contexts: set[str] = set()

    async def _get_or_create_agent(self) -> DatabricksAgent:
        """Get or create the Databricks Agent."""
        if not self._databricks_agent:
            from .databricks_agent import create_databricks_agent

            self._databricks_agent = await create_databricks_agent()
        return self._databricks_agent

    async def _process_request(
        self,
        message_parts: list[Part],
        context_id: str,
        task_updater: TaskUpdater,
    ) -> None:
        """Process a user request through the Databricks Agent."""
        try:
            # Convert A2A parts to text message
            user_message = self._convert_parts_to_text(message_parts)

            # Get agent
            agent = await self._get_or_create_agent()

            # Update status
            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    'Querying Databricks...', context_id=context_id
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

            # Mark as complete
            final_message = response['text'] if response['text'] else 'Query completed.'
            await task_updater.complete(
                message=new_agent_text_message(final_message, context_id=context_id)
            )

        except Exception as e:
            logger.error('Error processing Databricks request: %s', e, exc_info=True)
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
        """Execute the Databricks agent request."""
        logger.info(
            'Executing Databricks request for context: %s', context.context_id
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
            'Databricks agent execution completed for %s', context.context_id
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel the ongoing execution."""
        logger.info(
            'Cancelling Databricks execution for context: %s', context.context_id
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
        if self._databricks_agent:
            await self._databricks_agent.cleanup()
            self._databricks_agent = None
        self._active_contexts.clear()
        logger.info('Databricks agent executor cleaned up')


def create_databricks_agent_executor(
    card: AgentCard,
) -> DatabricksAgentExecutor:
    """Factory function to create a Databricks agent executor."""
    return DatabricksAgentExecutor(card)