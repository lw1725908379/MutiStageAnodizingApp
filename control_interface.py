from abc import ABC, abstractmethod

class IControlStrategy(ABC):
    """
    An interface that all control strategies must implement.
    This interface ensures a consistent method set for setting
    a target setpoint, updating output based on the measured value,
    and resetting internal states.
    """

    @abstractmethod
    def set_setpoint(self, value: float):
        pass

    @abstractmethod
    def update(self, measured_value: float) -> float:
        pass

    @abstractmethod
    def reset(self):
        pass
