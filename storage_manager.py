import logging
from exceptions import DataStorageError
import os
import csv
from datetime import datetime
from experiment_data import ExperimentData


class StorageManager:
    """
    Storage Manager to handle datasets saving.
    This class provides functionality to initialize, write to, and close a CSV storage file for experimental datasets.
    """

    def __init__(self, storage_path):
        """
        Initialize the StorageManager with a storage path.

        Args:
            storage_path (str): The directory path where datasets will be saved.
        """
        self.storage_path = storage_path
        self.file_path = None
        self.file = None
        self.writer = None
        self._is_data_saved = False

    def is_data_saved(self):
        return self._is_data_saved
    def initialize_storage(self):
        """
        Initialize the storage file for datasets saving.

        Returns:
            tuple: (bool, str) indicating success and a corresponding message.
        """
        # Validate the storage path
        if not os.path.isdir(self.storage_path):
            logging.error("Invalid storage path provided.")
            return False, "Invalid storage path"

        # Generate a unique filename based on the current timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"experiment_data_{timestamp_str}.csv"
        self.file_path = os.path.join(self.storage_path, filename)

        try:
            # Open the file for writing and initialize the CSV writer
            self.file = open(self.file_path, 'w', newline='')
            self.writer = csv.writer(self.file)

            # Write the header row to the CSV file
            self.writer.writerow([
                "Timestamp", "TargetVoltage", "MeasuredVoltage", "ControlSignal",
                "ControlMode", "Current", "FeedforwardKp", "PID_Kp", "PID_Ki", "PID_Kd"
            ])

            logging.info(f"Storage initialized at {self.file_path}")
            return True, f"Storage initialized: {self.file_path}"
        except Exception as e:
            logging.error(f"Failed to initialize storage: {e}")
            return False, str(e)

    def store_data(self, experiment_data: ExperimentData):
        """
        Store a single datasets record in the CSV file.

        Args:
            experiment_data (ExperimentData): The datasets object to store.

        Raises:
            DataStorageError: If the storage is not initialized.
        """
        if not self.writer:
            raise DataStorageError("Storage not initialized")

        try:
            # Write a row of datasets to the CSV file
            self.writer.writerow([
                experiment_data.timestamp,
                experiment_data.target_voltage,
                experiment_data.measured_voltage,
                experiment_data.control_signal,
                experiment_data.control_mode,
                experiment_data.current,
                experiment_data.feedforward_kp,
                experiment_data.pid_kp,
                experiment_data.pid_ki,
                experiment_data.pid_kd
            ])
            self._is_data_saved = True
            logging.debug(f"Data stored: {experiment_data}")
        except Exception as e:
            logging.error(f"Error storing datasets: {e}")
            raise DataStorageError(f"Failed to store datasets: {e}")

    def close_storage(self):
        """
        Close the storage file and clean up resources.
        """
        if self.file:
            try:
                self.file.close()
                logging.info(f"Storage file {self.file_path} successfully closed.")
            except Exception as e:
                logging.error(f"Error closing storage file: {e}")
            finally:
                self.file = None
                self.writer = None
