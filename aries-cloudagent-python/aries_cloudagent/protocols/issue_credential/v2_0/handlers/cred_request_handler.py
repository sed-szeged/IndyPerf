"""Credential request message handler."""

from .....indy.issuer import IndyIssuerError
from .....ledger.error import LedgerError
from .....messaging.base_handler import BaseHandler, HandlerException
from .....messaging.request_context import RequestContext
from .....messaging.responder import BaseResponder
from .....storage.error import StorageError
from .....utils.tracing import trace_event, get_timer

from ..manager import V20CredManager, V20CredManagerError
from ..messages.cred_request import V20CredRequest


class V20CredRequestHandler(BaseHandler):
    """Message handler class for credential requests."""

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """
        Message handler logic for credential requests.

        Args:
            context: request context
            responder: responder callback

        """
        r_time = get_timer()

        self._logger.debug("V20CredRequestHandler called with context %s", context)
        assert isinstance(context.message, V20CredRequest)
        self._logger.info(
            "Received v2.0 credential request message: %s",
            context.message.serialize(as_string=True),
        )

        if not context.connection_ready:
            raise HandlerException("No connection established for credential request")

        cred_manager = V20CredManager(context.profile)
        cred_ex_record = await cred_manager.receive_request(
            context.message, context.connection_record.connection_id
        )  # mgr only finds, saves record: on exception, saving state null is hopeless

        r_time = trace_event(
            context.settings,
            context.message,
            outcome="V20CredRequestHandler.handle.END",
            perf_counter=r_time,
        )

        # If auto_issue is enabled, respond immediately
        if cred_ex_record.auto_issue:
            cred_issue_message = None
            try:
                (
                    cred_ex_record,
                    cred_issue_message,
                ) = await cred_manager.issue_credential(
                    cred_ex_record=cred_ex_record,
                    comment=context.message.comment,
                )
                await responder.send_reply(cred_issue_message)
            except (V20CredManagerError, IndyIssuerError, LedgerError) as err:
                self._logger.exception(err)
            except StorageError as err:
                self._logger.exception(err)  # may be logging to wire, not dead disk

            trace_event(
                context.settings,
                cred_issue_message,
                outcome="V20CredRequestHandler.issue.END",
                perf_counter=r_time,
            )
