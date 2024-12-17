import time
import logging
import threading
import math
from queue import Queue

class ExperimentController:
    """Experiment Controller for managing experiment execution."""

    def __init__(self, serial_manager, stage_manager, storage_manager, data_collector, plot_window, plot_stop_event, storage_stop_event, experiment_done_event, control_strategy):
        self.serial_manager = serial_manager
        self.stage_manager = stage_manager
        self.storage_manager = storage_manager
        self.data_collector = data_collector
        self.plot_window = plot_window
        self.plot_stop_event = plot_stop_event
        self.storage_stop_event = storage_stop_event
        self.experiment_done_event = experiment_done_event
        self.is_experiment_running = False
        self.storage_thread = None

        # The injected control strategy
        self.control_strategy = control_strategy

    def collect_data_with_sample_rate(self, sample_rate):
        """Collect data at a specified sample rate using the chosen control strategy."""
        sample_interval = 1.0 / sample_rate
        logging.info(f"Starting data collection with sample rate: {sample_rate} Hz")

        try:
            for stage_idx, stage in enumerate(self.stage_manager.get_stages(), start=1):
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                logging.debug(f"Starting stage {stage_idx} - Start: {voltage_start} V, End: {voltage_end} V, Duration: {duration} s")

                steps = max(1, int(duration * sample_rate))
                increment = (voltage_end - voltage_start) / steps if steps != 0 else 0.0

                # Set initial voltage
                current_voltage = voltage_start
                self.serial_manager.power_supply.set_voltage(current_voltage)
                self.control_strategy.set_setpoint(current_voltage)

                start_time = time.perf_counter()

                for step in range(steps):
                    cycle_start = time.perf_counter()

                    elapsed_time = time.perf_counter() - start_time
                    # Compute linear target voltage for this step (feedforward)
                    target_voltage = voltage_start + increment * step
                    self.control_strategy.set_setpoint(target_voltage)

                    measured_voltage = self.serial_manager.power_supply.get_voltage()
                    if measured_voltage is None:
                        logging.error("Failed to read voltage, skipping this sample.")
                        continue

                    control_signal = self.control_strategy.update(measured_voltage)
                    self.serial_manager.power_supply.set_voltage(control_signal)

                    self.data_collector.collect_data_for_stage()

                    # Wait until next sample time
                    next_sample_time = start_time + (step + 1) * sample_interval
                    sleep_duration = next_sample_time - time.perf_counter()
                    if sleep_duration > 0:
                        time.sleep(sleep_duration)

                    logging.debug(f"Stage {stage_idx}, Step {step+1}/{steps}, Target: {target_voltage:.2f} V, Measured: {measured_voltage:.2f} V, Control: {control_signal:.2f} V")

                # Ensure final voltage reached
                self.serial_manager.power_supply.set_voltage(voltage_end)
                self.data_collector.collect_data_for_stage()

                logging.info(f"Completed data collection for stage {stage_idx}.")

            self.experiment_done_event.set()
            logging.info("Experiment completed.")
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

        logging.info("Plot window started.")

        # Start storage consumer thread
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()
        logging.info("Storage consumer thread started.")

        # Start data collection thread
        data_thread = threading.Thread(target=self.collect_data_with_sample_rate, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("Data collection thread started.")

    def storage_consumer(self):
        """Storage consumer thread function."""
        while not self.storage_stop_event.is_set():
            time.sleep(0.05)

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        self.experiment_done_event.wait()
        logging.info("Experiment completion signal received.")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("Storage consumer thread has ended.")

        self.is_experiment_running = False
