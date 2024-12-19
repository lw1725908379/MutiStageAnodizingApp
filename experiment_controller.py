import queue
import time
import logging
import sched
import threading
from experiment_data import ExperimentData


class ExperimentController:
    """Experiment Controller for managing experiment execution."""

    def __init__(self, serial_manager, stage_manager, storage_manager, data_collector, plot_window, plot_stop_event, storage_stop_event, experiment_done_event, control_strategy, control_mode):
        self.serial_manager = serial_manager
        self.stage_manager = stage_manager
        self.storage_manager = storage_manager
        self.data_collector = data_collector  # Use DataCollector for storage
        self.plot_window = plot_window
        self.plot_stop_event = plot_stop_event
        self.storage_stop_event = storage_stop_event
        self.experiment_done_event = experiment_done_event
        self.is_experiment_running = False
        self.control_strategy = control_strategy
        self.control_mode = control_mode

    def collect_data_with_sample_rate(self, sample_rate):
        """Collect data at a specified sample rate using the chosen control strategy."""
        try:
            for stage_idx, stage in enumerate(self.stage_manager.get_stages(), start=1):
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                logging.info(f"Starting stage {stage_idx} - Start: {voltage_start} V, End: {voltage_end} V, Duration: {duration} s")

                total_steps = max(1, int(duration * sample_rate))
                increment = (voltage_end - voltage_start) / total_steps
                self.serial_manager.power_supply.set_voltage(voltage_start)
                self.control_strategy.set_setpoint(voltage_start)

                start_time = time.time()

                for step in range(total_steps):
                    target_voltage = voltage_start + increment * step
                    self.control_strategy.set_setpoint(target_voltage)

                    measured_voltage = self.serial_manager.power_supply.get_voltage() or target_voltage
                    current = self.serial_manager.power_supply.get_current() or 0.0

                    control_signal = self.control_strategy.update(measured_voltage)
                    self.serial_manager.power_supply.set_voltage(control_signal)

                    # Collect data
                    self.data_collector.collect_data_for_stage(
                        ExperimentData(
                            timestamp=time.time(),
                            target_voltage=target_voltage,
                            measured_voltage=measured_voltage,
                            control_signal=control_signal,
                            control_mode=self.control_mode,
                            current=current,
                            feedforward_kp=getattr(self.control_strategy, 'Kp', None) if self.control_mode == "Feedforward" else None,
                            pid_kp=getattr(self.control_strategy, 'Kp', None) if self.control_mode == "PID" else None,
                            pid_ki=getattr(self.control_strategy, 'Ki', None) if self.control_mode == "PID" else None,
                            pid_kd=getattr(self.control_strategy, 'Kd', None) if self.control_mode == "PID" else None
                        )
                    )

                    # Ensure proper timing
                    elapsed_time = time.time() - start_time
                    expected_time = (step + 1) / sample_rate
                    sleep_time = expected_time - elapsed_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                logging.info(f"Completed data collection for stage {stage_idx}.")

            logging.info("Experiment completed.")
            self.experiment_done_event.set()
        except Exception as e:
            logging.error(f"Error during data collection: {e}")
            self.experiment_done_event.set()

    def start_experiment(self, sample_rate):
        """Start the experiment with the given sample rate."""
        if self.is_experiment_running:
            logging.warning("Attempted to start an experiment, but one is already running.")
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        logging.info("Starting experiment...")

        # Start data collection thread
        data_thread = threading.Thread(target=self.collect_data_with_sample_rate, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("Data collection thread started.")

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        self.experiment_done_event.wait()
        logging.info("Experiment completion signal received.")
        self.plot_stop_event.set()
        self.is_experiment_running = False

