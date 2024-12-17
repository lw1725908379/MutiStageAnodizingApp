import time
import logging
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from config import Config
from exceptions import ModbusConnectionError
from utils import handle_exception

class PowerSupply:
    """
    Power Supply class for Modbus RTU communication using pymodbus library.
    """

    def __init__(self, port: str, addr: int, retries: int = 5, delay: float = 1.0):
        self.client = ModbusSerialClient(
            method='rtu',
            port=port,
            baudrate=Config.BAUD_RATE,
            timeout=Config.TIMEOUT
        )
        self.addr = addr
        self._connect_with_retries(retries, delay)
        self.initialize_parameters()

    def _connect_with_retries(self, retries, delay):
        for attempt in range(1, retries + 1):
            if self.client.connect():
                logging.info(f"Successfully connected to Modbus client on port: {self.client.port}")
                return
            else:
                logging.warning(f"Failed to connect to Modbus client on port: {self.client.port}, retry {attempt}/{retries}")
                time.sleep(delay * attempt)
        logging.error(f"Unable to connect after {retries} attempts")
        raise ModbusConnectionError(f"Failed to connect to Modbus client on port: {self.client.port}")

    def initialize_parameters(self):
        self.name = self.read(Config.REG_NAME)
        self.class_name = self.read(Config.REG_CLASS_NAME)

        dot_msg = self.read(Config.REG_DOT)
        self.W_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.A_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.V_dot = 10 ** (dot_msg & 0x0F)

        protection_state_int = self.read(Config.REG_PROTECTION_STATE)
        self.isOVP = protection_state_int & Config.OVP
        self.isOCP = (protection_state_int & Config.OCP) >> 1
        self.isOPP = (protection_state_int & Config.OPP) >> 2
        self.isOTP = (protection_state_int & Config.OTP) >> 3
        self.isSCP = (protection_state_int & Config.SCP) >> 4

        logging.debug(f"Scaling factors - W_dot: {self.W_dot}, A_dot: {self.A_dot}, V_dot: {self.V_dot}")
        logging.debug(f"Protection states - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")

        self.set_voltage(0)

    def read(self, reg_addr: int, reg_len: int = 1):
        try:
            response = self.client.read_holding_registers(reg_addr, reg_len, unit=self.addr)
            if response.isError():
                logging.error(f"Error reading register {reg_addr}: {response}")
                return 0
            if reg_len <= 1:
                return response.registers[0]
            else:
                return (response.registers[0] << 16) | response.registers[1]
        except ModbusException as e:
            handle_exception(e, context=f"Reading register {reg_addr}")
            return 0
        except Exception as e:
            handle_exception(e, context=f"Reading register {reg_addr}")
            return 0

    def write(self, reg_addr: int, data: int, reg_len: int = 1):
        try:
            if reg_len <= 1:
                response = self.client.write_register(reg_addr, data, unit=self.addr)
                if response.isError():
                    logging.error(f"Error writing to register {reg_addr}: {response}")
                    return False
                read_back = self.read(reg_addr)
                logging.debug(f"Wrote {data} to register {reg_addr}, read back: {read_back}")
                return read_back == data
            else:
                high = data >> 16
                low = data & 0xFFFF
                response1 = self.client.write_register(reg_addr, high, unit=self.addr)
                response2 = self.client.write_register(reg_addr + 1, low, unit=self.addr)
                if response1.isError() or response2.isError():
                    logging.error(f"Error writing to registers {reg_addr}, {reg_addr+1}: {response1}, {response2}")
                    return False
                read_back1 = self.read(reg_addr)
                read_back2 = self.read(reg_addr + 1)
                logging.debug(f"Wrote {high} to register {reg_addr}, read back: {read_back1}")
                logging.debug(f"Wrote {low} to register {reg_addr+1}, read back: {read_back2}")
                return read_back1 == high and read_back2 == low
        except ModbusException as e:
            handle_exception(e, context=f"Writing to register {reg_addr}")
            return False
        except Exception as e:
            handle_exception(e, context=f"Writing to register {reg_addr}")
            return False

    def get_voltage(self):
        voltage = self.read(Config.REG_VOLTAGE)
        actual_voltage = voltage / self.V_dot
        logging.debug(f"Read voltage: {voltage} raw, {actual_voltage} V")
        return actual_voltage

    def set_voltage(self, V_input: float = None):
        if V_input is None:
            return self.get_voltage()
        else:
            logging.debug(f"Setting voltage to {V_input} V")
            success = self.write(Config.REG_VOLTAGE_SET, int(V_input * self.V_dot + 0.5))
            if success:
                actual_voltage = self.get_voltage()
                logging.debug(f"Voltage set successfully, actual voltage: {actual_voltage} V")
                return actual_voltage
            else:
                logging.error("Failed to set voltage")
                return None

    def get_current(self):
        current = self.read(Config.REG_CURRENT)
        actual_current = current / self.A_dot
        logging.debug(f"Read current: {current} raw, {actual_current} A")
        return actual_current

    def set_current(self, A_input: float = None):
        if A_input is None:
            return self.get_current()
        else:
            logging.debug(f"Setting current to {A_input} A")
            success = self.write(Config.REG_CURRENT_SET, int(A_input * self.A_dot + 0.5))
            if success:
                actual_current = self.get_current()
                logging.debug(f"Current set successfully, actual current: {actual_current} A")
                return actual_current
            else:
                logging.error("Failed to set current")
                return None

    def get_power(self):
        power = self.read(Config.REG_DISPLAYED_POWER, 2)
        actual_power = power / self.W_dot
        logging.debug(f"Read power: {power} raw, {actual_power} W")
        return actual_power

    def operative_mode(self, mode_input: int = None):
        if mode_input is None:
            return self.read(Config.REG_OPERATIVE_MODE)
        else:
            self.write(Config.REG_OPERATIVE_MODE, mode_input)
            return self.read(Config.REG_OPERATIVE_MODE)

    def close(self):
        if self.client:
            self.client.close()
            logging.info("Modbus client connection closed.")
            self.client = None

    def get_operative_mode(self):
        return self.read(Config.REG_OPERATIVE_MODE)
