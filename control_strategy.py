import time
from control_interface import IControlStrategy
import logging
class LinearStrategy(IControlStrategy):
    """A simple strategy that always outputs the setpoint as control signal."""
    def __init__(self):
        self.setpoint = 0.0

    def set_setpoint(self, value: float):
        self.setpoint = value

    def update(self, measured_value: float) -> float:
        # Just return the setpoint directly
        return self.setpoint

    def reset(self):
        self.setpoint = 0.0


class PIDStrategy(IControlStrategy):
    """A PID control strategy implementation."""
    def __init__(self, Kp, Ki, Kd, output_limits=(0, 102)):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.output_limits = output_limits
        self.setpoint = 0.0
        self._integral = 0.0
        self._previous_error = 0.0
        self._last_time = time.time()

    def set_setpoint(self, value: float):
        self.setpoint = value
        self._integral = 0.0
        self._previous_error = 0.0
        self._last_time = time.time()

    def update(self, measured_value: float) -> float:
        current_time = time.time()
        delta_time = current_time - self._last_time
        if delta_time <= 0.0:
            delta_time = 1e-16

        error = self.setpoint - measured_value
        self._integral += error * delta_time
        derivative = (error - self._previous_error) / delta_time

        output = self.Kp * error + self.Ki * self._integral + self.Kd * derivative
        # Apply output limits
        output = max(self.output_limits[0], min(output, self.output_limits[1]))

        self._previous_error = error
        self._last_time = current_time

        return output

    def reset(self):
        self._integral = 0.0
        self._previous_error = 0.0
        self._last_time = time.time()


class FeedforwardWithFeedbackStrategy(IControlStrategy):
    """
    Feedforward + small feedback strategy.
    output = setpoint + Kp*(setpoint - measured_value)
    This allows the system to follow a predetermined trajectory (the feedforward part)
    and then apply a small correction based on the error.
    """

    def __init__(self, Kp=0.01, output_limits=(0, 100)):
        self.setpoint = 0.0
        self.Kp = Kp
        self.output_limits = output_limits

    def set_setpoint(self, value: float):
        self.setpoint = value
        logging.debug(f"Setpoint updated to: {self.setpoint}")

    def update(self, measured_value: float) -> float:
        error = self.setpoint - measured_value
        output = self.setpoint + self.Kp * error
        # Limit output
        output = max(self.output_limits[0], min(output, self.output_limits[1]))
        logging.debug(f"FeedforwardWithFeedbackStrategy updated to: {output}")
        return output

    def reset(self):
        self.setpoint = 0.0
