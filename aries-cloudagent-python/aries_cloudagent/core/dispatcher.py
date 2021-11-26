"""
The Dispatcher.

The dispatcher is responsible for coordinating data flow between handlers, providing
lifecycle hook callbacks storing state for message threads, etc.
"""

import asyncio
import logging
import os
import warnings

from typing import Callable, Coroutine, Union

from aiohttp.web import HTTPException

from ..core.profile import Profile
from ..messaging.agent_message import AgentMessage
from ..messaging.base_message import BaseMessage
from ..messaging.error import MessageParseError
from ..messaging.models.base import BaseModelError
from ..messaging.request_context import RequestContext
from ..messaging.responder import BaseResponder
from ..messaging.util import datetime_now
from ..protocols.connections.v1_0.manager import ConnectionManager
from ..protocols.problem_report.v1_0.message import ProblemReport
from ..transport.inbound.message import InboundMessage
from ..transport.outbound.message import OutboundMessage
from ..transport.outbound.status import OutboundSendStatus
from ..utils.stats import Collector
from ..utils.task_queue import CompletedTask, PendingTask, TaskQueue
from ..utils.tracing import get_timer, trace_event

from .error import ProtocolMinorVersionNotSupported
from .protocol_registry import ProtocolRegistry

LOGGER = logging.getLogger(__name__)


class ProblemReportParseError(MessageParseError):
    """Error to raise on failure to parse problem-report message."""


class Dispatcher:
    """
    Dispatcher class.

    Class responsible for dispatching messages to message handlers and responding
    to other agents.
    """

    def __init__(self, profile: Profile):
        """Initialize an instance of Dispatcher."""
        self.collector: Collector = None
        self.profile = profile
        self.task_queue: TaskQueue = None

    async def setup(self):
        """Perform async instance setup."""
        self.collector = self.profile.inject(Collector, required=False)
        max_active = int(os.getenv("DISPATCHER_MAX_ACTIVE", 50))
        self.task_queue = TaskQueue(
            max_active=max_active, timed=bool(self.collector), trace_fn=self.log_task
        )

    def put_task(
        self, coro: Coroutine, complete: Callable = None, ident: str = None
    ) -> PendingTask:
        """Run a task in the task queue, potentially blocking other handlers."""
        return self.task_queue.put(coro, complete, ident)

    def run_task(
        self, coro: Coroutine, complete: Callable = None, ident: str = None
    ) -> asyncio.Task:
        """Run a task in the task queue, potentially blocking other handlers."""
        return self.task_queue.run(coro, complete, ident)

    def log_task(self, task: CompletedTask):
        """Log a completed task using the stats collector."""
        if task.exc_info and not issubclass(task.exc_info[0], HTTPException):
            # skip errors intentionally returned to HTTP clients
            LOGGER.exception(
                "Handler error: %s", task.ident or "", exc_info=task.exc_info
            )
        if self.collector:
            timing = task.timing
            if "queued" in timing:
                self.collector.log(
                    "Dispatcher:queued", timing["unqueued"] - timing["queued"]
                )
            if task.ident:
                self.collector.log(task.ident, timing["ended"] - timing["started"])

    def queue_message(
        self,
        profile: Profile,
        inbound_message: InboundMessage,
        send_outbound: Coroutine,
        complete: Callable = None,
    ) -> PendingTask:
        """
        Add a message to the processing queue for handling.

        Args:
            profile: The profile associated with the inbound message
            inbound_message: The inbound message instance
            send_outbound: Async function to send outbound messages
            complete: Function to call when the handler has completed

        Returns:
            A pending task instance resolving to the handler task

        """
        return self.put_task(
            self.handle_message(profile, inbound_message, send_outbound),
            complete,
        )

    async def handle_message(
        self,
        profile: Profile,
        inbound_message: InboundMessage,
        send_outbound: Coroutine,
    ):
        """
        Configure responder and message context and invoke the message handler.

        Args:
            profile: The profile associated with the inbound message
            inbound_message: The inbound message instance
            send_outbound: Async function to send outbound messages

        Returns:
            The response from the handler

        """
        r_time = get_timer()

        error_result = None
        message = None
        try:
            message = await self.make_message(inbound_message.payload)
        except ProblemReportParseError:
            pass  # avoid problem report recursion
        except MessageParseError as e:
            LOGGER.error(f"Message parsing failed: {str(e)}, sending problem report")
            error_result = ProblemReport(
                description={
                    "en": str(e),
                    "code": "message-parse-failure",
                }
            )
            if inbound_message.receipt.thread_id:
                error_result.assign_thread_id(inbound_message.receipt.thread_id)

        trace_event(
            self.profile.settings,
            message,
            outcome="Dispatcher.handle_message.START",
        )

        context = RequestContext(profile)
        context.message = message
        context.message_receipt = inbound_message.receipt

        responder = DispatcherResponder(
            context,
            inbound_message,
            send_outbound,
            reply_session_id=inbound_message.session_id,
            reply_to_verkey=inbound_message.receipt.sender_verkey,
        )

        context.injector.bind_instance(BaseResponder, responder)

        async with profile.session(context._context) as session:
            connection_mgr = ConnectionManager(session)
            connection = await connection_mgr.find_inbound_connection(
                inbound_message.receipt
            )
            del connection_mgr
        if connection:
            inbound_message.connection_id = connection.connection_id

        context.connection_ready = connection and connection.is_ready
        context.connection_record = connection
        responder.connection_id = connection and connection.connection_id

        if error_result:
            await responder.send_reply(error_result)
        elif context.message:
            context.injector.bind_instance(BaseResponder, responder)

            handler_cls = context.message.Handler
            handler = handler_cls().handle
            if self.collector:
                handler = self.collector.wrap_coro(handler, [handler.__qualname__])
            await handler(context, responder)

        trace_event(
            self.profile.settings,
            context.message,
            outcome="Dispatcher.handle_message.END",
            perf_counter=r_time,
        )

    async def make_message(self, parsed_msg: dict) -> BaseMessage:
        """
        Deserialize a message dict into the appropriate message instance.

        Given a dict describing a message, this method
        returns an instance of the related message class.

        Args:
            parsed_msg: The parsed message

        Returns:
            An instance of the corresponding message class for this message

        Raises:
            MessageParseError: If the message doesn't specify @type
            MessageParseError: If there is no message class registered to handle
            the given type

        """
        if not isinstance(parsed_msg, dict):
            raise MessageParseError("Expected a JSON object")
        message_type = parsed_msg.get("@type")

        if not message_type:
            raise MessageParseError("Message does not contain '@type' parameter")

        registry: ProtocolRegistry = self.profile.inject(ProtocolRegistry)
        try:
            message_cls = registry.resolve_message_class(message_type)
        except ProtocolMinorVersionNotSupported as e:
            raise MessageParseError(f"Problem parsing message type. {e}")

        if not message_cls:
            raise MessageParseError(f"Unrecognized message type {message_type}")

        try:
            instance = message_cls.deserialize(parsed_msg)
        except BaseModelError as e:
            if "/problem-report" in message_type:
                raise ProblemReportParseError("Error parsing problem report message")
            raise MessageParseError(f"Error deserializing message: {e}") from e

        return instance

    async def complete(self, timeout: float = 0.1):
        """Wait for pending tasks to complete."""
        await self.task_queue.complete(timeout=timeout)


