"""Abstract base class for EHR provider clients.

Defines the interface that any EHR backend (OpenEMR, Epic, Cerner, etc.)
must implement. Both FHIRClient and MockFHIRClient inherit from this,
ensuring a consistent API and making it straightforward to swap backends.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseEHRProvider(ABC):
    """Abstract interface for EHR data access."""

    @abstractmethod
    async def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """GET a resource by path with optional query parameters."""
        ...

    @abstractmethod
    async def search(
        self, resource_type: str, params: Optional[dict] = None
    ) -> list[dict[str, Any]]:
        """Search for resources of a given type."""
        ...

    @abstractmethod
    async def get_resource(
        self, resource_type: str, resource_id: str
    ) -> dict[str, Any]:
        """Retrieve a single resource by type and ID."""
        ...

    @abstractmethod
    async def post(self, path: str, json_body: dict) -> dict[str, Any]:
        """Create a resource via POST."""
        ...

    @abstractmethod
    async def create_resource(
        self, resource_type: str, resource: dict
    ) -> dict[str, Any]:
        """Create a new resource of the given type."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any underlying connections."""
        ...
