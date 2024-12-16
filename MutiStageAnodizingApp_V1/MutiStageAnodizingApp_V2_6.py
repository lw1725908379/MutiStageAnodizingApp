import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import time
import threading
import serial.tools.list_ports
import os
import csv
from datetime import datetime
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.constants import Defaults
from pymodbus.exceptions import ModbusException
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import logging
import matplotlib.animation as animation

# 设置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置类，集中管理所有常量
class Config:
    # 串口通信配置
    BAUD_RATE = 9600
    TIMEOUT = 1

    # 电源寄存器地址（根据您的设备文档进行确认和调整）
    REG_VOLTAGE = 0x0010
    REG_CURRENT = 0x0011
    REG_VOLTAGE_SET = 0x0030
    REG_CURRENT_SET = 0x0031
    REG_NAME = 0x0003
    REG_CLASS_NAME = 0x0004
    REG_DOT = 0x0005
    REG_PROTECTION_STATE = 0x0002
    REG_ADDR = 0x9999

    # 电源保护状态标志
    OVP = 0x01
    OCP = 0x02
    OPP = 0x04
    OTP = 0x08
    SCP = 0x10

    # 默认读取超时
    TIMEOUT_READ = 1.0

    # 默认采样频率
    DEFAULT_SAMPLE_RATE = 10  # 10Hz

class PowerSupply:
    """
    电源类，使用pymodbus库进行Modbus RTU通信
    """

    def __init__(self, port: str, addr: int, retries: int = 5, delay: float = 1.0):
        self.client = ModbusSerialClient(method='rtu', port=port, baudrate=Config.BAUD_RATE, timeout=Config.TIMEOUT)
        for attempt in range(retries):
            connection = self.client.connect()
            if connection:
                logging.info(f"成功连接到Modbus客户端，端口: {port}")
                break
            else:
                logging.warning(f"无法连接到Modbus客户端，端口: {port}，尝试重试 {attempt + 1}/{retries}...")
                time.sleep(delay)
        else:
            logging.error(f"无法连接到Modbus客户端，端口: {port}，所有重试均失败")
            raise Exception("Modbus客户端连接失败")

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

        logging.debug(f"缩放因子 - W_dot: {self.W_dot}, A_dot: {self.A_dot}, V_dot: {self.V_dot}")
        logging.debug(f"保护状态 - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")

        self.set_volt(0)

    def read(self, reg_addr: int, reg_len: int = 1):
        try:
            response = self.client.read_holding_registers(reg_addr, reg_len, unit=self.addr)
            if response.isError():
                logging.error(f"读取寄存器 {reg_addr} 时出错: {response}")
                return 0
            if reg_len <= 1:
                return response.registers[0]
            else:
                return (response.registers[0] << 16) | response.registers[1]
        except ModbusException as e:
            logging.exception(f"读取寄存器 {reg_addr} 时发生Modbus异常: {e}")
            return 0
        except Exception as e:
            logging.exception(f"读取寄存器 {reg_addr} 时发生异常: {e}")
            return 0

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        try:
            if data_len <= 1:
                response = self.client.write_register(reg_addr, data, unit=self.addr)
                if response.isError():
                    logging.error(f"写入寄存器 {reg_addr} 时出错: {response}")
                    return False
                read_back = self.read(reg_addr)
                logging.debug(f"写入寄存器 {reg_addr} 值: {data}, 读取回值: {read_back}")
                return read_back == data
            else:
                high = data >> 16
                low = data & 0xFFFF
                response1 = self.client.write_register(reg_addr, high, unit=self.addr)
                response2 = self.client.write_register(reg_addr + 1, low, unit=self.addr)
                if response1.isError() or response2.isError():
                    logging.error(f"写入寄存器 {reg_addr} 和 {reg_addr + 1} 时出错: {response1}, {response2}")
                    return False
                read_back1 = self.read(reg_addr)
                read_back2 = self.read(reg_addr + 1)
                logging.debug(f"写入寄存器 {reg_addr} 值: {high}, 读取回值: {read_back1}")
                logging.debug(f"写入寄存器 {reg_addr + 1} 值: {low}, 读取回值: {read_back2}")
                return read_back1 == high and read_back2 == low
        except ModbusException as e:
            logging.exception(f"写入寄存器 {reg_addr} 时发生Modbus异常: {e}")
            return False
        except Exception as e:
            logging.exception(f"写入寄存器 {reg_addr} 时发生异常: {e}")
            return False

    def read_protection_state(self):
        protection_state_int = self.read(Config.REG_PROTECTION_STATE)
        self.isOVP = protection_state_int & Config.OVP
        self.isOCP = (protection_state_int & Config.OCP) >> 1
        self.isOPP = (protection_state_int & Config.OPP) >> 2
        self.isOTP = (protection_state_int & Config.OTP) >> 3
        self.isSCP = (protection_state_int & Config.SCP) >> 4
        logging.debug(f"更新保护状态 - OVP: {self.isOVP}, OCP: {self.isOCP}, OPP: {self.isOPP}, OTP: {self.isOTP}, SCP: {self.isSCP}")
        return protection_state_int

    def V(self, V_input: float = None):
        if V_input is None:
            voltage = self.read(Config.REG_VOLTAGE)
            actual_voltage = voltage / self.V_dot
            logging.debug(f"读取电压: {voltage} 原始值, {actual_voltage} V")
            return actual_voltage
        else:
            logging.debug(f"设置电压为 {V_input} V")
            success = self.write(Config.REG_VOLTAGE_SET, int(V_input * self.V_dot + 0.5))
            if success:
                actual_voltage = self.read(Config.REG_VOLTAGE) / self.V_dot
                logging.debug(f"电压设置完成，实际电压: {actual_voltage} V")
                return actual_voltage
            else:
                logging.error("电压设置失败")
                return None

    def A(self, A_input: float = None):
        if A_input is None:
            current = self.read(Config.REG_CURRENT)
            actual_current = current / self.A_dot
            logging.debug(f"读取电流: {current} 原始值, {actual_current} A")
            return actual_current
        else:
            logging.debug(f"设置电流为 {A_input} A")
            success = self.write(Config.REG_CURRENT_SET, int(A_input * self.A_dot + 0.5))
            if success:
                current_set = self.read(Config.REG_CURRENT_SET)
                actual_current = current_set / self.A_dot
                logging.debug(f"电流设置完成，实际电流: {actual_current} A")
                return actual_current
            else:
                logging.error("电流设置失败")
                return None

    def set_volt(self, V_input, error_range: float = 0.4, timeout: int = 600):
        old_volt = self.V()
        logging.info(f"设置目标电压，从 {old_volt} V 到 {V_input} V")
        self.V(V_input)
        start_time = time.time()
        while True:
            current_volt = self.V()  # 读取实际电压
            if abs(current_volt - V_input) <= error_range:
                break
            if (time.time() - start_time) > timeout:
                raise ValueError("设置电压超时")
            time.sleep(0.1)
        elapsed_time = time.time() - start_time
        logging.info(f"电压已设置为 {current_volt} V, 用时 {elapsed_time:.2f} 秒")

class PlotWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("实时数据绘图")

        # 创建Matplotlib图形
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

        self.times = []
        self.voltages = []
        self.currents = []
        self.powers = []
        self.lock = threading.Lock()

    def update_plot(self, timestamp, voltage, current):
        with self.lock:
            self.times.append(timestamp)
            self.voltages.append(voltage)
            self.currents.append(current)
            self.powers.append(voltage * current)

            MAX_DATA_POINTS = 1000
            if len(self.times) > MAX_DATA_POINTS:
                self.times = self.times[-MAX_DATA_POINTS:]
                self.voltages = self.voltages[-MAX_DATA_POINTS:]
                self.currents = self.currents[-MAX_DATA_POINTS:]
                self.powers = self.powers[-MAX_DATA_POINTS:]

            self.voltage_line.set_data(self.times, self.voltages)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()

            self.current_line.set_data(self.times, self.currents)
            self.ax_current.relim()
            self.ax_current.autoscale_view()

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
        logging.debug(f"可用的串口: {ports}")
        return ports

    def set_serial_port(self, event):
        serial_port = self.combo_serial.get()
        if serial_port:
            try:
                self.power_supply = PowerSupply(serial_port, 1)
                messagebox.showinfo("Serial Port", f"Connected to {serial_port}")
                logging.info(f"成功连接到串口: {serial_port}")
            except Exception as e:
                messagebox.showerror("Serial Port Error", f"Failed to connect to {serial_port}\n{e}")
                logging.error(f"无法连接到串口 {serial_port}: {e}")
                self.power_supply = None

    def browse_storage_path(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder_selected)
            logging.info(f"选择的数据存储路径: {folder_selected}")

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
            logging.info(f"添加实验阶段: {stage}")
        except ValueError:
            messagebox.showerror("Invalid Input", "请为电压和时间输入有效的数值。")
            logging.error("添加实验阶段时输入无效")

    def delete_stage(self):
        selected_items = self.tree_stages.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "请先选择要删除的实验阶段。")
            logging.warning("尝试删除实验阶段但未选择任何项目")
            return

        confirm = messagebox.askyesno("Confirm Deletion", "确定要删除选中的实验阶段吗？")
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

        messagebox.showinfo("Stage Deleted", "选中的实验阶段已被删除。")
        logging.info(f"删除实验阶段: {selected_items}")

    def initialize_storage(self):
        storage_path = self.entry_storage_path.get()
        if not storage_path:
            messagebox.showerror("Storage Path Error", "请指定数据存储路径。")
            logging.error("未指定数据存储路径")
            return False

        file_path = os.path.join(storage_path, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            self.storage_file = open(file_path, mode='w', newline='')
            self.storage_writer = csv.writer(self.storage_file)
            self.storage_writer.writerow(["Timestamp", "Voltage (V)", "Current (A)", "Power (W)"])
            logging.info(f"初始化数据存储文件: {file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Storage Initialization Error", f"无法创建CSV文件。\n{e}")
            logging.exception(f"初始化数据存储文件时出错: {e}")
            return False

    def storage_consumer(self):
        while not self.storage_stop_event.is_set():
            try:
                timestamp, voltage, current = self.storage_queue.get(timeout=0.1)
                power = voltage * current
                with self.storage_lock:
                    self.storage_writer.writerow([timestamp, voltage, current, power])
                    self.storage_file.flush()
                logging.debug(f"存储数据: {timestamp}, {voltage}, {current}, {power}")
            except queue.Empty:
                continue
            except Exception as e:
                messagebox.showerror("Storage Error", f"数据存储时出错。\n{e}")
                logging.exception(f"存储数据时出错: {e}")
                break

    def collect_data_for_stage(self, stage, sample_interval):
        try:
            voltage = self.power_supply.V()
            if voltage is None:
                logging.error("读取电压失败，跳过此次采样")
                return
            current = self.power_supply.A()
            if current is None:
                logging.error("读取电流失败，跳过此次采样")
                return
            timestamp = time.time()
            self.plot_queue.put((timestamp, voltage, current))
            self.storage_queue.put((timestamp, voltage, current))
            logging.debug(f"收集数据: {timestamp}, {voltage}, {current}")
        except Exception as e:
            logging.exception(f"收集阶段数据时出错: {e}")

    def collect_data(self, sample_rate):
        sample_interval = 1.0 / sample_rate
        logging.info(f"开始数据收集，采样频率: {sample_rate} Hz")

        for stage in self.stages:
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            if duration == 0:
                voltage_increment = 0
            else:
                voltage_increment = (voltage_end - voltage_start) * sample_interval / duration

            logging.debug(f"阶段开始 - 初始电压: {voltage_start} V, 终止电压: {voltage_end} V, 持续时间: {duration} s, 电压增量: {voltage_increment} V")

            current_voltage = voltage_start
            start_time = time.time()

            # 设置初始电压
            self.power_supply.set_volt(current_voltage)

            # 在阶段持续时间内循环
            while time.time() - start_time < duration:
                # 1. 更新电压（先计算并设置新电压）
                current_voltage += voltage_increment
                # 确保电压在起始和终止值之间
                if voltage_increment > 0 and current_voltage > voltage_end:
                    current_voltage = voltage_end
                elif voltage_increment < 0 and current_voltage < voltage_end:
                    current_voltage = voltage_end

                self.power_supply.set_volt(current_voltage)

                # 给设备一点时间达到设定电压（这里假设半个采样周期）
                time.sleep(sample_interval * 0.5)

                # 2. 采集数据
                self.collect_data_for_stage(stage, sample_interval)

                # 检查保护状态
                protection_state = self.power_supply.read_protection_state()
                if protection_state != 0:
                    logging.error(f"保护状态被触发: {protection_state}")
                    messagebox.showerror("Protection Triggered", f"保护状态被触发: {protection_state}")
                    self.is_experiment_running = False
                    return

                # 再等待剩余的半个采样周期
                time.sleep(sample_interval * 0.5)

        self.experiment_done_event.set()
        logging.info("数据收集完成")

    def start_experiment(self):
        if not self.stages:
            messagebox.showerror("No Stages", "请添加至少一个实验阶段。")
            logging.error("尝试启动实验但未添加任何阶段")
            return

        if not self.power_supply:
            messagebox.showerror("No Serial Port", "请先选择串口。")
            logging.error("尝试启动实验但未选择串口")
            return

        if self.is_experiment_running:
            messagebox.showwarning("Experiment Running", "实验已经在运行中。")
            logging.warning("尝试启动实验但已有实验在运行")
            return

        if not self.initialize_storage():
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        try:
            sample_rate = int(self.entry_sample_rate.get()) if self.entry_sample_rate.get() else Config.DEFAULT_SAMPLE_RATE
        except ValueError:
            messagebox.showerror("Invalid Sample Rate", "采样频率必须是一个整数。")
            logging.error("输入的采样频率无效")
            self.is_experiment_running = False
            return

        # 启动绘图窗口
        plot_root = tk.Toplevel(self.root)
        self.plot_window = PlotWindow(plot_root)
        self.plot_window.start_animation(self.plot_queue, self.plot_stop_event)
        logging.info("绘图窗口已启动")

        # 启动存储线程
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()
        logging.info("存储消费者线程已启动")

        # 启动数据收集线程
        data_thread = threading.Thread(target=self.collect_data, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("数据收集线程已启动")

        # 监控实验完成的线程
        monitor_thread = threading.Thread(target=self.monitor_experiment, daemon=True)
        monitor_thread.start()
        logging.info("实验监控线程已启动")

    def monitor_experiment(self):
        self.experiment_done_event.wait()
        logging.info("接收到实验完成信号")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("存储消费者线程已结束")

        if self.storage_file is not None:
            self.storage_file.close()
            logging.info("存储文件已关闭")

        if self.power_supply and self.power_supply.client:
            self.power_supply.client.close()
            logging.info("Modbus客户端连接已关闭")

        self.is_experiment_running = False
        messagebox.showinfo("Experiment Complete", "实验已完成，数据已保存。")
        logging.info("向用户显示实验完成信息")

if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
