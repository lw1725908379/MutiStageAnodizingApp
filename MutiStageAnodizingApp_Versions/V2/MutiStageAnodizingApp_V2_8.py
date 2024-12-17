import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import time
import threading
import serial.tools.list_ports
import os
import csv
from datetime import datetime
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class Config:
    # -------------------------
    # Serial Communication Settings
    # -------------------------
    BAUD_RATE = 9600          # Baud rate for serial communication
    TIMEOUT = 1               # Timeout for serial communication in seconds

    # -------------------------
    # Power Supply Register Addresses
    # -------------------------
    REG_VOLTAGE = 0x0010      # Register for voltage reading
    REG_CURRENT = 0x0011      # Register for current reading
    REG_VOLTAGE_SET = 0x0030  # Register for setting voltage
    REG_CURRENT_SET = 0x0031  # Register for setting current

    REG_NAME = 0x0003         # Register for power supply name
    REG_CLASS_NAME = 0x0004   # Register for power supply class name
    REG_DOT = 0x0005          # Register for scaling factor (dot)
    REG_PROTECTION_STATE = 0x0002  # Register for protection state (overvoltage, overcurrent, etc.)
    REG_ADDR = 0x9999         # Register for reading the device address
    REG_OPERATIVE_MODE = 0x0001   # Register for reading or setting the operative mode
    REG_DISPLAYED_POWER = 0x0012  # Register for reading the displayed power (W)

    # -------------------------
    # Power Protection State Flags
    # -------------------------
    OVP = 0x01                # Overvoltage protection flag
    OCP = 0x02                # Overcurrent protection flag
    OPP = 0x04                # Overpower protection flag
    OTP = 0x08                # Overtemperature protection flag
    SCP = 0x10                # Short-circuit protection flag

    # -------------------------
    # Protection Setting Registers
    # -------------------------
    REG_OVP = 0x0020          # Register for overvoltage protection setting
    REG_OCP = 0x0021          # Register for overcurrent protection setting
    REG_OPP = 0x0022          # Register for overpower protection setting

    # -------------------------
    # Slave Address Registers
    # -------------------------
    REG_ADDR_SLAVE = 0x9999   # Register for setting or reading the slave address

    # -------------------------
    # Default Settings
    # -------------------------
    TIMEOUT_READ = 1.0        # Default read timeout in seconds
    DEFAULT_SAMPLE_RATE = 10  # Default sampling rate in Hz (10 Hz)
