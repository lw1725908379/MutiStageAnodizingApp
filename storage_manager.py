import logging
from exceptions import DataStorageError
import os
import csv

class StorageManager:
    """Storage Manager to handle data saving."""

    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.file_path = None
        self.file = None
        self.writer = None

    def initialize_storage(self):
        """Initialize the storage file for data saving."""
        if not os.path.isdir(self.storage_path):
            return False, "Invalid storage path"

        self.file_path = os.path.join(self.storage_path, "experiment_data.csv")

        try:
            self.file = open(self.file_path, 'w', newline='')
            self.writer = csv.writer(self.file)
            self.writer.writerow(["Timestamp", "Voltage(V)", "Current(A)"])
            logging.info(f"Storage initialized at {self.file_path}")
            return True, f"Storage initialized: {self.file_path}"
        except Exception as e:
            logging.error(f"Failed to initialize storage: {e}")
            return False, str(e)

    def store_data(self, timestamp, voltage, current):
        """Store a single data record."""
        if not self.writer:
            raise DataStorageError("Storage not initialized")

        self.writer.writerow([timestamp, voltage, current])

    def close_storage(self):
        """Close the storage file."""
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
            logging.info("Storage manager closed.")
