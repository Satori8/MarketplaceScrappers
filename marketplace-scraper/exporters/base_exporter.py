from abc import ABC, abstractmethod
from typing import List
from core.models import RawProduct

class BaseExporter(ABC):
    @abstractmethod
    def export(self, products: List[RawProduct], filename: str = "") -> str:
        """
        Export list of products to a file or cloud service.
        Returns the path or URL of the exported resource.
        """
        pass
