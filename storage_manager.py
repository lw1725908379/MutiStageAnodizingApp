# storage_manager.py
import os
import csv
import threading
import logging
from datetime import datetime
from exceptions import DataStorageError

class StorageManager:
    """Storage Manager for handling data storage."""

    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.storage_file = None
        self.storage_writer = None
        self.lock = threading.Lock()
        self.file_path = None

    def initialize_storage(self):
        """Initialize the CSV storage file."""
        if not self.storage_path:
            logging.error("Storage path not specified.")
            return False, "Storage path not specified."

        self.file_path = os.path.join(self.storage_path, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            self.storage_file = open(self.file_path, mode='w', newline='')
            self.storage_writer = csv.writer(self.storage_file)
            self.storage_writer.writerow(["Timestamp", "Voltage (V)", "Current (A)", "Power (W)"])
            logging.info(f"Initialized data storage file: {self.file_path}")
            return True, f"Data storage initialized at {self.file_path}"
        except Exception as e:
            logging.exception(f"Failed to initialize data storage file: {e}")
            return False, f"Failed to create CSV file.\n{e}"

    def store_data(self, timestamp, voltage, current):
        """Store a data record into the CSV file."""
        if self.storage_writer:
            power = voltage * current
            try:
                with self.lock:
                    self.storage_writer.writerow([timestamp, voltage, current, power])
                    self.storage_file.flush()
                logging.debug(f"Stored data: {timestamp}, {voltage}, {current}, {power}")
            except Exception as e:
                logging.exception(f"Failed to store data: {e}")
                raise DataStorageError(f"Failed to store data: {e}")
        else:
            logging.error("Storage writer not initialized.")
            raise DataStorageError("Storage writer not initialized.")

    def close_storage(self):
        """Close the storage file."""
        if self.storage_file:
            try:
                self.storage_file.close()
                logging.info("Closed data storage file.")
            except Exception as e:
                logging.error(f"Error closing storage file: {e}")
            finally:
                self.storage_file = None
                self.storage_writer = None
        else:
            logging.warning("No storage file to close.")