class PowerSupply:
    """
    Power Supply class, using pymodbus library for Modbus RTU communication
    """

    def __init__(self, port: str, addr: int, retries: int = 5, delay: float = 1.0):
        self.client = ModbusSerialClient(method='rtu', port=port, baudrate=Config.BAUD_RATE, timeout=Config.TIMEOUT)
        for attempt in range(retries):
            connection = self.client.connect()
            if connection:
                logging.info(f"Successfully connected to Modbus client on port: {port}")
                break
            else:
                logging.warning(f"Unable to connect to Modbus client on port: {port}, retrying {attempt + 1}/{retries}...")
                time.sleep(delay)
        else:
            logging.error(f"Unable to connect to Modbus client on port: {port}, all retries failed")
            raise Exception("Modbus client connection failed")

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

        logging.debug(f"Scaling factors - W_dot: {self.W_dot}, A_dot: {self.A_dot}, V_dot: {self.V_dot}")
        logging.debug(f"Protection states - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")

        self.set_volt(0)

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
            logging.exception(f"Modbus exception when reading register {reg_addr}: {e}")
            return 0
        except Exception as e:
            logging.exception(f"Exception when reading register {reg_addr}: {e}")
            return 0

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        try:
            if data_len <= 1:
                response = self.client.write_register(reg_addr, data, unit=self.addr)
                if response.isError():
                    logging.error(f"Error writing register {reg_addr}: {response}")
                    return False
                read_back = self.read(reg_addr)
                logging.debug(f"Wrote value {data} to register {reg_addr}, read back: {read_back}")
                return read_back == data
            else:
                high = data >> 16
                low = data & 0xFFFF
                response1 = self.client.write_register(reg_addr, high, unit=self.addr)
                response2 = self.client.write_register(reg_addr + 1, low, unit=self.addr)
                if response1.isError() or response2.isError():
                    logging.error(f"Error writing registers {reg_addr} and {reg_addr + 1}: {response1}, {response2}")
                    return False
                read_back1 = self.read(reg_addr)
                read_back2 = self.read(reg_addr + 1)
                logging.debug(f"Wrote value {high} to register {reg_addr}, read back: {read_back1}")
                logging.debug(f"Wrote value {low} to register {reg_addr + 1}, read back: {read_back2}")
                return read_back1 == high and read_back2 == low
        except ModbusException as e:
            logging.exception(f"Modbus exception when writing register {reg_addr}: {e}")
            return False
        except Exception as e:
            logging.exception(f"Exception when writing register {reg_addr}: {e}")
            return False

    def read_protection_state(self):
        protection_state_int = self.read(Config.REG_PROTECTION_STATE)
        self.isOVP = protection_state_int & Config.OVP
        self.isOCP = (protection_state_int & Config.OCP) >> 1
        self.isOPP = (protection_state_int & Config.OPP) >> 2
        self.isOTP = (protection_state_int & Config.OTP) >> 3
        self.isSCP = (protection_state_int & Config.SCP) >> 4
        logging.debug(f"Updated protection state - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")
        return protection_state_int

    def V(self, V_input: float = None):
        if V_input is None:
            voltage = self.read(Config.REG_VOLTAGE)
            actual_voltage = voltage / self.V_dot
            logging.debug(f"Read voltage: {voltage} raw value, {actual_voltage} V")
            return actual_voltage
        else:
            logging.debug(f"Setting voltage to {V_input} V")
            success = self.write(Config.REG_VOLTAGE_SET, int(V_input * self.V_dot + 0.5))
            if success:
                actual_voltage = self.read(Config.REG_VOLTAGE) / self.V_dot
                logging.debug(f"Voltage set successfully, actual voltage: {actual_voltage} V")
                return actual_voltage
            else:
                logging.error("Voltage setting failed")
                return None

    def A(self, A_input: float = None):
        if A_input is None:
            current = self.read(Config.REG_CURRENT)
            actual_current = current / self.A_dot
            logging.debug(f"Read current: {current} raw value, {actual_current} A")
            return actual_current
        else:
            logging.debug(f"Setting current to {A_input} A")
            success = self.write(Config.REG_CURRENT_SET, int(A_input * self.A_dot + 0.5))
            if success:
                current_set = self.read(Config.REG_CURRENT_SET)
                actual_current = current_set / self.A_dot
                logging.debug(f"Current set successfully, actual current: {actual_current} A")
                return actual_current
            else:
                logging.error("Current setting failed")
                return None

    def W(self):
        """
        Read the displayed power
        :return: Displayed power in watts
        """
        return self.read(Config.REG_DISPLAYED_POWER, 2) / self.W_dot

    def OVP(self, OVP_input: float = None):
        """
        Read or write the overvoltage protection setting
        :param OVP_input: Overvoltage protection setting
        :return: Overvoltage protection setting
        """
        if OVP_input is None:
            return self.read(Config.REG_OVP) / self.V_dot
        else:
            self.write(Config.REG_OVP, int(OVP_input * self.V_dot + 0.5))
            return self.read(Config.REG_OVP) / self.V_dot

    def OCP(self, OAP_input: float = None):
        """
        Read or write the overcurrent protection setting
        :param OAP_input: Overcurrent protection setting
        :return: Overcurrent protection setting
        """
        if OAP_input is None:
            return self.read(Config.REG_OCP) / self.A_dot
        else:
            self.write(Config.REG_OCP, int(OAP_input * self.A_dot + 0.5))
            return self.read(Config.REG_OCP) / self.A_dot

    def OPP(self, OPP_input: float = None):
        """
        Read or write the overpower protection setting
        :param OPP_input: Overpower protection setting
        :return: Overpower protection setting
        """
        if OPP_input is None:
            return self.read(Config.REG_OPP, 2) / self.W_dot
        else:
            self.write(Config.REG_OPP, int(OPP_input * self.W_dot + 0.5), 2)
            return self.read(Config.REG_OPP, 2) / self.W_dot

    def Addr(self, addr_input: int = None):
        """
        Read or change the slave address
        :param addr_input: The slave address to set, range 1 to 250
        :return: The slave address
        """
        if addr_input is None:
            self.addr = self.read(Config.REG_ADDR_SLAVE)
            return self.addr
        else:
            self.write(Config.REG_ADDR_SLAVE, addr_input)
            self.addr = addr_input
            return self.read(Config.REG_ADDR_SLAVE)

    def set_volt(self, V_input, error_range: float = 0.4, timeout: int = 600):
        old_volt = self.V()
        logging.info(f"Setting target voltage from {old_volt} V to {V_input} V")
        self.V(V_input)
        start_time = time.time()
        while True:
            current_volt = self.V()  # Read actual voltage
            if abs(current_volt - V_input) <= error_range:
                break
            if (time.time() - start_time) > timeout:
                raise ValueError("Voltage setting timed out")
            time.sleep(0.1)
        elapsed_time = time.time() - start_time
        logging.info(f"Voltage set to {current_volt} V, took {elapsed_time:.2f} seconds")

    def operative_mode(self, mode_input: int = None):
        """
        Read or write the  operational mode
        :param mode_input:  operational mode, 1: Enable output; 0: Disable output
        :return: Current operational status
        """
        if mode_input is None:
            return self.read(Config.REG_OPERATIVE_MODE)
        else:
            self.write(Config.REG_OPERATIVE_MODE, mode_input)
            return self.read(Config.REG_OPERATIVE_MODE)

class PlotWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("Real-time Data Plot")

        # Create Matplotlib figure
        self.fig, (self.ax_voltage, self.ax_current, self.ax_power) = plt.subplots(3, 1, figsize=(8, 6))
        self.fig.tight_layout(pad=3.0)

        self.voltage_line, = self.ax_voltage.plot([], [], label='Voltage (V)', color='blue')
        self.current_line, = self.ax_current.plot([], [], label='Current (A)', color='green')
        self.power_line, = self.ax_power.plot([], [], label='Power (W)', color='red')

        self.ax_voltage.set_title('Voltage vs Time')
        self.ax_voltage.set_xlabel('Time (s)')
        self.ax_voltage.set_ylabel('Voltage (V)')
        self.ax_voltage.legend()
        self.ax_voltage.grid(True)

        self.ax_current.set_title('Current vs Time')
        self.ax_current.set_xlabel('Time (s)')
        self.ax_current.set_ylabel('Current (A)')
        self.ax_current.legend()
        self.ax_current.grid(True)

        self.ax_power.set_title('Power vs Time')
        self.ax_power.set_xlabel('Time (s)')
        self.ax_power.set_ylabel('Power (W)')
        self.ax_power.legend()
        self.ax_power.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Data storage
        self.start_time = None  # Record the timestamp when the first data is received
        self.times = []
        self.voltages = []
        self.currents = []
        self.powers = []
        self.lock = threading.Lock()

    def update_plot(self, timestamp, voltage, current):
        with self.lock:
            # Normalize the timestamp to start from 0
            if self.start_time is None:
                self.start_time = timestamp  # Record the start time
            normalized_time = timestamp - self.start_time

            self.times.append(normalized_time)
            self.voltages.append(voltage)
            self.currents.append(current)
            self.powers.append(voltage * current)

            # Limit the number of plot points to keep the plot smooth
            MAX_DATA_POINTS = 1000
            if len(self.times) > MAX_DATA_POINTS:
                self.times = self.times[-MAX_DATA_POINTS:]
                self.voltages = self.voltages[-MAX_DATA_POINTS:]
                self.currents = self.currents[-MAX_DATA_POINTS:]
                self.powers = self.powers[-MAX_DATA_POINTS:]

            # Update plot data
            self.voltage_line.set_data(self.times, self.voltages)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()

            self.current_line.set_data(self.times, self.currents)
            self.ax_current.relim()
            self.ax_current.autoscale_view()

            self.power_line.set_data(self.times, self.powers)
            self.ax_power.relim()
            self.ax_power.autoscale_view()

            # Refresh the plot
            self.canvas.draw()

    def start_animation(self, plot_queue, stop_event):
        """ Start the plot update thread """
        def animate():
            while not stop_event.is_set():
                try:
                    timestamp, voltage, current = plot_queue.get(timeout=0.1)
                    self.update_plot(timestamp, voltage, current)
                except queue.Empty:
                    continue
        threading.Thread(target=animate, daemon=True).start()
