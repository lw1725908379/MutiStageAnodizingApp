import logging

class Config:
    """
    Configuration class for the power supply system.
    Contains all relevant constants, default settings, and register addresses.
    """

    # Serial Communication Settings
    BAUD_RATE = 9600
    TIMEOUT = 1  # seconds

    # Power Supply Register Addresses
    REG_VOLTAGE = 0x0010
    REG_CURRENT = 0x0011
    REG_VOLTAGE_SET = 0x0030
    REG_CURRENT_SET = 0x0031

    REG_NAME = 0x0003
    REG_CLASS_NAME = 0x0004
    REG_DOT = 0x0005
    REG_PROTECTION_STATE = 0x0002
    REG_ADDR = 0x9999
    REG_OPERATIVE_MODE = 0x0001
    REG_DISPLAYED_POWER = 0x0012

    # Protection Status Flags
    OVP = 0x01  # Over Voltage Protection
    OCP = 0x02  # Over Current Protection
    OPP = 0x04  # Over Power Protection
    OTP = 0x08  # Over Temperature Protection
    SCP = 0x10  # Short Circuit Protection

    # Protection Setting Registers
    REG_OVP = 0x0020
    REG_OCP = 0x0021
    REG_OPP = 0x0022

    # Slave Device Address Register
    REG_ADDR_SLAVE = 0x9999

    # Default Settings
    TIMEOUT_READ = 1.0  # seconds
    DEFAULT_SAMPLE_RATE = 1  # Hz

    # Set up logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    @staticmethod
    def update_config(attribute, value):
        if hasattr(Config, attribute):
            expected_type = type(getattr(Config, attribute))
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"{attribute} expects a value of type {expected_type.__name__}, got {type(value).__name__}")
            setattr(Config, attribute, value)
            logging.info(f"Configuration updated: {attribute} = {value}")
        else:
            raise AttributeError(f"{attribute} is not a valid configuration key.")

    @staticmethod
    def load_from_file(file_path):
        with open(file_path, 'r') as file:
            config_data = json.load(file)
            for key, value in config_data.items():
                Config.update_config(key, value)

