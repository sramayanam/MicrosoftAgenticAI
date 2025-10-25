"""SQL Foundry Agent Executor for A2A framework.

Wraps an existing Azure AI Foundry SQL agent to work with the A2A protocol.
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

from .sql_foundry_agent import SQLFoundryAgent


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SQLFoundryAgentExecutor(AgentExecutor):
    """An AgentExecutor that runs Azure AI Foundry SQL agents.

    Wraps an existing SQL agent to work with the A2A protocol.
    """

    def __init__(self, card: AgentCard) -> None:
        self._card = card
        self._foundry_agent: SQLFoundryAgent | None = None
        self._active_threads: dict[
            str, str
        ] = {}  # context_id -> thread_id mapping

    async def _get_or_create_agent(self) -> SQLFoundryAgent:
        """Get or create the SQL Foundry agent."""
        if not self._foundry_agent:
            from .sql_foundry_agent import create_sql_foundry_agent

            self._foundry_agent = await create_sql_foundry_agent()
        return self._foundry_agent

    async def _get_or_create_thread(self, context_id: str) -> str:
        """Get or create a thread for the given context."""
        if context_id not in self._active_threads:
            agent = await self._get_or_create_agent()
            thread_data = await agent.create_thread()
            # Handle both dict and object formats
            if isinstance(thread_data, dict):
                thread_id = thread_data['id']
            else:
                thread_id = getattr(thread_data, 'id', None)
                if not thread_id:
                    raise ValueError(
                        'Could not extract thread ID from response'
                    )

            self._active_threads[context_id] = thread_id
            logger.info(
                'Created new thread %s for context %s', thread_id, context_id
            )

        return self._active_threads[context_id]

    async def _process_request(
        self,
        message_parts: list[Part],
        context_id: str,
        task_updater: TaskUpdater,
    ) -> None:
        """Process a user request through the SQL Foundry agent."""
        try:
            # Convert A2A parts to text message
            user_message = self._convert_parts_to_text(message_parts)

            # Get agent and thread
            agent = await self._get_or_create_agent()
            thread_id = await self._get_or_create_thread(context_id)

            # Update status
            await task_updater.update_status(
                TaskState.working,
                message=new_agent_text_message(
                    'Processing your SQL query...', context_id=context_id
                ),
            )

            # Run the conversation
            responses = await agent.run_conversation(thread_id, user_message)

            # Send responses back
            for response in responses:
                await task_updater.update_status(
                    TaskState.working,
                    message=new_agent_text_message(
                        response, context_id=context_id
                    ),
                )

            # Mark as complete
            final_message = (
                responses[-1] if responses else 'SQL query completed.'
            )
            await task_updater.complete(
                message=new_agent_text_message(
                    final_message, context_id=context_id
                )
            )

        except Exception as e:
            logger.error('Error processing SQL request: %s', e, exc_info=True)
            await task_updater.failed(
                message=new_agent_text_message(
                    f'Error: {e!s}', context_id=context_id
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
                # For demo purposes, just indicate file presence
                if isinstance(part.file, FileWithUri):
                    text_parts.append(f'[File: {part.file.uri}]')
                elif isinstance(part.file, FileWithBytes):
                    text_parts.append(f'[File: {len(part.file.bytes)} bytes]')
            else:
                logger.warning('Unsupported part type: %s', type(part))

        return ' '.join(text_parts)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the SQL agent request."""
        logger.info('Executing SQL request for context: %s', context.context_id)

        # Create task updater
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        # Notify task submission
        if not context.current_task:
            await updater.submit()

        # Start working
        await updater.start_work()

        # Process the request
        await self._process_request(
            context.message.parts,
            context.context_id,
            updater,
        )

        logger.debug(
            'SQL Foundry agent execution completed for %s', context.context_id
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel the ongoing execution."""
        logger.info(
            'Cancelling SQL execution for context: %s', context.context_id
        )

        # For now, just log cancellation
        # In a full implementation, you might want to:
        # 1. Cancel any ongoing SQL queries
        # 2. Clean up resources
        # 3. Notify the task store

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.failed(
            message=new_agent_text_message(
                'SQL task cancelled by user', context_id=context.context_id
            )
        )

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._foundry_agent:
            await self._foundry_agent.cleanup_agent()
            self._foundry_agent = None
        self._active_threads.clear()
        logger.info('SQL Foundry agent executor cleaned up')


def create_sql_foundry_agent_executor(
    card: AgentCard,
) -> SQLFoundryAgentExecutor:
    """Factory function to create a SQL Foundry agent executor."""
    return SQLFoundryAgentExecutor(card)
