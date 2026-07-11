from abc import ABC, abstractmethod


class BaseSearchProvider(ABC):

    @abstractmethod
    def search(self, question: str):
        raise NotImplementedError