# experiment_controller.py
import time
import logging
import threading
import math
from queue import Queue

class ExperimentController:
    """Experiment Controller for managing experiment execution."""

    def __init__(self, serial_manager, stage_manager, storage_manager, data_collector, plot_window, plot_stop_event, storage_stop_event, experiment_done_event):
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

    def collect_data_with_sample_rate(self, sample_rate):
        """Collect data based on the sample rate."""
        sample_interval = 1.0 / sample_rate
        logging.info(f"Starting data collection with sample rate: {sample_rate} Hz")

        try:
            for stage in self.stage_manager.get_stages():
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                if duration <= 0:
                    voltage_increment = 0
                    voltage_steps = 1  # Ensure at least one step
                else:
                    voltage_steps = math.ceil(duration * sample_rate)  # Use math.ceil to ensure enough steps
                    voltage_increment = (voltage_end - voltage_start) / voltage_steps if voltage_steps != 0 else 0

                logging.debug(f"Starting stage - Start Voltage: {voltage_start} V, End Voltage: {voltage_end} V, "
                              f"Duration: {duration} s, Voltage Increment: {voltage_increment} V")

                current_voltage = voltage_start
                self.serial_manager.power_supply.set_voltage(current_voltage)

                start_time = time.perf_counter()
                for step in range(voltage_steps):
                    cycle_start = time.perf_counter()

                    # Update voltage
                    current_voltage += voltage_increment
                    # Ensure voltage does not exceed the target
                    if voltage_increment > 0 and current_voltage > voltage_end:
                        current_voltage = voltage_end
                    elif voltage_increment < 0 and current_voltage < voltage_end:
                        current_voltage = voltage_end

                    # Set new voltage
                    self.serial_manager.power_supply.set_voltage(current_voltage)

                    # Collect data
                    self.data_collector.collect_data_for_stage()

                    # Calculate next sample time
                    next_sample_time = start_time + (step + 1) * sample_interval
                    sleep_duration = next_sample_time - time.perf_counter()
                    if sleep_duration > 0:
                        time.sleep(sleep_duration)

                    logging.debug(f"Step {step + 1}/{voltage_steps}: Voltage set to {current_voltage} V")

                # Removed the following lines to prevent extending the experiment duration
                # self.serial_manager.power_supply.set_voltage(voltage_end)
                # self.data_collector.collect_data_for_stage()

                logging.info("Completed data collection for this stage.")

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

        # PlotWindow 不需要额外调用 start_animation，因为它已在初始化时处理 plot_queue
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
            time.sleep(0.05)  # Simple wait mechanism; can be optimized if needed

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        self.experiment_done_event.wait()
        logging.info("Experiment completion signal received.")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("Storage consumer thread has ended.")

        # Do not disconnect serial here; leave to the GUI's on_closing
        self.is_experiment_running = False
        # GUI will show a message externally
