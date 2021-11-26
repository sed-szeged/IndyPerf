import asyncio
import json

from asynctest import TestCase as AsyncTestCase, mock as async_mock
from marshmallow import EXCLUDE

from ...config.injection_context import InjectionContext
from ...connections.models.conn_record import ConnRecord
from ...core.event_bus import EventBus
from ...core.in_memory import InMemoryProfile
from ...core.profile import Profile
from ...core.protocol_registry import ProtocolRegistry
from ...messaging.agent_message import AgentMessage, AgentMessageSchema
from ...messaging.responder import MockResponder
from ...messaging.request_context import RequestContext
from ...messaging.util import datetime_now
from ...protocols.didcomm_prefix import DIDCommPrefix
from ...protocols.issue_credential.v2_0.message_types import CRED_20_PROBLEM_REPORT
from ...protocols.issue_credential.v2_0.messages.cred_problem_report import (
    V20CredProblemReport,
)
from ...protocols.problem_report.v1_0.message import ProblemReport
from ...transport.inbound.message import InboundMessage
from ...transport.inbound.receipt import MessageReceipt
from ...transport.outbound.message import OutboundMessage
from ...utils.stats import Collector

from .. import dispatcher as test_module


def make_profile() -> Profile:
    profile = InMemoryProfile.test_profile()
    profile.context.injector.bind_instance(ProtocolRegistry, ProtocolRegistry())
    profile.context.injector.bind_instance(Collector, Collector())
    profile.context.injector.bind_instance(EventBus, EventBus())
    return profile


def make_inbound(payload) -> InboundMessage:
    return InboundMessage(payload, MessageReceipt(thread_id="dummy-thread"))


class Receiver:
    def __init__(self):
        self.messages = []

    async def send(
        self,
        context: InjectionContext,
        message: OutboundMessage,
        inbound: InboundMessage = None,
    ):
        self.messages.append((context, message, inbound))


class StubAgentMessage(AgentMessage):
    class Meta:
        handler_class = "StubAgentMessageHandler"
        schema_class = "StubAgentMessageSchema"
        message_type = "proto-name/1.1/message-type"


class StubAgentMessageSchema(AgentMessageSchema):
    class Meta:
        model_class = StubAgentMessage
        unknown = EXCLUDE


class StubAgentMessageHandler:
    async def handle(self, context, responder):
        pass


class StubV1_2AgentMessage(AgentMessage):
    class Meta:
        handler_class = "StubV1_2AgentMessageHandler"
        schema_class = "StubV1_2AgentMessageSchema"
        message_type = "proto-name/1.2/message-type"


class StubV1_2AgentMessageSchema(AgentMessageSchema):
    class Meta:
        model_class = StubV1_2AgentMessage
        unknonw = EXCLUDE


class StubV1_2AgentMessageHandler:
    async def handle(self, context, responder):
        pass


