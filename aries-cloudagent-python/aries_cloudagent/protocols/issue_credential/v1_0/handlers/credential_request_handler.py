"""Credential request message handler."""

from .....indy.issuer import IndyIssuerError
from .....ledger.error import LedgerError
from .....messaging.base_handler import BaseHandler, HandlerException
from .....messaging.request_context import RequestContext
from .....messaging.responder import BaseResponder
from .....storage.error import StorageError
from .....utils.tracing import trace_event, get_timer

from ..manager import CredentialManager, CredentialManagerError
from ..messages.credential_request import CredentialRequest


class CredentialRequestHandler(BaseHandler):
    """Message handler class for credential requests."""

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """
        Message handler logic for credential requests.

        Args:
            context: request context
            responder: responder callback

        """
        r_time = get_timer()

        self._logger.debug("CredentialRequestHandler called with context %s", context)
        assert isinstance(context.message, CredentialRequest)
        self._logger.info(
            "Received credential request message: %s",
            context.message.serialize(as_string=True),
        )

        if not context.connection_ready:
            raise HandlerException("No connection established for credential request")

        credential_manager = CredentialManager(context.profile)
        cred_ex_record = await credential_manager.receive_request(
            context.message, context.connection_record.connection_id
        )  # mgr only finds, saves record: on exception, saving state null is hopeless

        r_time = trace_event(
            context.settings,
            context.message,
            outcome="CredentialRequestHandler.handle.END",
            perf_counter=r_time,
        )

        # If auto_issue is enabled, respond immediately
        if cred_ex_record.auto_issue:
            if (
                cred_ex_record.credential_proposal_dict
                and "credential_proposal" in cred_ex_record.credential_proposal_dict
            ):
                credential_issue_message = None
                try:
                    (
                        cred_ex_record,
                        credential_issue_message,
                    ) = await credential_manager.issue_credential(
                        cred_ex_record=cred_ex_record,
                        comment=context.message.comment,
                    )
                    await responder.send_reply(credential_issue_message)
                except (CredentialManagerError, IndyIssuerError, LedgerError) as err:
                    self._logger.exception(err)
                    if cred_ex_record:
                        await cred_ex_record.save_error_state(
                            context.session(),
                            reason=err.message,
                        )
                except StorageError as err:
                    self._logger.exception(err)  # may be logging to wire, not dead disk

                trace_event(
                    context.settings,
                    credential_issue_message,
                    outcome="CredentialRequestHandler.issue.END",
                    perf_counter=r_time,
                )
            else:
                self._logger.warning(
                    "Operation set for auto-issue but credential exchange record "
                    f"{cred_ex_record.credential_exchange_id} "
                    "has no attribute values"
                )
