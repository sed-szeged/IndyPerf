"""Indy revocation registry management."""

from typing import Sequence

from ..core.profile import Profile
from ..ledger.base import BaseLedger
from ..storage.base import StorageNotFoundError

from .error import RevocationNotSupportedError, RevocationRegistryBadSizeError
from .models.issuer_rev_reg_record import IssuerRevRegRecord
from .models.revocation_registry import RevocationRegistry


class IndyRevocation:
    """Class for managing Indy credential revocation."""

    REV_REG_CACHE = {}

    def __init__(self, profile: Profile):
        """Initialize the IndyRevocation instance."""
        self._profile = profile

    async def init_issuer_registry(
        self,
        cred_def_id: str,
        max_cred_num: int = None,
        revoc_def_type: str = None,
        tag: str = None,
    ) -> "IssuerRevRegRecord":
        """Create a new revocation registry record for a credential definition."""
        ledger = self._profile.inject(BaseLedger)
        async with ledger:
            cred_def = await ledger.get_credential_definition(cred_def_id)
        if not cred_def:
            raise RevocationNotSupportedError("Credential definition not found")
        if not cred_def["value"].get("revocation"):
            raise RevocationNotSupportedError(
                "Credential definition does not support revocation"
            )
        if max_cred_num and not (
            RevocationRegistry.MIN_SIZE <= max_cred_num <= RevocationRegistry.MAX_SIZE
        ):
            raise RevocationRegistryBadSizeError(
                f"Bad revocation registry size: {max_cred_num}"
            )

        record = IssuerRevRegRecord(
            cred_def_id=cred_def_id,
            issuer_did=cred_def_id.split(":")[0],
            max_cred_num=max_cred_num,
            revoc_def_type=revoc_def_type,
            tag=tag,
        )
        async with self._profile.session() as session:
            await record.save(session, reason="Init revocation registry")
        return record

    async def get_active_issuer_rev_reg_record(
        self, cred_def_id: str
    ) -> "IssuerRevRegRecord":
        """Return current active registry for issuing a given credential definition.

        Args:
            cred_def_id: ID of the base credential definition
        """
        async with self._profile.session() as session:
            current = sorted(
                await IssuerRevRegRecord.query_by_cred_def_id(
                    session, cred_def_id, IssuerRevRegRecord.STATE_ACTIVE
                )
            )
        if current:
            return current[0]  # active record is oldest published but not full
        raise StorageNotFoundError(
            f"No active issuer revocation record found for cred def id {cred_def_id}"
        )

    async def get_issuer_rev_reg_record(
        self, revoc_reg_id: str
    ) -> "IssuerRevRegRecord":
        """Return a revocation registry record by identifier.

        Args:
            revoc_reg_id: ID of the revocation registry
        """
        async with self._profile.session() as session:
            return await IssuerRevRegRecord.retrieve_by_revoc_reg_id(
                session, revoc_reg_id
            )

    async def list_issuer_registries(self) -> Sequence["IssuerRevRegRecord"]:
        """List the issuer's current revocation registries."""
        async with self._profile.session() as session:
            return await IssuerRevRegRecord.query(session)

    async def get_ledger_registry(self, revoc_reg_id: str) -> "RevocationRegistry":
        """Get a revocation registry from the ledger, fetching as necessary."""
        if revoc_reg_id in IndyRevocation.REV_REG_CACHE:
            return IndyRevocation.REV_REG_CACHE[revoc_reg_id]

        ledger = self._profile.inject(BaseLedger)
        async with ledger:
            rev_reg = RevocationRegistry.from_definition(
                await ledger.get_revoc_reg_def(revoc_reg_id), True
            )
            IndyRevocation.REV_REG_CACHE[revoc_reg_id] = rev_reg
            return rev_reg