class TestDispatcher(AsyncTestCase):
    async def test_dispatch(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                pfx.qualify(StubAgentMessage.Meta.message_type): StubAgentMessage
                for pfx in DIDCommPrefix
            }
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {
            "@type": DIDCommPrefix.qualify_current(StubAgentMessage.Meta.message_type)
        }

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock, async_mock.patch.object(
            test_module, "ConnectionManager", autospec=True
        ) as conn_mgr_mock:
            conn_mgr_mock.return_value = async_mock.MagicMock(
                find_inbound_connection=async_mock.CoroutineMock(
                    return_value=async_mock.MagicMock(connection_id="dummy")
                )
            )
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            handler_mock.assert_awaited_once()
            assert isinstance(handler_mock.call_args[0][1].message, StubAgentMessage)
            assert isinstance(
                handler_mock.call_args[0][2], test_module.DispatcherResponder
            )

    async def test_dispatch_versioned_message(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubAgentMessage.Meta.message_type
                ): StubAgentMessage
            },
            version_definition={
                "major_version": 1,
                "minimum_minor_version": 0,
                "current_minor_version": 1,
                "path": "v1_1",
            },
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {
            "@type": DIDCommPrefix.qualify_current(StubAgentMessage.Meta.message_type)
        }

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock:
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            handler_mock.assert_awaited_once()
            assert isinstance(handler_mock.call_args[0][1].message, StubAgentMessage)
            assert isinstance(
                handler_mock.call_args[0][2], test_module.DispatcherResponder
            )

    async def test_dispatch_versioned_message_no_message_class(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubAgentMessage.Meta.message_type
                ): StubAgentMessage
            },
            version_definition={
                "major_version": 1,
                "minimum_minor_version": 0,
                "current_minor_version": 1,
                "path": "v1_1",
            },
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {"@type": "proto-name/1.1/no-such-message-type"}

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock:
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            assert rcv.messages and isinstance(rcv.messages[0][1], OutboundMessage)
            payload = json.loads(rcv.messages[0][1].payload)
            assert payload["@type"] == DIDCommPrefix.qualify_current(
                ProblemReport.Meta.message_type
            )

    async def test_dispatch_versioned_message_message_class_deserialize_x(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubAgentMessage.Meta.message_type
                ): StubAgentMessage
            },
            version_definition={
                "major_version": 1,
                "minimum_minor_version": 0,
                "current_minor_version": 1,
                "path": "v1_1",
            },
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {"@type": "proto-name/1.1/no-such-message-type"}

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock, async_mock.patch.object(
            registry, "resolve_message_class", async_mock.MagicMock()
        ) as mock_resolve:
            mock_resolve.return_value = async_mock.MagicMock(
                deserialize=async_mock.MagicMock(
                    side_effect=test_module.BaseModelError()
                )
            )
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            assert rcv.messages and isinstance(rcv.messages[0][1], OutboundMessage)
            payload = json.loads(rcv.messages[0][1].payload)
            assert payload["@type"] == DIDCommPrefix.qualify_current(
                ProblemReport.Meta.message_type
            )

    async def test_dispatch_versioned_message_handle_greater_succeeds(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubAgentMessage.Meta.message_type
                ): StubAgentMessage
            },
            version_definition={
                "major_version": 1,
                "minimum_minor_version": 0,
                "current_minor_version": 1,
                "path": "v1_1",
            },
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {
            "@type": DIDCommPrefix.qualify_current(
                StubV1_2AgentMessage.Meta.message_type
            )
        }

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock:
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            handler_mock.assert_awaited_once()
            assert isinstance(handler_mock.call_args[0][1].message, StubAgentMessage)
            assert isinstance(
                handler_mock.call_args[0][2], test_module.DispatcherResponder
            )

    async def test_dispatch_versioned_message_fail(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubV1_2AgentMessage.Meta.message_type
                ): StubV1_2AgentMessage
            },
            version_definition={
                "major_version": 1,
                "minimum_minor_version": 2,
                "current_minor_version": 2,
                "path": "v1_2",
            },
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        message = {
            "@type": DIDCommPrefix.qualify_current(StubAgentMessage.Meta.message_type)
        }

        with async_mock.patch.object(
            StubAgentMessageHandler, "handle", autospec=True
        ) as handler_mock:
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(message), rcv.send
            )
            await dispatcher.task_queue
            assert rcv.messages and isinstance(rcv.messages[0][1], OutboundMessage)
            payload = json.loads(rcv.messages[0][1].payload)
            assert payload["@type"] == DIDCommPrefix.qualify_current(
                ProblemReport.Meta.message_type
            )

    async def test_bad_message_dispatch_parse_x(self):
        dispatcher = test_module.Dispatcher(make_profile())
        await dispatcher.setup()
        rcv = Receiver()
        bad_messages = ["not even a dict", {"bad": "message"}]
        for bad in bad_messages:
            await dispatcher.queue_message(
                dispatcher.profile, make_inbound(bad), rcv.send
            )
            await dispatcher.task_queue
            assert rcv.messages and isinstance(rcv.messages[0][1], OutboundMessage)
            payload = json.loads(rcv.messages[0][1].payload)
            assert payload["@type"] == DIDCommPrefix.qualify_current(
                ProblemReport.Meta.message_type
            )
            rcv.messages.clear()

    async def test_bad_message_dispatch_problem_report_x(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                pfx.qualify(CRED_20_PROBLEM_REPORT): V20CredProblemReport
                for pfx in DIDCommPrefix
            }
        )
        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()
        rcv = Receiver()
        bad_message = {
            "@type": DIDCommPrefix.qualify_current(CRED_20_PROBLEM_REPORT),
            "description": "should be a dict",
        }
        await dispatcher.queue_message(
            dispatcher.profile, make_inbound(bad_message), rcv.send
        )
        await dispatcher.task_queue
        assert not rcv.messages

    async def test_dispatch_log(self):
        profile = make_profile()
        registry = profile.inject(ProtocolRegistry)
        registry.register_message_types(
            {
                DIDCommPrefix.qualify_current(
                    StubAgentMessage.Meta.message_type
                ): StubAgentMessage
            },
        )

        dispatcher = test_module.Dispatcher(profile)
        await dispatcher.setup()

        mock_task = async_mock.MagicMock(
            exc_info=(KeyError, KeyError("sample exception"), "..."),
            ident="abc",
            timing={
                "queued": 1234567890,
                "unqueued": 1234567899,
                "started": 1234567901,
                "ended": 1234567999,
            },
        )
        dispatcher.log_task(mock_task)

    async def test_create_send_outbound(self):
        profile = make_profile()
        context = RequestContext(
            profile,
            settings={"timing.enabled": True},
        )
        message = StubAgentMessage()
        responder = test_module.DispatcherResponder(context, message, None)
        outbound_message = await responder.create_outbound(message)
        with async_mock.patch.object(responder, "_send", async_mock.CoroutineMock()):
            await responder.send_outbound(outbound_message)

    async def test_create_send_webhook(self):
        profile = make_profile()
        context = RequestContext(profile)
        message = StubAgentMessage()
        responder = test_module.DispatcherResponder(context, message, None)
        await responder.send_webhook("topic", {"pay": "load"})

    async def test_create_enc_outbound(self):
        profile = make_profile()
        context = RequestContext(profile)
        message = b"abc123xyz7890000"
        responder = test_module.DispatcherResponder(context, message, None)
        with async_mock.patch.object(
            responder, "send_outbound", async_mock.CoroutineMock()
        ) as mock_send_outbound:
            await responder.send(message)
            assert mock_send_outbound.called_once()
