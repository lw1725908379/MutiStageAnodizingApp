import queue
import logging
import threading
from exceptions import DataStorageError
from experiment_data import ExperimentData


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

            try:
                # Pass the ExperimentData object directly
                self.storage_manager.store_data(data)
                logging.debug(f"Data stored: {data}")
            except DataStorageError as e:
                logging.error(f"Error storing data: {e}")
            self.storage_queue.task_done()

    def collect_data_for_stage(self, experiment_data: ExperimentData):
        """Collect data from the power supply and enqueue for plotting and storage."""
        try:
            # Enqueue data for plotting (if plot_queue is not None)
            if self.plot_queue is not None:
                self.plot_queue.put((
                    experiment_data.timestamp,
                    experiment_data.measured_voltage,
                    experiment_data.current
                ))

            # Enqueue data for storage
            self.storage_queue.put(experiment_data)

            logging.debug(f"Collected data: {experiment_data}")
        except Exception as e:
            logging.exception(f"Error collecting data for stage: {e}")

    def close(self):
        """Close the storage worker."""
        self.storage_queue.put(None)
        self.storage_thread.join()
        logging.debug("DataCollector storage worker thread has been closed.")
