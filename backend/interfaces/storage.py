from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class DetectionRepository(ABC):
    """Interface for detection storage backends."""

    @abstractmethod
    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Save a detection record, return the saved record with timestamp."""
        ...

    @abstractmethod
    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent records, up to limit."""
        ...

    @abstractmethod
    def get_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Get records for a specific date (YYYY-MM-DD)."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Delete all records."""
        ...