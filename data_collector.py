import queue
import logging
import threading
import time
from exceptions import DataStorageError

class DataCollector:
    """Data Collector for collecting and storing data."""

    def __init__(self, power_supply, storage_manager, plot_queue):
        self.power_supply = power_supply
        self.storage_manager = storage_manager
        self.plot_queue = plot_queue
        self.storage_queue = queue.Queue()
        self.storage_thread = threading.Thread(target=self._storage_worker, daemon=True)
        self.storage_thread.start()
        logging.debug("DataCollector initialized and storage worker thread started.")

    def _storage_worker(self):
        """Worker thread for storing data."""
        while True:
            data = self.storage_queue.get()
            if data is None:  # Sentinel to stop
                logging.debug("Storage worker received sentinel. Exiting.")
                break

            # data structure, for example: (timestamp, target_voltage, measured_voltage, control_signal, control_mode, current)
            try:
                self.storage_manager.store_data(*data)
                logging.debug(f"Data stored: {data}")
            except DataStorageError as e:
                logging.error(f"Error storing data: {e}")
            self.storage_queue.task_done()

    def collect_data_for_stage(self, timestamp, target_voltage, measured_voltage, control_signal, control_mode,
                               current):
        """Collect data from the power supply and enqueue for plotting and storage."""
        try:
            # Check if voltage and current readings are valid
            voltage = self.power_supply.get_voltage()
            if voltage is None:
                logging.error("Failed to read voltage, skipping this sample.")
                return
            current = self.power_supply.get_current()
            if current is None:
                logging.error("Failed to read current, skipping this sample.")
                return

            # Enqueue data for plotting only if plot_queue is not None
            if self.plot_queue is not None:
                self.plot_queue.put((timestamp, measured_voltage, current))

            # Always enqueue data for storage
            self.storage_queue.put((timestamp, target_voltage, measured_voltage, control_signal, control_mode, current))

            logging.debug(
                f"Collected and enqueued data: {timestamp}, {target_voltage}, {measured_voltage}, {control_signal}, {control_mode}, {current}")
        except Exception as e:
            logging.exception(f"Error collecting data for stage: {e}")

    def close(self):
        """Close the storage worker."""
        self.storage_queue.put(None)
        self.storage_thread.join()
        logging.debug("DataCollector storage worker thread has been closed.")
