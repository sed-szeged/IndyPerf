"""Connection request handler."""

from .....messaging.base_handler import (
    BaseHandler,
    BaseResponder,
    RequestContext,
)

from ..manager import ConnectionManager, ConnectionManagerError
from ..messages.connection_request import ConnectionRequest
from ..messages.problem_report import ConnectionProblemReport


class ConnectionRequestHandler(BaseHandler):
    """Handler class for connection requests."""

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """
        Handle connection request.

        Args:
            context: Request context
            responder: Responder callback
        """

        self._logger.debug(f"ConnectionRequestHandler called with context {context}")
        assert isinstance(context.message, ConnectionRequest)

        session = await context.session()
        mgr = ConnectionManager(session)

        if context.connection_record:
            mediation_metadata = await context.connection_record.metadata_get(
                session, "mediation", {}
            )
        else:
            mediation_metadata = {}

        try:
            await mgr.receive_request(
                context.message,
                context.message_receipt,
                mediation_id=mediation_metadata.get("id"),
            )
        except ConnectionManagerError as e:
            self._logger.exception("Error receiving connection request")
            if e.error_code:
                targets = None
                if context.message.connection and context.message.connection.did_doc:
                    try:
                        targets = mgr.diddoc_connection_targets(
                            context.message.connection.did_doc,
                            context.message_receipt.recipient_verkey,
                        )
                    except ConnectionManagerError:
                        self._logger.exception(
                            "Error parsing DIDDoc for problem report"
                        )
                await responder.send_reply(
                    ConnectionProblemReport(problem_code=e.error_code, explain=str(e)),
                    target_list=targets,
                )
