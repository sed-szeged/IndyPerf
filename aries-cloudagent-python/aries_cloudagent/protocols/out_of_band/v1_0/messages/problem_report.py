"""Represents an OOB connection reuse problem report message."""

from enum import Enum

from marshmallow import (
    EXCLUDE,
    pre_dump,
    validates_schema,
    ValidationError,
)

from ....problem_report.v1_0.message import ProblemReport, ProblemReportSchema

from ..message_types import PROBLEM_REPORT, PROTOCOL_PACKAGE

HANDLER_CLASS = (
    f"{PROTOCOL_PACKAGE}.handlers"
    ".problem_report_handler.OOBProblemReportMessageHandler"
)


class ProblemReportReason(Enum):
    """Supported reason codes."""

    NO_EXISTING_CONNECTION = "no_existing_connection"
    EXISTING_CONNECTION_NOT_ACTIVE = "existing_connection_not_active"


class OOBProblemReport(ProblemReport):
    """Base class representing an OOB connection reuse problem report message."""

    class Meta:
        """OOB connection reuse problem report metadata."""

        handler_class = HANDLER_CLASS
        message_type = PROBLEM_REPORT
        schema_class = "OOBProblemReportSchema"

    def __init__(self, *args, **kwargs):
        """Initialize a ProblemReport message instance."""
        super().__init__(*args, **kwargs)


class OOBProblemReportSchema(ProblemReportSchema):
    """Schema for ProblemReport base class."""

    class Meta:
        """Metadata for problem report schema."""

        model_class = OOBProblemReport
        unknown = EXCLUDE

    @pre_dump
    def check_thread_deco(self, obj, **kwargs):
        """Thread decorator, and its thid and pthid, are mandatory."""

        if not obj._decorators.to_dict().get("~thread", {}).keys() >= {"thid", "pthid"}:
            raise ValidationError("Missing required field(s) in thread decorator")

        return obj

    @validates_schema
    def validate_fields(self, data, **kwargs):
        """Validate schema fields."""

        if data.get("description", {}).get("code", "") not in [
            prr.value for prr in ProblemReportReason
        ]:
            raise ValidationError(
                "Value for description.code must be one of "
                f"{[prr.value for prr in ProblemReportReason]}"
            )
