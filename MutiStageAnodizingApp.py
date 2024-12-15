import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading
import numpy as np
import serial
import serial.tools.list_ports
import os
import csv
from datetime import datetime
import pymodbus as modbus_rtu

#Configuration class, centralized management of all constants
class Config:
    # Serial communication configuration
    BAUD_RATE = 9600
    TIMEOUT = 1

    # Power register address
    REG_VOLTAGE = 0x0010
    REG_CURRENT = 0x0011
    REG_VOLTAGE_SET = 0x0030
    REG_CURRENT_SET = 0x0031
    REG_NAME = 0x0003
    REG_CLASS_NAME = 0x0004
    REG_DOT = 0x0005
    REG_PROTECTION_STATE = 0x0002

    # Power protection status flag
    OVP = 0x01
    OCP = 0x02
    OPP = 0x04
    OTP = 0x08
    SCP = 0x10

    #Default timeout
    TIMEOUT_READ = 1.0

    # Default sampling frequency
    DEFAULT_SAMPLE_RATE = 10  # 10Hz


class PowerSupply:
    """
    Power Class
    """

    def __init__(self, serial_obj: serial.Serial, addr: int):
        """
        Constructor
        :param serial_obj: serial port class
        :param addr: slave address
        """
        self.modbus_rtu_obj = modbus_rtu.RtuMaster(serial_obj)
        self.modbus_rtu_obj.set_timeout(Config.TIMEOUT_READ)
        self.addr = addr
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

        self.V(0)

    def read(self, reg_addr: int, reg_len: int = 1):
        """
        Read register
        :param reg_addr: register address
        :param reg_len: number of registers, 1~2
        :return: data
        """
        if reg_len <= 1:
            return self.modbus_rtu_obj.execute(self.addr, modbus_rtu.READ_HOLDING_REGISTERS, reg_addr, reg_len)[0]
        elif reg_len >= 2:
            raw_tuple = self.modbus_rtu_obj.execute(self.addr, modbus_rtu.READ_HOLDING_REGISTERS, reg_addr, reg_len)
            return raw_tuple[0] << 16 | raw_tuple[1]

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        """
        Write data
            :param reg_addr: register address
            :param data: data to be written
            :param data_len: data length
            :return: write status
        """
        if data_len <= 1:
            self.modbus_rtu_obj.execute(self.addr, modbus_rtu.WRITE_SINGLE_REGISTER, reg_addr, output_value=data)
            if self.read(reg_addr) == data:
                return True
            else:
                return False
        elif data_len >= 2:
            self.modbus_rtu_obj.execute(self.addr, modbus_rtu.WRITE_SINGLE_REGISTER, reg_addr, output_value=data >> 16)
            self.modbus_rtu_obj.execute(self.addr, modbus_rtu.WRITE_SINGLE_REGISTER, reg_addr + 1,
                                        output_value=data & 0xFFFF)
            if self.read(reg_addr) == (data >> 16) and self.read(reg_addr + 1) == (data & 0xFFFF):
                return True
            else:
                return False

    def V(self, V_input: float = None):
        """
        Read the meter voltage or write the target voltage
            :param V_input: voltage value, unit: volt
            :return: meter voltage or target voltage
        """
        if V_input is None:
            return self.read(Config.REG_VOLTAGE) / self.V_dot
        else:
            self.write(Config.REG_VOLTAGE_SET, int(V_input * self.V_dot + 0.5))
            return self.read(Config.REG_VOLTAGE_SET) / self.V_dot

    def A(self, A_input: float = None):
        """
        Read the meter current or write the limit current
            :param A_input: current value, unit: ampere
            :return: meter current or limit current
        """
        if A_input is None:
            return self.read(Config.REG_CURRENT) / self.A_dot
        else:
            self.write(Config.REG_CURRENT_SET, int(A_input * self.A_dot + 0.5))
            return self.read(Config.REG_CURRENT_SET) / self.A_dot