class DispatcherResponder(BaseResponder):
    """Handle outgoing messages from message handlers."""

    def __init__(
        self,
        context: RequestContext,
        inbound_message: InboundMessage,
        send_outbound: Coroutine,
        **kwargs,
    ):
        """
        Initialize an instance of `DispatcherResponder`.

        Args:
            context: The request context of the incoming message
            inbound_message: The inbound message triggering this handler
            send_outbound: Async function to send outbound message

        """
        super().__init__(**kwargs)
        self._context = context
        self._inbound_message = inbound_message
        self._send = send_outbound

    async def create_outbound(
        self, message: Union[AgentMessage, BaseMessage, str, bytes], **kwargs
    ) -> OutboundMessage:
        """
        Create an OutboundMessage from a message body.

        Args:
            message: The message payload
        """
        if isinstance(message, AgentMessage) and self._context.settings.get(
            "timing.enabled"
        ):
            # Inject the timing decorator
            in_time = (
                self._context.message_receipt and self._context.message_receipt.in_time
            )
            if not message._decorators.get("timing"):
                message._decorators["timing"] = {
                    "in_time": in_time,
                    "out_time": datetime_now(),
                }

        return await super().create_outbound(message, **kwargs)

    async def send_outbound(self, message: OutboundMessage) -> OutboundSendStatus:
        """
        Send outbound message.

        Args:
            message: The `OutboundMessage` to be sent
        """
        return await self._send(self._context.profile, message, self._inbound_message)

    async def send_webhook(self, topic: str, payload: dict):
        """
        Dispatch a webhook. DEPRECATED: use the event bus instead.

        Args:
            topic: the webhook topic identifier
            payload: the webhook payload value
        """
        warnings.warn(
            "responder.send_webhook is deprecated; please use the event bus instead.",
            DeprecationWarning,
        )
        await self._context.profile.notify("acapy::webhook::" + topic, payload)
