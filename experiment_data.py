from dataclasses import dataclass

@dataclass
class ExperimentData:
    """Data structure to hold experiment data for collection and storage."""
    timestamp: float
    target_voltage: float
    measured_voltage: float
    control_signal: float
    control_mode: str
    current: float
    feedforward_kp: float = None  # Default to None for Feedforward
    pid_kp: float = None          # Default to None for PID
    pid_ki: float = None          # Default to None for PID
    pid_kd: float = None          # Default to None for PID
