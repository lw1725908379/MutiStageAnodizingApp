class ModbusConnectionError(Exception):
    """Exception raised when Modbus connection fails."""
    pass

class DataStorageError(Exception):
    """Exception raised when datasets storage encounters an error."""
    pass