class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Experiment Control Panel")

        # Initialize serial connection objects
        self.serial_obj = None  # Placeholder for serial object
        self.power_supply = None  # Placeholder for power supply object

        # List to store experiment stages
        self.stages = []

        # Serial port selection UI
        self.label_serial = tk.Label(root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5)

        self.serial_ports = self.get_serial_ports()  # Retrieve list of available serial ports
        self.combo_serial = ttk.Combobox(root, values=self.serial_ports)
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5)
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)  # Bind event for port selection

        # Voltage input fields for start and end values
        self.label_voltage_start = tk.Label(root, text="Initial Voltage (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5)

        self.entry_voltage_start = tk.Entry(root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5)

        self.label_voltage_end = tk.Label(root, text="Termination Voltage (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5)

        self.entry_voltage_end = tk.Entry(root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5)

        # Time duration input field
        self.label_time = tk.Label(root, text="Set Time (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5)

        self.entry_time = tk.Entry(root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5)

        # Sampling frequency input field
        self.label_sample_rate = tk.Label(root, text="Sampling Rate (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5)

        self.entry_sample_rate = tk.Entry(root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5)
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))  # Default value: 10 Hz

        # Path selection for data storage
        self.label_storage_path = tk.Label(root, text="Storage Path:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5)

        self.entry_storage_path = tk.Entry(root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5)

        self.button_browse = tk.Button(root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5)

        # Button to add a new experiment stage
        self.button_add_stage = tk.Button(root, text="Add Stage", command=self.add_stage)
        self.button_add_stage.grid(row=6, column=0, columnspan=2, pady=5)

        # Button to initiate the experiment
        self.button_start = tk.Button(root, text="Start Experiment", command=self.start_experiment)
        self.button_start.grid(row=7, column=0, columnspan=2, pady=5)

    def get_serial_ports(self):
        """Retrieve and return the list of available serial ports on the system"""
        ports = list(serial.tools.list_ports.comports())
        return [port.device for port in ports] if ports else []

    def set_serial_port(self, event):
        """
        Establishes a serial connection to the selected port
        :param event: Event triggered by serial port selection
        """
        port = self.combo_serial.get()
        if port:
            # Initialize the serial connection and power supply object
            self.serial_obj = serial.Serial(port, Config.BAUD_RATE, timeout=Config.TIMEOUT)
            self.power_supply = PowerSupply(self.serial_obj, 1)

    def browse_storage_path(self):
        """
        Opens a dialog for the user to browse and select a directory for data storage
        """
        path = filedialog.askdirectory()
        if path:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, path)

    def add_stage(self):
        """
        Add a new stage to the experiment with user-defined parameters
        """
        voltage_start = float(self.entry_voltage_start.get())
        voltage_end = float(self.entry_voltage_end.get())
        time_duration = float(self.entry_time.get())
        sample_rate = int(self.entry_sample_rate.get())
        storage_path = self.entry_storage_path.get()

        # Store the parameters for the new stage
        self.stages.append({
            'voltage_start': voltage_start,
            'voltage_end': voltage_end,
            'time_duration': time_duration,
            'sample_rate': sample_rate,
            'storage_path': storage_path
        })
        messagebox.showinfo("Stage Added", "The stage has been successfully added!")

    def start_experiment(self):
        """
        Starts the experiment by initiating the necessary checks and launching the experiment in a new thread
        """
        if not self.power_supply:
            messagebox.showerror("Error", "Power supply is not connected!")
            return

        if not self.stages:
            messagebox.showerror("Error", "Please add at least one experiment stage!")
            return

        # Execute the experiment in a separate thread to avoid blocking the GUI
        threading.Thread(target=self.run_experiment).start()

    def run_experiment(self):
        """
        Run the experiment sequentially across all defined stages, recording data for each stage
        """
        for stage in self.stages:
            # Set the voltage for the current stage
            self.power_supply.V(stage['voltage_start'])
            start_time = time.time()

            # List to store collected data during the experiment
            data = []

            while time.time() - start_time < stage['time_duration']:
                # Collect data at specified intervals
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                voltage = self.power_supply.V()
                current = self.power_supply.A()
                data.append([current_time, voltage, current, voltage * current])  # Time(s), Voltage(V), Current(A), Power(W)

                time.sleep(1 / stage['sample_rate'])  # Sleep according to the sampling rate

            # Save the collected data to a CSV file
            self.save_to_csv(data, stage['storage_path'])

            messagebox.showinfo("Experiment Finished", "Experiment completed successfully!")

    def save_to_csv(self, data, storage_path):
        """
        Save the collected data to a CSV file at the specified storage path
        :param data: Data to be saved (time, voltage, current, power)
        :param storage_path: Directory where the CSV file will be saved
        """
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)  # Create the directory if it doesn't exist

        filename = os.path.join(storage_path, f"Experiment_Data_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")

        # Write the data to a CSV file
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'Voltage (V)', 'Current (A)', 'Power (W)'])  # CSV headers
            writer.writerows(data)  # Write the recorded data



# 运行GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
