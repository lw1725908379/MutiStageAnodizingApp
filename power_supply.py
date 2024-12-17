# power_supply.py
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
        """Attempt to connect to Modbus client with retries and exponential backoff."""
        for attempt in range(1, retries + 1):
            if self.client.connect():
                logging.info(f"Successfully connected to Modbus client on port: {self.client.port}")
                return
            else:
                logging.warning(f"Failed to connect to Modbus client on port: {self.client.port}, retry {attempt}/{retries}")
                time.sleep(delay * attempt)  # Exponential backoff
        logging.error(f"Unable to connect to Modbus client on port: {self.client.port} after {retries} attempts")
        raise ModbusConnectionError(f"Failed to connect to Modbus client on port: {self.client.port}")

    def initialize_parameters(self):
        """Initialize power supply parameters by reading necessary registers."""
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
        """Read holding registers from the power supply."""
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
        """Write data to holding registers."""
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
                    logging.error(f"Error writing to registers {reg_addr} and {reg_addr +1}: {response1}, {response2}")
                    return False
                read_back1 = self.read(reg_addr)
                read_back2 = self.read(reg_addr + 1)
                logging.debug(f"Wrote {high} to register {reg_addr}, read back: {read_back1}")
                logging.debug(f"Wrote {low} to register {reg_addr +1}, read back: {read_back2}")
                return read_back1 == high and read_back2 == low
        except ModbusException as e:
            handle_exception(e, context=f"Writing to register {reg_addr}")
            return False
        except Exception as e:
            handle_exception(e, context=f"Writing to register {reg_addr}")
            return False

    def read_protection_state(self):
        """Read and update protection state flags."""
        protection_state_int = self.read(Config.REG_PROTECTION_STATE)
        self.isOVP = protection_state_int & Config.OVP
        self.isOCP = (protection_state_int & Config.OCP) >> 1
        self.isOPP = (protection_state_int & Config.OPP) >> 2
        self.isOTP = (protection_state_int & Config.OTP) >> 3
        self.isSCP = (protection_state_int & Config.SCP) >> 4
        logging.debug(f"Updated protection states - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")
        return protection_state_int

    def get_voltage(self):
        """Read the current voltage."""
        voltage = self.read(Config.REG_VOLTAGE)
        actual_voltage = voltage / self.V_dot
        logging.debug(f"Read voltage: {voltage} raw, {actual_voltage} V")
        return actual_voltage

    def set_voltage(self, V_input: float = None):
        """Set the voltage to the specified value or read the current voltage."""
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
        """Read the current."""
        current = self.read(Config.REG_CURRENT)
        actual_current = current / self.A_dot
        logging.debug(f"Read current: {current} raw, {actual_current} A")
        return actual_current

    def set_current(self, A_input: float = None):
        """Set the current to the specified value or read the current."""
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
        """Read the displayed power."""
        power = self.read(Config.REG_DISPLAYED_POWER, 2)
        actual_power = power / self.W_dot
        logging.debug(f"Read power: {power} raw, {actual_power} W")
        return actual_power

    def set_over_voltage_protection(self, OVP_input: float = None):
        """Read or set over voltage protection."""
        if OVP_input is None:
            return self.read(Config.REG_OVP) / self.V_dot
        else:
            self.write(Config.REG_OVP, int(OVP_input * self.V_dot + 0.5))
            return self.read(Config.REG_OVP) / self.V_dot

    def set_over_current_protection(self, OCP_input: float = None):
        """Read or set over current protection."""
        if OCP_input is None:
            return self.read(Config.REG_OCP) / self.A_dot
        else:
            self.write(Config.REG_OCP, int(OCP_input * self.A_dot + 0.5))
            return self.read(Config.REG_OCP) / self.A_dot

    def set_over_power_protection(self, OPP_input: float = None):
        """Read or set over power protection."""
        if OPP_input is None:
            return self.read(Config.REG_OPP, 2) / self.W_dot
        else:
            self.write(Config.REG_OPP, int(OPP_input * self.W_dot + 0.5), 2)
            return self.read(Config.REG_OPP, 2) / self.W_dot

    def slave_address(self, addr_input: int = None):
        """Read or set the slave device address."""
        if addr_input is None:
            self.addr = self.read(Config.REG_ADDR_SLAVE)
            return self.addr
        else:
            self.write(Config.REG_ADDR_SLAVE, addr_input)
            self.addr = addr_input
            return self.read(Config.REG_ADDR_SLAVE)

    def set_voltage_and_wait(self, V_input, error_range: float = 0.1, timeout: int = 30):
        """
        Set voltage to the specified value and wait until it stabilizes within the error range.
        """
        old_voltage = self.get_voltage()
        logging.info(f"Setting target voltage from {old_voltage} V to {V_input} V")
        self.set_voltage(V_input)
        start_time = time.time()
        while True:
            current_voltage = self.get_voltage()
            if abs(current_voltage - V_input) <= error_range:
                logging.info(f"Voltage stabilized at {current_voltage} V")
                break
            if (time.time() - start_time) > timeout:
                logging.warning(f"Voltage setting timed out: current voltage {current_voltage} V, target {V_input} V")
                break
            time.sleep(0.5)  # Increase check interval
        elapsed_time = time.time() - start_time
        logging.info(f"Voltage setting completed, actual voltage: {current_voltage} V, time elapsed: {elapsed_time:.2f} seconds")

    def set_voltage_non_blocking(self, V_input):
        """
        Set voltage to the specified value without waiting for verification.
        """
        old_voltage = self.get_voltage()
        logging.info(f"Setting target voltage from {old_voltage} V to {V_input} V (non-blocking)")
        self.set_voltage(V_input)
        logging.info(f"Voltage set command sent: {V_input} V")

    def operative_mode(self, mode_input: int = None):
        """
        Read or set the operative mode.
        :param mode_input: 1 to enable output, 0 to disable
        """
        if mode_input is None:
            return self.read(Config.REG_OPERATIVE_MODE)
        else:
            self.write(Config.REG_OPERATIVE_MODE, mode_input)
            return self.read(Config.REG_OPERATIVE_MODE)

    def close(self):
        """Close the Modbus client connection."""
        if self.client:
            self.client.close()
            logging.info("Modbus client connection closed.")
            self.client = None

    def get_operative_mode(self):
        """Read the current operative mode."""
        return self.read(Config.REG_OPERATIVE_MODE)
