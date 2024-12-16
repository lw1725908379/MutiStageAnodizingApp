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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
import random

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

class MockPowerSupply:
    """
    Mock Power Supply for Testing
    """
    def __init__(self, addr: int):
        self.addr = addr
        self.current_voltage_set = 0.0
        self.current_current_set = 0.0
        self.V_dot = 1.0  # Scaling factors can be adjusted as needed
        self.A_dot = 1.0
        self.V_actual = 0.0
        self.A_actual = 0.0

    def read(self, reg_addr: int, reg_len: int = 1):
        # Simulate reading registers by returning predefined values
        if reg_addr == Config.REG_VOLTAGE:
            return int(self.V_actual * self.V_dot)
        elif reg_addr == Config.REG_CURRENT:
            return int(self.A_actual * self.A_dot)
        elif reg_addr == Config.REG_VOLTAGE_SET:
            return int(self.current_voltage_set * self.V_dot)
        elif reg_addr == Config.REG_CURRENT_SET:
            return int(self.current_current_set * self.A_dot)
        else:
            return 0

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        # Simulate writing to registers by setting internal variables
        if reg_addr == Config.REG_VOLTAGE_SET:
            self.current_voltage_set = data / self.V_dot
            return True
        elif reg_addr == Config.REG_CURRENT_SET:
            self.current_current_set = data / self.A_dot
            return True
        return False

    def V(self, V_input: float = None):
        if V_input is None:
            return self.V_actual
        else:
            self.current_voltage_set = V_input
            return self.current_voltage_set

    def A(self, A_input: float = None):
        if A_input is None:
            return self.A_actual
        else:
            self.current_current_set = A_input
            return self.current_current_set

    def simulate(self, sample_interval):
        """
        Simulate voltage and current changes over time.
        This method should be run in a separate thread.
        """
        while True:
            # For simulation, let's make actual voltage approach the set voltage
            delta_v = (self.current_voltage_set - self.V_actual) * 0.1
            self.V_actual += delta_v

            # Similarly for current
            delta_a = (self.current_current_set - self.A_actual) * 0.1
            self.A_actual += delta_a

            # Introduce some randomness
            self.V_actual += random.uniform(-0.05, 0.05)
            self.A_actual += random.uniform(-0.02, 0.02)

            # Ensure values are within reasonable bounds
            self.V_actual = max(0.0, min(self.V_actual, 100.0))  # Example: 0V to 100V
            self.A_actual = max(0.0, min(self.A_actual, 10.0))   # Example: 0A to 10A

            time.sleep(sample_interval)

class PlotWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("实时数据绘图")

        # 创建Matplotlib图形
        self.fig, (self.ax_voltage, self.ax_current, self.ax_power) = plt.subplots(3, 1, figsize=(8, 6))
        self.fig.tight_layout(pad=3.0)

        # 创建图表对象
        self.voltage_line, = self.ax_voltage.plot([], [], label='Voltage (V)', color='blue')
        self.current_line, = self.ax_current.plot([], [], label='Current (A)', color='green')
        self.power_line, = self.ax_power.plot([], [], label='Power (W)', color='red')

        # 设置图表属性
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

        # 创建Canvas并嵌入到Tkinter窗口
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 数据存储
        self.times = []
        self.voltages = []
        self.currents = []
        self.powers = []

        # 锁定机制
        self.lock = threading.Lock()

    def update_plot(self, timestamp, voltage, current):
        with self.lock:
            self.times.append(timestamp)
            self.voltages.append(voltage)
            self.currents.append(current)
            self.powers.append(voltage * current)

            # 更新电压图
            self.voltage_line.set_data(self.times, self.voltages)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()

            # 更新电流图
            self.current_line.set_data(self.times, self.currents)
            self.ax_current.relim()
            self.ax_current.autoscale_view()

            # 更新功率图
            self.power_line.set_data(self.times, self.powers)
            self.ax_power.relim()
            self.ax_power.autoscale_view()

            self.canvas.draw()

    def start_animation(self, plot_queue, stop_event):
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

        # Initialize serial connection objects
        self.serial_obj = None  # Placeholder for serial object
        self.power_supply = None  # Placeholder for power supply object
        self.is_experiment_running = False  # Flag to prevent multiple experiments

        # List to store experiment stages
        self.stages = []

        # Queues for storing experimental data
        self.plot_queue = queue.Queue()
        self.storage_queue = queue.Queue()

        # Event to signal the experiment has finished
        self.experiment_done_event = threading.Event()

        # Plotting related
        self.plot_window = None
        self.plot_stop_event = threading.Event()

        # Storage related
        self.storage_thread = None
        self.storage_stop_event = threading.Event()
        self.storage_file = None
        self.storage_writer = None
        self.storage_lock = threading.Lock()

        # Serial port selection UI
        self.label_serial = tk.Label(root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        self.serial_ports = self.get_serial_ports()  # Retrieve list of available serial ports
        self.combo_serial = ttk.Combobox(root, values=self.serial_ports, state="readonly")
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)  # Bind event for port selection

        # Virtual Power Supply Checkbox
        self.use_virtual_var = tk.BooleanVar()
        self.checkbox_virtual = tk.Checkbutton(root, text="Use Virtual Power Supply", variable=self.use_virtual_var, command=self.toggle_virtual_mode)
        self.checkbox_virtual.grid(row=0, column=2, padx=5, pady=5, sticky='w')

        # Voltage input fields for start and end values
        self.label_voltage_start = tk.Label(root, text="Initial Voltage (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')

        self.entry_voltage_start = tk.Entry(root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        self.label_voltage_end = tk.Label(root, text="Termination Voltage (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')

        self.entry_voltage_end = tk.Entry(root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        # Time duration input field
        self.label_time = tk.Label(root, text="Set Time (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5, sticky='e')

        self.entry_time = tk.Entry(root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        # Sampling frequency input field
        self.label_sample_rate = tk.Label(root, text="Sampling Rate (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5, sticky='e')

        self.entry_sample_rate = tk.Entry(root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))  # Default value: 10 Hz

        # Path selection for data storage
        self.label_storage_path = tk.Label(root, text="Storage Path:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5, sticky='e')

        self.entry_storage_path = tk.Entry(root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5, sticky='w')

        self.button_browse = tk.Button(root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5, sticky='w')

        # Frame for buttons (Add Stage, Delete Selected Stage, Start Experiment)
        self.frame_buttons = tk.Frame(root)
        self.frame_buttons.grid(row=6, column=0, columnspan=3, padx=5, pady=5)

        # Button to add a new experiment stage
        self.button_add_stage = tk.Button(self.frame_buttons, text="Add Stage", command=self.add_stage, width=15)
        self.button_add_stage.pack(side='left', padx=5)

        # Button to delete selected experiment stage
        self.button_delete_stage = tk.Button(self.frame_buttons, text="Delete Selected Stage", command=self.delete_stage, width=20)
        self.button_delete_stage.pack(side='left', padx=5)

        # Button to initiate the experiment
        self.button_start = tk.Button(self.frame_buttons, text="Start Experiment", command=self.start_experiment, width=15)
        self.button_start.pack(side='left', padx=5)

        # Frame for experiment stages list
        self.frame_stages = tk.Frame(root)
        self.frame_stages.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')

        # Configure grid weights for resizing
        root.grid_rowconfigure(7, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # Initialize Treeview for displaying experiment stages
        self.tree_stages = ttk.Treeview(self.frame_stages, columns=("Stage No.", "Initial Voltage (V)", "Termination Voltage (V)", "Duration (s)"), show='headings', selectmode='extended')
        self.tree_stages.heading("Stage No.", text="Stage No.")
        self.tree_stages.heading("Initial Voltage (V)", text="Initial Voltage (V)")
        self.tree_stages.heading("Termination Voltage (V)", text="Termination Voltage (V)")
        self.tree_stages.heading("Duration (s)", text="Duration (s)")

        # Define column widths
        self.tree_stages.column("Stage No.", width=80, anchor='center')
        self.tree_stages.column("Initial Voltage (V)", width=150, anchor='center')
        self.tree_stages.column("Termination Voltage (V)", width=170, anchor='center')
        self.tree_stages.column("Duration (s)", width=100, anchor='center')

        # Add vertical scrollbar
        self.scrollbar_stages = ttk.Scrollbar(self.frame_stages, orient="vertical", command=self.tree_stages.yview)
        self.tree_stages.configure(yscroll=self.scrollbar_stages.set)
        self.scrollbar_stages.pack(side='right', fill='y')

        # Pack the Treeview
        self.tree_stages.pack(fill='both', expand=True)

        # Initialize mock simulation thread
        self.mock_thread = None
        self.mock_stop_event = threading.Event()

    def toggle_virtual_mode(self):
        """Enable or disable serial port selection based on virtual mode."""
        if self.use_virtual_var.get():
            self.combo_serial.configure(state='disabled')
            # Initialize MockPowerSupply
            self.power_supply = MockPowerSupply(addr=1)
            # Start the simulation thread
            self.mock_stop_event.clear()
            self.mock_thread = threading.Thread(target=self.power_supply.simulate, args=(0.5,), daemon=True)
            self.mock_thread.start()
            messagebox.showinfo("Virtual Power Supply", "已启用虚拟电源。")
        else:
            self.combo_serial.configure(state='readonly')
            # Stop the simulation thread
            if self.mock_thread and self.mock_thread.is_alive():
                self.mock_stop_event.set()
                self.mock_thread.join()
            self.power_supply = None
            messagebox.showinfo("Virtual Power Supply", "已禁用虚拟电源。")

    def get_serial_ports(self):
        """Get a list of available serial ports."""
        return [port.device for port in serial.tools.list_ports.comports()]

    def set_serial_port(self, event):
        """Set the selected serial port."""
        if self.use_virtual_var.get():
            # If virtual mode is enabled, ignore serial port selection
            return

        serial_port = self.combo_serial.get()
        if serial_port:
            try:
                self.serial_obj = serial.Serial(serial_port, Config.BAUD_RATE, timeout=Config.TIMEOUT)
                self.power_supply = PowerSupply(self.serial_obj, 1)  # Assuming address 1 for the power supply
                messagebox.showinfo("Serial Port", f"Connected to {serial_port}")
            except serial.SerialException as e:
                messagebox.showerror("Serial Port Error", f"Failed to connect to {serial_port}\n{e}")
                self.serial_obj = None
                self.power_supply = None

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

            # Insert stage into Treeview
            stage_no = len(self.stages)
            self.tree_stages.insert('', 'end', values=(stage_no, voltage_start, voltage_end, time_duration))

            messagebox.showinfo("Stage Added", f"Stage added: {stage}")
        except ValueError:
            messagebox.showerror("Invalid Input", "请为电压和时间输入有效的数值。")

    def delete_stage(self):
        """Delete selected stages from the experiment."""
        selected_items = self.tree_stages.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "请先选择要删除的实验阶段。")
            return

        confirm = messagebox.askyesno("Confirm Deletion", "确定要删除选中的实验阶段吗？")
        if not confirm:
            return

        # Get indices of selected items
        indices = []
        for item in selected_items:
            values = self.tree_stages.item(item, 'values')
            stage_no = int(values[0]) - 1  # Zero-based index
            indices.append(stage_no)

        # Sort indices in descending order to delete from the end
        indices.sort(reverse=True)

        for index in indices:
            if 0 <= index < len(self.stages):
                del self.stages[index]

        # Remove items from Treeview
        for item in selected_items:
            self.tree_stages.delete(item)

        # Update Stage No. in Treeview
        for idx, item in enumerate(self.tree_stages.get_children(), start=1):
            self.tree_stages.item(item, values=(idx, self.stages[idx-1]["voltage_start"],
                                               self.stages[idx-1]["voltage_end"],
                                               self.stages[idx-1]["time"]))

        messagebox.showinfo("Stage Deleted", "选中的实验阶段已被删除。")

    def initialize_storage(self):
        """Initialize the CSV file for storage."""
        storage_path = self.entry_storage_path.get()
        if not storage_path:
            messagebox.showerror("Storage Path Error", "请指定数据存储路径。")
            return False

        file_path = os.path.join(storage_path, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            self.storage_file = open(file_path, mode='w', newline='')
            self.storage_writer = csv.writer(self.storage_file)
            self.storage_writer.writerow(["Timestamp", "Voltage (V)", "Current (A)", "Power (W)"])
            return True
        except Exception as e:
            messagebox.showerror("Storage Initialization Error", f"无法创建CSV文件。\n{e}")
            return False

    def storage_consumer(self):
        """Consumer thread that writes data to CSV."""
        while not self.storage_stop_event.is_set():
            try:
                timestamp, voltage, current = self.storage_queue.get(timeout=0.1)
                power = voltage * current
                with self.storage_lock:
                    self.storage_writer.writerow([timestamp, voltage, current, power])
                    self.storage_file.flush()  # 确保数据及时写入磁盘
            except queue.Empty:
                continue
            except Exception as e:
                messagebox.showerror("Storage Error", f"数据存储时出错。\n{e}")
                break

    def collect_data_for_stage(self, stage, sample_interval):
        """Collect data for a given stage."""
        voltage = self.power_supply.V()
        current = self.power_supply.A()
        timestamp = time.time()

        # Put data into both queues
        self.plot_queue.put((timestamp, voltage, current))
        self.storage_queue.put((timestamp, voltage, current))

    def collect_data(self, sample_rate):
        """Collect data for the experiment stages."""
        sample_interval = 1.0 / sample_rate  # Calculate time interval for each sample

        for stage in self.stages:
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            # Calculate voltage increment per sample
            if duration == 0:
                voltage_increment = 0
            else:
                voltage_increment = (voltage_end - voltage_start) * sample_interval / duration

            # Start with initial voltage and gradually change it
            current_voltage = voltage_start
            start_time = time.time()

            # Set initial voltage
            self.power_supply.V(current_voltage)

            # Loop through the time duration of the stage
            while time.time() - start_time < duration:
                self.collect_data_for_stage(stage, sample_interval)

                # Update the voltage for the next sample
                current_voltage += voltage_increment

                # Ensure the voltage stays within the bounds of start and end voltages
                if voltage_increment > 0 and current_voltage > voltage_end:
                    current_voltage = voltage_end
                elif voltage_increment < 0 and current_voltage < voltage_end:
                    current_voltage = voltage_end

                self.power_supply.V(current_voltage)  # Set the power supply voltage

                time.sleep(sample_interval)  # Wait for the next sample

        self.experiment_done_event.set()

    def start_experiment(self):
        """Start the experiment in separate threads."""
        if not self.stages:
            messagebox.showerror("No Stages", "请添加至少一个实验阶段。")
            return

        if not self.power_supply:
            if self.use_virtual_var.get():
                # Virtual power supply is already initialized in toggle_virtual_mode
                pass
            else:
                messagebox.showerror("No Power Supply", "请先选择串口或启用虚拟电源。")
                return

        if self.is_experiment_running:
            messagebox.showwarning("Experiment Running", "实验已经在运行中。")
            return

        if not self.initialize_storage():
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        try:
            sample_rate = int(self.entry_sample_rate.get()) if self.entry_sample_rate.get() else Config.DEFAULT_SAMPLE_RATE
        except ValueError:
            messagebox.showerror("Invalid Sample Rate", "采样频率必须是一个整数。")
            self.is_experiment_running = False
            return

        # Initialize and start the plot window
        plot_root = tk.Toplevel(self.root)
        self.plot_window = PlotWindow(plot_root)
        self.plot_window.start_animation(self.plot_queue, self.plot_stop_event)

        # Start storage consumer thread
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()

        # Start data collection thread
        threading.Thread(target=self.collect_data, args=(sample_rate,), daemon=True).start()

        # Start a thread to monitor experiment completion
        threading.Thread(target=self.monitor_experiment, daemon=True).start()

    def monitor_experiment(self):
        """Monitor the experiment and handle post-experiment tasks."""
        self.experiment_done_event.wait()  # Wait until the experiment is done

        # Signal the plot window and storage thread to stop
        self.plot_stop_event.set()
        self.storage_stop_event.set()

        # Wait for storage thread to finish
        if self.storage_thread is not None:
            self.storage_thread.join()

        # Close the storage file
        if self.storage_file is not None:
            self.storage_file.close()

        # Save the collected data to CSV is already handled by the storage consumer

        self.is_experiment_running = False
        messagebox.showinfo("Experiment Complete", "实验已完成，数据已保存。")

# Start the Tkinter window and GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
