import queue
import logging
import threading
from exceptions import DataStorageError
from experiment_data import ExperimentData


class DataCollector:
    """Data Collector for collecting and storing datasets."""

    def __init__(self, power_supply, storage_manager, plot_queue=None, max_queue_size=1000):
        """
        Initialize the DataCollector.

        Args:
            power_supply: The power supply instance for reading voltage and current.
            storage_manager: The storage manager instance for storing collected datasets.
            plot_queue: A queue for passing datasets to the plotting system (optional).
            max_queue_size: Maximum size of the storage queue.
        """
        self.power_supply = power_supply
        self.storage_manager = storage_manager
        self.plot_queue = plot_queue
        self.storage_queue = queue.Queue(maxsize=max_queue_size)
        self.storage_thread = threading.Thread(target=self._storage_worker, daemon=True)
        self.is_running = True  # A flag to control the worker thread
        self.storage_thread.start()
        logging.info("DataCollector initialized and storage worker thread started.")

    def _storage_worker(self):
        """Worker thread for storing datasets."""
        logging.info("Storage worker thread has started.")
        while self.is_running or not self.storage_queue.empty():
            try:
                # Wait for datasets from the queue with a timeout
                data = self.storage_queue.get(timeout=0.1)
                if data is None:  # Sentinel value to stop the thread
                    logging.info("Storage worker received sentinel. Exiting.")
                    break

                # Store datasets using the storage manager
                self.storage_manager.store_data(data)
                logging.debug(f"Data successfully stored: {data}")

                # Mark the task as done
                self.storage_queue.task_done()
            except queue.Empty:
                # Timeout waiting for datasets; continue checking the `is_running` flag
                continue
            except DataStorageError as e:
                logging.error(f"Error storing datasets: {e}")
            except Exception as e:
                logging.error(f"Unexpected error in storage worker: {e}")
        logging.info("Storage worker thread has stopped.")

    def collect_data_for_stage(self, experiment_data: ExperimentData):
        """
        Collect datasets from the power supply and enqueue for plotting and storage.

        Args:
            experiment_data: An instance of ExperimentData containing the datasets to be collected.
        """
        try:
            # Enqueue datasets for plotting (if plot_queue is provided)
            if self.plot_queue is not None:
                self.plot_queue.put_nowait((
                    experiment_data.timestamp,
                    experiment_data.measured_voltage,
                    experiment_data.current
                ))
                logging.debug("Data enqueued for plotting.")

            # Enqueue datasets for storage
            self.storage_queue.put_nowait(experiment_data)
            logging.debug(f"Data enqueued for storage: {experiment_data}. Queue size: {self.storage_queue.qsize()}")
        except queue.Full:
            logging.warning("Storage queue is full. Dropping datasets to prevent blocking.")
        except Exception as e:
            logging.exception(f"Error collecting datasets for stage: {e}")

    def close(self):
        """Close the storage worker and wait for it to finish."""
        self.is_running = False
        # Add a sentinel value to ensure the worker thread stops gracefully
        self.storage_queue.put(None)
        self.storage_thread.join()
        logging.info("DataCollector storage worker thread has been closed.")
