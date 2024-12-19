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
        self.data_collector = data_collector
        self.plot_window = plot_window
        self.plot_stop_event = plot_stop_event
        self.storage_stop_event = storage_stop_event
        self.experiment_done_event = experiment_done_event
        self.is_experiment_running = False
        self.storage_thread = None

        # Scheduler for precise timing
        self.scheduler = sched.scheduler(time.time, time.sleep)

        # The injected control strategy
        self.control_strategy = control_strategy
        self.control_mode = control_mode

    def _collect_sample(self, stage_idx, start_time, sample_rate, increment, voltage_start, step, total_steps):
        """Collect a single data sample and schedule the next."""
        try:
            target_voltage = voltage_start + increment * step
            self.control_strategy.set_setpoint(target_voltage)

            measured_voltage = self.serial_manager.power_supply.get_voltage()
            if measured_voltage is None:
                logging.warning("Failed to read voltage, using last valid voltage.")
                measured_voltage = target_voltage  # Fallback to the target

            current = self.serial_manager.power_supply.get_current()
            if current is None:
                logging.warning("Failed to read current, using default value.")
                current = 0.0  # Default current value

            # Ensure data integrity
            if measured_voltage < 0:
                logging.warning(f"Invalid measured voltage: {measured_voltage}, setting to 0.")
                measured_voltage = 0.0
            if current < 0:
                logging.warning(f"Invalid current value: {current}, setting to 0.")
                current = 0.0

            control_signal = self.control_strategy.update(measured_voltage)
            try:
                self.serial_manager.power_supply.set_voltage(control_signal)
            except Exception as e:
                logging.error(f"Failed to set control signal: {e}")
                control_signal = 0.0  # Fallback

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

            logging.debug(
                f"Stage {stage_idx}, Step {step}/{total_steps}, "
                f"Target: {target_voltage:.2f} V, Measured: {measured_voltage:.2f} V, Control: {control_signal:.2f} V"
            )

            next_step = step + 1
            if next_step < total_steps:
                next_sample_time = start_time + (next_step / sample_rate)
                self.scheduler.enterabs(next_sample_time, 1, self._collect_sample,
                                        (stage_idx, start_time, sample_rate, increment, voltage_start, next_step,
                                         total_steps))

        except Exception as e:
            logging.error(f"Error during sample collection: {e}")

    def collect_data_with_sample_rate(self, sample_rate):
        """Collect data at a specified sample rate using the chosen control strategy."""
        try:
            for stage_idx, stage in enumerate(self.stage_manager.get_stages(), start=1):
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                logging.info(
                    f"Starting stage {stage_idx} - Start: {voltage_start} V, End: {voltage_end} V, Duration: {duration} s"
                )

                total_steps = max(1, int(duration * sample_rate))
                increment = (voltage_end - voltage_start) / total_steps

                self.serial_manager.power_supply.set_voltage(voltage_start)
                self.control_strategy.set_setpoint(voltage_start)

                start_time = time.time()
                self.scheduler.enterabs(start_time, 1, self._collect_sample,
                                        (stage_idx, start_time, sample_rate, increment, voltage_start, 0, total_steps))

                while not self.experiment_done_event.is_set():
                    self.scheduler.run(blocking=False)
                    time.sleep(0.1)

                logging.info(f"Completed data collection for stage {stage_idx}.")

            logging.info("Experiment completed.")
        except Exception as e:
            logging.error(f"Error during data collection: {e}")

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
        logging.info("Storage consumer thread has started.")
        while not self.storage_stop_event.is_set():
            try:
                experiment_data = self.data_collector.storage_queue.get(timeout=0.1)
                if experiment_data is None:
                    logging.info("Storage consumer received termination signal, exiting.")
                    break

                # Store data
                self.storage_manager.store_data(experiment_data)
                logging.debug(f"Stored data: {experiment_data}")
                self.data_collector.storage_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"An error occurred in the storage consumer thread: {e}")
        logging.info("Storage consumer thread has stopped.")

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
