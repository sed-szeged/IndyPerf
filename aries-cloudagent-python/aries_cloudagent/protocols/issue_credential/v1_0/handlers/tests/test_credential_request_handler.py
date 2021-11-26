from asynctest import mock as async_mock, TestCase as AsyncTestCase

from ......messaging.request_context import RequestContext
from ......messaging.responder import MockResponder
from ......transport.inbound.receipt import MessageReceipt

from ...messages.credential_request import CredentialRequest
from ...messages.inner.credential_preview import CredAttrSpec, CredentialPreview
from ...models.credential_exchange import V10CredentialExchange

from .. import credential_request_handler as test_module

CD_ID = "LjgpST2rjsoxYegQDRm7EL:3:CL:18:tag"


class TestCredentialRequestHandler(AsyncTestCase):
    async def test_called(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.connection_record = async_mock.MagicMock()

        with async_mock.patch.object(
            test_module, "CredentialManager", autospec=True
        ) as mock_cred_mgr:
            mock_cred_mgr.return_value.receive_request = async_mock.CoroutineMock(
                return_value=async_mock.MagicMock()
            )
            mock_cred_mgr.return_value.receive_request.return_value.auto_issue = False
            request_context.message = CredentialRequest()
            request_context.connection_ready = True
            handler = test_module.CredentialRequestHandler()
            responder = MockResponder()
            await handler.handle(request_context, responder)

        mock_cred_mgr.assert_called_once_with(request_context.profile)
        mock_cred_mgr.return_value.receive_request.assert_called_once_with(
            request_context.message, request_context.connection_record.connection_id
        )
        assert not responder.messages

    async def test_called_auto_issue(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.connection_record = async_mock.MagicMock()

        ATTR_DICT = {"test": "123", "hello": "world"}
        cred_ex_rec = V10CredentialExchange(
            credential_proposal_dict={
                "credential_proposal": CredentialPreview(
                    attributes=(CredAttrSpec.list_plain(ATTR_DICT))
                ).serialize(),
                "cred_def_id": CD_ID,
            },
        )

        with async_mock.patch.object(
            test_module, "CredentialManager", autospec=True
        ) as mock_cred_mgr:
            mock_cred_mgr.return_value.receive_request = async_mock.CoroutineMock(
                return_value=cred_ex_rec
            )
            mock_cred_mgr.return_value.receive_request.return_value.auto_issue = True
            mock_cred_mgr.return_value.issue_credential = async_mock.CoroutineMock(
                return_value=(None, "credential_issue_message")
            )
            request_context.message = CredentialRequest()
            request_context.connection_ready = True
            handler = test_module.CredentialRequestHandler()
            responder = MockResponder()
            await handler.handle(request_context, responder)
            mock_cred_mgr.return_value.issue_credential.assert_called_once_with(
                cred_ex_record=cred_ex_rec, comment=None
            )

        mock_cred_mgr.assert_called_once_with(request_context.profile)
        mock_cred_mgr.return_value.receive_request.assert_called_once_with(
            request_context.message, request_context.connection_record.connection_id
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "credential_issue_message"
        assert target == {}

    async def test_called_auto_issue_x(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.connection_record = async_mock.MagicMock()

        ATTR_DICT = {"test": "123", "hello": "world"}
        cred_ex_rec = V10CredentialExchange(
            credential_proposal_dict={
                "credential_proposal": CredentialPreview(
                    attributes=(CredAttrSpec.list_plain(ATTR_DICT))
                ).serialize(),
                "cred_def_id": CD_ID,
            },
        )

        with async_mock.patch.object(
            test_module, "CredentialManager", autospec=True
        ) as mock_cred_mgr, async_mock.patch.object(
            cred_ex_rec, "save_error_state", async_mock.CoroutineMock()
        ):
            mock_cred_mgr.return_value.receive_request = async_mock.CoroutineMock(
                return_value=cred_ex_rec
            )
            mock_cred_mgr.return_value.receive_request.return_value.auto_issue = True
            mock_cred_mgr.return_value.issue_credential = async_mock.CoroutineMock(
                side_effect=[
                    test_module.IndyIssuerError(),
                    test_module.StorageError(),
                ]
            )

            request_context.message = CredentialRequest()
            request_context.connection_ready = True
            handler = test_module.CredentialRequestHandler()
            responder = MockResponder()

            with async_mock.patch.object(
                responder, "send_reply", async_mock.CoroutineMock()
            ) as mock_send_reply:
                await handler.handle(request_context, responder)  # holder error
                await handler.handle(request_context, responder)  # storage error
                mock_send_reply.assert_not_called()

    async def test_called_auto_issue_no_preview(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.connection_record = async_mock.MagicMock()

        cred_ex_rec = V10CredentialExchange(
            credential_proposal_dict={"cred_def_id": CD_ID}
        )

        with async_mock.patch.object(
            test_module, "CredentialManager", autospec=True
        ) as mock_cred_mgr:
            mock_cred_mgr.return_value.receive_request = async_mock.CoroutineMock(
                return_value=cred_ex_rec
            )
            mock_cred_mgr.return_value.receive_request.return_value.auto_issue = True
            mock_cred_mgr.return_value.issue_credential = async_mock.CoroutineMock(
                return_value=(None, "credential_issue_message")
            )

            request_context.message = CredentialRequest()
            request_context.connection_ready = True
            handler = test_module.CredentialRequestHandler()
            responder = MockResponder()
            await handler.handle(request_context, responder)
            mock_cred_mgr.return_value.issue_credential.assert_not_called()

        mock_cred_mgr.assert_called_once_with(request_context.profile)
        mock_cred_mgr.return_value.receive_request.assert_called_once_with(
            request_context.message, request_context.connection_record.connection_id
        )
        assert not responder.messages

    async def test_called_not_ready(self):
        request_context = RequestContext.test_context()
        request_context.message_receipt = MessageReceipt()
        request_context.connection_record = async_mock.MagicMock()

        with async_mock.patch.object(
            test_module, "CredentialManager", autospec=True
        ) as mock_cred_mgr:
            mock_cred_mgr.return_value.receive_request = async_mock.CoroutineMock()
            request_context.message = CredentialRequest()
            request_context.connection_ready = False
            handler = test_module.CredentialRequestHandler()
            responder = MockResponder()
            with self.assertRaises(test_module.HandlerException):
                await handler.handle(request_context, responder)

        assert not responder.messages
