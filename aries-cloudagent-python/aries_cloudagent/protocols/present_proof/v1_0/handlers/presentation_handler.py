"""Presentation message handler."""

from .....ledger.error import LedgerError
from .....messaging.base_handler import BaseHandler
from .....messaging.request_context import RequestContext
from .....messaging.responder import BaseResponder
from .....storage.error import StorageError
from .....utils.tracing import trace_event, get_timer

from ..manager import PresentationManager
from ..messages.presentation import Presentation


class PresentationHandler(BaseHandler):
    """Message handler class for presentations."""

    async def handle(self, context: RequestContext, responder: BaseResponder):
        """
        Message handler logic for presentations.

        Args:
            context: request context
            responder: responder callback

        """
        r_time = get_timer()

        self._logger.debug("PresentationHandler called with context %s", context)
        assert isinstance(context.message, Presentation)
        self._logger.info(
            "Received presentation message: %s",
            context.message.serialize(as_string=True),
        )

        presentation_manager = PresentationManager(context.profile)

        presentation_exchange_record = await presentation_manager.receive_presentation(
            context.message, context.connection_record
        )  # mgr saves record state null if need be and possible

        r_time = trace_event(
            context.settings,
            context.message,
            outcome="PresentationHandler.handle.END",
            perf_counter=r_time,
        )

        if context.settings.get("debug.auto_verify_presentation"):
            try:
                await presentation_manager.verify_presentation(
                    presentation_exchange_record
                )
            except LedgerError as err:
                self._logger.exception(err)
                if presentation_exchange_record:
                    await presentation_exchange_record.save_error_state(
                        context.session(),
                        reason=err.message,
                    )
            except StorageError as err:
                self._logger.exception(err)  # may be logging to wire, not dead disk

            trace_event(
                context.settings,
                presentation_exchange_record,
                outcome="PresentationHandler.handle.VERIFY",
                perf_counter=r_time,
            )
