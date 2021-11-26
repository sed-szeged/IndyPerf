"""Base Class for DID Resolvers."""

from abc import ABC, abstractmethod
from enum import Enum
import re
from typing import NamedTuple, Pattern, Sequence, Union
import warnings

from pydid import DID, DIDDocument
from pydid.options import (
    doc_allow_public_key,
    doc_insert_missing_ids,
    vm_allow_controller_list,
    vm_allow_missing_controller,
    vm_allow_type_list,
)

from ..config.injection_context import InjectionContext
from ..core.error import BaseError
from ..core.profile import Profile


class ResolverError(BaseError):
    """Base class for resolver exceptions."""


class DIDNotFound(ResolverError):
    """Raised when DID is not found in verifiable data registry."""


class DIDMethodNotSupported(ResolverError):
    """Raised when no resolver is registered for a given did method."""


class ResolverType(Enum):
    """Resolver Type declarations."""

    NATIVE = "native"
    NON_NATIVE = "non-native"


class ResolutionMetadata(NamedTuple):
    """Resolution Metadata."""

    resolver_type: ResolverType
    resolver: str
    retrieved_time: str
    duration: int

    def serialize(self) -> dict:
        """Return serialized resolution metadata."""
        return {**self._asdict(), "resolver_type": self.resolver_type.value}


class ResolutionResult:
    """Resolution Class to pack the DID Doc and the resolution information."""

    def __init__(self, did_document: DIDDocument, metadata: ResolutionMetadata):
        """Initialize Resolution.

        Args:
            did_doc: DID Document resolved
            resolver_metadata: Resolving details
        """
        self.did_document = did_document
        self.metadata = metadata

    def serialize(self) -> dict:
        """Return serialized resolution result_4."""
        return {
            "did_document": self.did_document.serialize(),
            "metadata": self.metadata.serialize(),
        }


class BaseDIDResolver(ABC):
    """Base Class for DID Resolvers."""

    def __init__(self, type_: ResolverType = None):
        """Initialize BaseDIDResolver.

        Args:
            type_ (Type): Type of resolver, native or non-native
        """
        self.type = type_ or ResolverType.NON_NATIVE

    @abstractmethod
    async def setup(self, context: InjectionContext):
        """Do asynchronous resolver setup."""

    @property
    def native(self):
        """Return if this resolver is native."""
        return self.type == ResolverType.NATIVE

    @property
    def supported_methods(self) -> Sequence[str]:
        """Return supported methods.

        DEPRECATED: Use supported_did_regex instead.
        """
        return []

    @property
    def supported_did_regex(self) -> Pattern:
        """Supported DID regex for matching this resolver to DIDs it can resolve.

        Override this property with a class var or similar to use regex
        matching on DIDs to determine if this resolver supports a given DID.
        """
        raise NotImplementedError(
            "supported_did_regex must be overriden by subclasses of BaseResolver "
            "to use default supports method"
        )

    async def supports(self, profile: Profile, did: str) -> bool:
        """Return if this resolver supports the given DID.

        Override this method to determine if this resolver supports a DID based
        on information other than just a regular expression; i.e. check a value
        in storage, query a resolver connection record, etc.
        """
        try:
            supported_did_regex = self.supported_did_regex
        except NotImplementedError as error:
            if not self.supported_methods:
                raise error
            warnings.warn(
                "BaseResolver.supported_methods is deprecated; "
                "use supported_did_regex instead",
                DeprecationWarning,
            )

            supported_did_regex = re.compile(
                "^did:(?:{}):.*$".format("|".join(self.supported_methods))
            )

        return bool(supported_did_regex.match(did))

    async def resolve(self, profile: Profile, did: Union[str, DID]) -> DIDDocument:
        """Resolve a DID using this resolver."""
        if isinstance(did, DID):
            did = str(did)
        else:
            DID.validate(did)
        if not await self.supports(profile, did):
            raise DIDMethodNotSupported(
                f"{self.__class__.__name__} does not support DID method for: {did}"
            )

        doc_dict = await self._resolve(profile, did)
        return DIDDocument.deserialize(
            doc_dict,
            options={
                doc_insert_missing_ids,
                doc_allow_public_key,
                vm_allow_controller_list,
                vm_allow_missing_controller,
                vm_allow_type_list,
            },
        )

    @abstractmethod
    async def _resolve(self, profile: Profile, did: str) -> dict:
        """Resolve a DID using this resolver."""
