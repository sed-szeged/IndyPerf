import pytest

from asynctest import mock as async_mock, TestCase as AsyncTestCase

from ......messaging.request_context import RequestContext
from ......messaging.responder import MockResponder
from ......transport.inbound.receipt import MessageReceipt

from ...messages.presentation import Presentation

from .. import presentation_handler as test_module


class TestPresentationHandler(AsyncTestCase):
    async def test_called(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.settings["debug.auto_verify_presentation"] = False

        with async_mock.patch.object(
            test_module, "PresentationManager", autospec=True
        ) as mock_pres_mgr:
            mock_pres_mgr.return_value.receive_presentation = async_mock.CoroutineMock()
            request_context.message = Presentation()
            request_context.connection_ready = True
            request_context.connection_record = async_mock.MagicMock()
            handler = test_module.PresentationHandler()
            responder = MockResponder()
            await handler.handle(request_context, responder)

        mock_pres_mgr.assert_called_once_with(request_context.profile)
        mock_pres_mgr.return_value.receive_presentation.assert_called_once_with(
            request_context.message, request_context.connection_record
        )
        assert not responder.messages

    async def test_called_auto_verify(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.settings["debug.auto_verify_presentation"] = True

        with async_mock.patch.object(
            test_module, "PresentationManager", autospec=True
        ) as mock_pres_mgr:
            mock_pres_mgr.return_value.receive_presentation = async_mock.CoroutineMock()
            mock_pres_mgr.return_value.verify_presentation = async_mock.CoroutineMock()
            request_context.message = Presentation()
            request_context.connection_ready = True
            request_context.connection_record = async_mock.MagicMock()
            handler = test_module.PresentationHandler()
            responder = MockResponder()
            await handler.handle(request_context, responder)

        mock_pres_mgr.assert_called_once_with(request_context.profile)
        mock_pres_mgr.return_value.receive_presentation.assert_called_once_with(
            request_context.message, request_context.connection_record
        )
        assert not responder.messages

    async def test_called_auto_verify_x(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.settings["debug.auto_verify_presentation"] = True

        with async_mock.patch.object(
            test_module, "PresentationManager", autospec=True
        ) as mock_pres_mgr:
            mock_pres_mgr.return_value.receive_presentation = async_mock.CoroutineMock(
                return_value=async_mock.MagicMock(
                    save_error_state=async_mock.CoroutineMock()
                )
            )
            mock_pres_mgr.return_value.verify_presentation = async_mock.CoroutineMock(
                side_effect=[
                    test_module.LedgerError(),
                    test_module.StorageError(),
                ]
            )
            request_context.message = Presentation()
            request_context.connection_ready = True
            request_context.connection_record = async_mock.MagicMock()
            handler = test_module.PresentationHandler()
            responder = MockResponder()

            await handler.handle(request_context, responder)  # ledger error
            await handler.handle(request_context, responder)  # storage error