class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Experiment Control Panel")

        self.power_supply = None
        self.is_experiment_running = False
        self.stages = []

        self.plot_queue = queue.Queue()
        self.storage_queue = queue.Queue()

        self.experiment_done_event = threading.Event()
        self.plot_window = None
        self.plot_stop_event = threading.Event()

        self.storage_thread = None
        self.storage_stop_event = threading.Event()
        self.storage_file = None
        self.storage_writer = None
        self.storage_lock = threading.Lock()

        self.label_serial = tk.Label(root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        self.serial_ports = self.get_serial_ports()
        self.combo_serial = ttk.Combobox(root, values=self.serial_ports, state="readonly")
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)

        self.label_voltage_start = tk.Label(root, text="Initial Voltage (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')

        self.entry_voltage_start = tk.Entry(root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        self.label_voltage_end = tk.Label(root, text="Termination Voltage (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')

        self.entry_voltage_end = tk.Entry(root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        self.label_time = tk.Label(root, text="Set Time (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5, sticky='e')

        self.entry_time = tk.Entry(root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.label_sample_rate = tk.Label(root, text="Sampling Rate (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5, sticky='e')

        self.entry_sample_rate = tk.Entry(root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))

        self.label_storage_path = tk.Label(root, text="Storage Path:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5, sticky='e')

        self.entry_storage_path = tk.Entry(root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5, sticky='w')

        self.button_browse = tk.Button(root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5, sticky='w')

        self.frame_buttons = tk.Frame(root)
        self.frame_buttons.grid(row=6, column=0, columnspan=3, padx=5, pady=5)

        self.button_add_stage = tk.Button(self.frame_buttons, text="Add Stage", command=self.add_stage, width=15)
        self.button_add_stage.pack(side='left', padx=5)

        self.button_delete_stage = tk.Button(self.frame_buttons, text="Delete Selected Stage", command=self.delete_stage, width=20)
        self.button_delete_stage.pack(side='left', padx=5)

        self.button_start = tk.Button(self.frame_buttons, text="Start Experiment", command=self.start_experiment, width=15)
        self.button_start.pack(side='left', padx=5)

        self.frame_stages = tk.Frame(root)
        self.frame_stages.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        root.grid_rowconfigure(7, weight=1)
        root.grid_columnconfigure(1, weight=1)

        self.tree_stages = ttk.Treeview(self.frame_stages, columns=("Stage No.", "Initial Voltage (V)", "Termination Voltage (V)", "Duration (s)"), show='headings', selectmode='extended')
        self.tree_stages.heading("Stage No.", text="Stage No.")
        self.tree_stages.heading("Initial Voltage (V)", text="Initial Voltage (V)")
        self.tree_stages.heading("Termination Voltage (V)", text="Termination Voltage (V)")
        self.tree_stages.heading("Duration (s)", text="Duration (s)")

        self.tree_stages.column("Stage No.", width=80, anchor='center')
        self.tree_stages.column("Initial Voltage (V)", width=150, anchor='center')
        self.tree_stages.column("Termination Voltage (V)", width=170, anchor='center')
        self.tree_stages.column("Duration (s)", width=100, anchor='center')

        self.scrollbar_stages = ttk.Scrollbar(self.frame_stages, orient="vertical", command=self.tree_stages.yview)
        self.tree_stages.configure(yscroll=self.scrollbar_stages.set)
        self.scrollbar_stages.pack(side='right', fill='y')
        self.tree_stages.pack(fill='both', expand=True)

    def get_serial_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        logging.debug(f"Available serial ports: {ports}")
        return ports

    def set_serial_port(self, event):
        serial_port = self.combo_serial.get()
        if serial_port:
            try:
                self.power_supply = PowerSupply(serial_port, 1)
                messagebox.showinfo("Serial Port", f"Connected to {serial_port}")
                logging.info(f"Successfully connected to serial port: {serial_port}")
            except Exception as e:
                messagebox.showerror("Serial Port Error", f"Failed to connect to {serial_port}\n{e}")
                logging.error(f"Failed to connect to serial port {serial_port}: {e}")
                self.power_supply = None

    def browse_storage_path(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder_selected)
            logging.info(f"Selected data storage path: {folder_selected}")

    def add_stage(self):
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())
            stage = {"voltage_start": voltage_start, "voltage_end": voltage_end, "time": time_duration}
            self.stages.append(stage)

            stage_no = len(self.stages)
            self.tree_stages.insert('', 'end', values=(stage_no, voltage_start, voltage_end, time_duration))

            messagebox.showinfo("Stage Added", f"Stage added: {stage}")
            logging.info(f"Added experiment stage: {stage}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid values for voltage and time.")
            logging.error("Invalid input when adding experiment stage")

    def delete_stage(self):
        selected_items = self.tree_stages.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select a stage to delete.")
            logging.warning("Tried to delete experiment stage but no items were selected")
            return

        confirm = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected stage?")
        if not confirm:
            return

        indices = []
        for item in selected_items:
            values = self.tree_stages.item(item, 'values')
            stage_no = int(values[0]) - 1
            indices.append(stage_no)

        indices.sort(reverse=True)

        for index in indices:
            if 0 <= index < len(self.stages):
                del self.stages[index]

        for item in selected_items:
            self.tree_stages.delete(item)

        for idx, item in enumerate(self.tree_stages.get_children(), start=1):
            self.tree_stages.item(item, values=(idx, self.stages[idx-1]["voltage_start"],
                                               self.stages[idx-1]["voltage_end"],
                                               self.stages[idx-1]["time"]))

        messagebox.showinfo("Stage Deleted", "The selected stage has been deleted.")
        logging.info(f"Deleted experiment stage: {selected_items}")

    def initialize_storage(self):
        storage_path = self.entry_storage_path.get()
        if not storage_path:
            messagebox.showerror("Storage Path Error", "Please specify the data storage path.")
            logging.error("Data storage path not specified")
            return False

        file_path = os.path.join(storage_path, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            self.storage_file = open(file_path, mode='w', newline='')
            self.storage_writer = csv.writer(self.storage_file)
            self.storage_writer.writerow(["Timestamp", "Voltage (V)", "Current (A)", "Power (W)"])
            logging.info(f"Initialized data storage file: {file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Storage Initialization Error", f"Failed to create CSV file.\n{e}")
            logging.exception(f"Error initializing data storage file: {e}")
            return False

    def storage_consumer(self):
        while not self.storage_stop_event.is_set():
            try:
                timestamp, voltage, current = self.storage_queue.get(timeout=0.05)
                power = voltage * current
                with self.storage_lock:
                    self.storage_writer.writerow([timestamp, voltage, current, power])
                    self.storage_file.flush()
                logging.debug(f"Stored data: {timestamp}, {voltage}, {current}, {power}")
            except queue.Empty:
                continue
            except Exception as e:
                messagebox.showerror("Storage Error", f"Error storing data.\n{e}")
                logging.exception(f"Error storing data: {e}")
                break

    def collect_data_for_stage(self, stage, sample_interval):
        try:
            voltage = self.power_supply.V()
            if voltage is None:
                logging.error("Failed to read voltage, skipping this sample")
                return
            current = self.power_supply.A()
            if current is None:
                logging.error("Failed to read current, skipping this sample")
                return
            timestamp = time.time()
            self.plot_queue.put((timestamp, voltage, current))
            self.storage_queue.put((timestamp, voltage, current))
            logging.debug(f"Collected data: {timestamp}, {voltage}, {current}")
        except Exception as e:
            logging.exception(f"Error collecting data for stage: {e}")

    def run_voltage_ramp(self, sample_rate):
        """
        Perform a linear voltage ramp, collect voltage and current data, and store to file and plot queue.
        :param sample_rate: Sampling frequency (Hz)
        """
        sample_interval = 1.0 / sample_rate  # Time interval between each sample
        logging.info(f"Starting voltage ramp with sampling frequency: {sample_rate} Hz")

        for stage in self.stages:
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            # Calculate voltage increment for each step
            steps = int(duration / sample_interval)
            voltage_increment = (voltage_end - voltage_start) / steps
            current_voltage = voltage_start

            # Initialize start time
            start_time = time.time()
            logging.info(f"Stage start - Initial voltage: {voltage_start} V, Target voltage: {voltage_end} V, Duration: {duration} s")

            for step in range(steps):
                step_start_time = time.time()  # Start time for each loop iteration

                # Update voltage
                current_voltage += voltage_increment
                current_voltage = min(current_voltage, voltage_end) if voltage_increment > 0 else max(current_voltage, voltage_end)
                self.power_supply.set_volt(current_voltage)

                # Collect data
                self.collect_data_for_stage(stage, sample_interval)

                # Adjust wait time dynamically to ensure accurate sampling intervals
                elapsed_time = time.time() - step_start_time
                sleep_time = max(0, sample_interval - elapsed_time)
                time.sleep(sleep_time)

                # Check protection state
                protection_state = self.power_supply.read_protection_state()
                if protection_state != 0:
                    logging.error(f"Protection triggered: {protection_state}")
                    messagebox.showerror("Protection Triggered", f"Protection triggered: {protection_state}")
                    self.is_experiment_running = False
                    return

            logging.info(f"Stage complete - Target voltage: {voltage_end} V")

        self.experiment_done_event.set()
        logging.info("All stages of voltage ramp completed")

    def collect_data(self, sample_rate):
        sample_interval = 1.0 / sample_rate
        logging.info(f"Starting data collection with sampling frequency: {sample_rate} Hz")

        for stage in self.stages:
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            if duration == 0:
                voltage_increment = 0
            else:
                voltage_increment = (voltage_end - voltage_start) * sample_interval / duration

            logging.debug(f"Stage start - Initial voltage: {voltage_start} V, Termination voltage: {voltage_end} V, Duration: {duration} s, Voltage increment: {voltage_increment} V")

            current_voltage = voltage_start
            start_time = time.time()

            # Set initial voltage
            self.power_supply.set_volt(current_voltage)

            # Loop through the stage duration
            while time.time() - start_time < duration:
                # 1. Update voltage (calculate and set new voltage)
                current_voltage += voltage_increment
                # Ensure voltage stays between start and end values
                if voltage_increment > 0 and current_voltage > voltage_end:
                    current_voltage = voltage_end
                elif voltage_increment < 0 and current_voltage < voltage_end:
                    current_voltage = voltage_end

                self.power_supply.set_volt(current_voltage)

                # Give the device some time to reach the set voltage (assuming half of the sampling interval)
                time.sleep(sample_interval * 0.5)

                # 2. Collect data
                self.collect_data_for_stage(stage, sample_interval)

                # Check protection state
                protection_state = self.power_supply.read_protection_state()
                if protection_state != 0:
                    logging.error(f"Protection triggered: {protection_state}")
                    messagebox.showerror("Protection Triggered", f"Protection triggered: {protection_state}")
                    self.is_experiment_running = False
                    return

                # Wait for the remaining half of the sampling interval
                time.sleep(sample_interval * 0.5)

        self.experiment_done_event.set()
        logging.info("Data collection complete")

    def start_experiment(self):
        if not self.stages:
            messagebox.showerror("No Stages", "Please add at least one experiment stage.")
            logging.error("Attempted to start experiment but no stages were added")
            return

        if not self.power_supply:
            messagebox.showerror("No Serial Port", "Please select a serial port first.")
            logging.error("Attempted to start experiment but no serial port was selected")
            return

        if self.is_experiment_running:
            messagebox.showwarning("Experiment Running", "An experiment is already running.")
            logging.warning("Attempted to start experiment but one is already running")
            return

        if not self.initialize_storage():
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        try:
            sample_rate = int(self.entry_sample_rate.get()) if self.entry_sample_rate.get() else Config.DEFAULT_SAMPLE_RATE
        except ValueError:
            messagebox.showerror("Invalid Sample Rate", "Sampling rate must be an integer.")
            logging.error("Invalid sample rate input")
            self.is_experiment_running = False
            return

        if self.power_supply:
            try:
                self.power_supply.operative_mode(1)  # Setting the operative mode to 1 (to enable output)
                logging.info("Operative mode set to 1 (output enabled).")
            except Exception as e:
                messagebox.showerror("Operative Mode Error", f"Failed to set operative mode: {e}")
                logging.error(f"Failed to set operative mode: {e}")
                self.is_experiment_running = False
                return

        # Start plot window
        plot_root = tk.Toplevel(self.root)
        self.plot_window = PlotWindow(plot_root)
        self.plot_window.start_animation(self.plot_queue, self.plot_stop_event)
        logging.info("Plot window started")

        # Start storage thread
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()
        logging.info("Storage consumer thread started")

        # Start data collection thread
        data_thread = threading.Thread(target=self.run_voltage_ramp, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("Data collection thread started")

        # Monitor experiment completion
        monitor_thread = threading.Thread(target=self.monitor_experiment, daemon=True)
        monitor_thread.start()
        logging.info("Experiment monitoring thread started")

    def monitor_experiment(self):
        self.experiment_done_event.wait()
        logging.info("Received experiment complete signal")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("Storage consumer thread ended")

        if self.storage_file is not None:
            self.storage_file.close()
            logging.info("Storage file closed")

        if self.power_supply and self.power_supply.client:
            self.power_supply.client.close()
            logging.info("Modbus client connection closed")

        self.is_experiment_running = False
        messagebox.showinfo("Experiment Complete", "Experiment complete, data saved.")
        logging.info("Displayed experiment complete message")

if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
