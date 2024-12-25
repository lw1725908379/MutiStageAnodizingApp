import serial.tools.list_ports
import logging
from power_supply import PowerSupply
from exceptions import ModbusConnectionError

class SerialManager:
    """
    Serial Manager for handling serial port connections.
    This class facilitates discovering, connecting, and disconnecting serial ports
    for the Modbus RTU communication with the power supply.
    """

    def __init__(self):
        self.power_supply = None

    def get_serial_ports(self):
        """
        List available serial ports.

        Returns:
            list: A list of available serial port device names.
        """
        ports = [port.device for port in serial.tools.list_ports.comports()]
        logging.debug(f"Available serial ports: {ports}")
        return ports

    def connect(self, port, addr=1):
        """
        Connect to the specified serial port.

        Args:
            port (str): The serial port to connect to.
            addr (int): The Modbus address of the power supply (default is 1).

        Returns:
            tuple: (bool, str) - A success flag and a message.
        """
        if port:
            try:
                self.power_supply = PowerSupply(port, addr)
                logging.info(f"Successfully connected to serial port: {port}")
                return True, f"Connected to {port}"
            except ModbusConnectionError as e:
                logging.error(f"Failed to connect to serial port {port}: {e}")
                return False, f"Failed to connect to {port}\n{e}"
            except Exception as e:
                logging.error(f"Failed to connect to serial port {port}: {e}")
                return False, f"Failed to connect to {port}\n{e}"
        else:
            logging.warning("No serial port selected.")
            return False, "No serial port selected."

    def disconnect(self):
        """
        Disconnect the current serial port.

        This closes the Modbus client connection if it exists.
        """
        if self.power_supply and self.power_supply.client:
            self.power_supply.close()
            logging.info("Modbus client connection closed.")
            self.power_supply = None
        else:
            logging.warning("No active Modbus client connection to close.")




