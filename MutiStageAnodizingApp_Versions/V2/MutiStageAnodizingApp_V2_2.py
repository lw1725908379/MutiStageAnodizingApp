import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import time
import threading
import serial
import serial.tools.list_ports
import os
import csv
from datetime import datetime
import pymodbus as modbus_rtu
import queue


# Configuration class, centralized management of all constants
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

    # Default timeout
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
        self.is_experiment_running = False  # Flag to prevent multiple experiments

        # List to store experiment stages
        self.stages = []

        # Queue for storing experimental data
        self.data_queue = queue.Queue()

        # Event to signal the experiment has finished
        self.experiment_done_event = threading.Event()
        self.stage_done_event = threading.Event()  # For synchronizing stages

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
        self.button_start.grid(row=7, column=0, columnspan=2, pady=10)

    def get_serial_ports(self):
        """Get a list of available serial ports."""
        return [port.device for port in serial.tools.list_ports.comports()]

    def set_serial_port(self, event):
        """Set the selected serial port."""
        serial_port = self.combo_serial.get()
        if serial_port:
            self.serial_obj = serial.Serial(serial_port, Config.BAUD_RATE, timeout=Config.TIMEOUT)
            self.power_supply = PowerSupply(self.serial_obj, 1)  # Assuming address 1 for the power supply

    def browse_storage_path(self):
        """Browse for the folder where data will be saved."""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder_selected)

    def add_stage(self):
        """Add a new stage to the experiment."""
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())
            stage = {"voltage_start": voltage_start, "voltage_end": voltage_end, "time": time_duration}
            self.stages.append(stage)
            messagebox.showinfo("Stage Added", f"Stage added: {stage}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid values for voltage and time.")

    def collect_data_for_stage(self, stage, sample_interval):
        """Collect data for a given stage (to be implemented based on your data collection logic)."""
        # Placeholder for your data collection logic
        voltage = self.power_supply.V()
        current = self.power_supply.A()
        timestamp = time.time()
        self.data_queue.put((timestamp, voltage, current))

    def collect_data(self, sample_rate):
        """Collect data for the experiment stages."""
        sample_interval = 1.0 / sample_rate  # Calculate time interval for each sample

        for stage in self.stages:
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            # Calculate voltage increment per sample
            voltage_increment = (voltage_end - voltage_start) * sample_interval / duration

            # Start with initial voltage and gradually change it
            current_voltage = voltage_start
            start_time = time.time()

            # Loop through the time duration of the stage
            while time.time() - start_time < duration:
                self.power_supply.V(current_voltage)  # Set the power supply voltage
                self.collect_data_for_stage(stage, sample_interval)

                # Update the voltage for the next sample
                current_voltage += voltage_increment

                # Ensure the voltage stays within the bounds of start and end voltages
                if current_voltage > voltage_end:
                    current_voltage = voltage_end
                elif current_voltage < voltage_start:
                    current_voltage = voltage_start

                time.sleep(sample_interval)  # Wait for the next sample

            self.stage_done_event.wait()
            self.stage_done_event.clear()

        self.experiment_done_event.set()

    def save_data(self):
        """Save collected data to a CSV file."""
        file_path = os.path.join(self.entry_storage_path.get(), f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Voltage", "Current"])
            while not self.data_queue.empty():
                writer.writerow(self.data_queue.get())
        messagebox.showinfo("Data Saved", f"Data saved to {file_path}")

    def start_experiment(self):
        """Start the experiment in a separate thread."""
        if not self.stages:
            messagebox.showerror("No Stages", "Please add at least one stage.")
            return

        if not self.serial_obj or not self.power_supply:
            messagebox.showerror("No Serial Port", "Please select a serial port.")
            return

        if self.is_experiment_running:
            messagebox.showwarning("Experiment Running", "An experiment is already running.")
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        sample_rate = int(self.entry_sample_rate.get()) if self.entry_sample_rate.get() else Config.DEFAULT_SAMPLE_RATE

        # Start data collection thread
        threading.Thread(target=self.collect_data, args=(sample_rate,)).start()

        # Wait for the experiment to finish
        self.experiment_done_event.wait()

        # Save the collected data to CSV
        self.save_data()

        self.is_experiment_running = False
        messagebox.showinfo("Experiment Complete", "Experiment finished and data saved.")


# Start the Tkinter window and GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
