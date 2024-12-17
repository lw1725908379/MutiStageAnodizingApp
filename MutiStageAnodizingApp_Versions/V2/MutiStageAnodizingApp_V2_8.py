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

# -------------------------
# 配置和日志设置
# -------------------------
# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class Config:
    # -------------------------
    # 串行通信设置
    # -------------------------
    BAUD_RATE = 9600          # 串行通信波特率
    TIMEOUT = 1               # 串行通信超时时间（秒）

    # -------------------------
    # 电源供应器寄存器地址
    # -------------------------
    REG_VOLTAGE = 0x0010      # 电压读取寄存器
    REG_CURRENT = 0x0011      # 电流读取寄存器
    REG_VOLTAGE_SET = 0x0030  # 设置电压寄存器
    REG_CURRENT_SET = 0x0031  # 设置电流寄存器

    REG_NAME = 0x0003         # 电源名称寄存器
    REG_CLASS_NAME = 0x0004   # 电源类别名称寄存器
    REG_DOT = 0x0005          # 缩放因子（点）寄存器
    REG_PROTECTION_STATE = 0x0002  # 保护状态寄存器（过压、过流等）
    REG_ADDR = 0x9999         # 设备地址读取寄存器
    REG_OPERATIVE_MODE = 0x0001   # 操作模式寄存器（读取或设置）
    REG_DISPLAYED_POWER = 0x0012  # 显示功率读取寄存器（瓦特）

    # -------------------------
    # 保护状态标志
    # -------------------------
    OVP = 0x01                # 过压保护标志
    OCP = 0x02                # 过流保护标志
    OPP = 0x04                # 过功率保护标志
    OTP = 0x08                # 过温保护标志
    SCP = 0x10                # 短路保护标志

    # -------------------------
    # 保护设置寄存器
    # -------------------------
    REG_OVP = 0x0020          # 过压保护设置寄存器
    REG_OCP = 0x0021          # 过流保护设置寄存器
    REG_OPP = 0x0022          # 过功率保护设置寄存器

    # -------------------------
    # 从设备地址寄存器
    # -------------------------
    REG_ADDR_SLAVE = 0x9999   # 从设备地址设置或读取寄存器

    # -------------------------
    # 默认设置
    # -------------------------
    TIMEOUT_READ = 1.0        # 默认读取超时时间（秒）
    DEFAULT_SAMPLE_RATE = 10  # 默认采样率（Hz）

class PowerSupply:
    """
    电源供应器类，使用pymodbus库进行Modbus RTU通信
    """

    def __init__(self, port: str, addr: int, retries: int = 5, delay: float = 1.0):
        self.client = ModbusSerialClient(method='rtu', port=port, baudrate=Config.BAUD_RATE, timeout=Config.TIMEOUT)
        for attempt in range(retries):
            connection = self.client.connect()
            if connection:
                logging.info(f"成功连接到端口: {port} 的Modbus客户端")
                break
            else:
                logging.warning(f"无法连接到端口: {port} 的Modbus客户端，正在重试 {attempt + 1}/{retries}...")
                time.sleep(delay)
        else:
            logging.error(f"无法连接到端口: {port} 的Modbus客户端，所有重试均失败")
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
                logging.debug(f"向寄存器 {reg_addr} 写入值 {data}，读取回值: {read_back}")
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
                logging.debug(f"向寄存器 {reg_addr} 写入值 {high}，读取回值: {read_back1}")
                logging.debug(f"向寄存器 {reg_addr + 1} 写入值 {low}，读取回值: {read_back2}")
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
                logging.debug(f"电压设置成功，实际电压: {actual_voltage} V")
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
                logging.debug(f"电流设置成功，实际电流: {actual_current} A")
                return actual_current
            else:
                logging.error("电流设置失败")
                return None

    def W(self):
        """
        读取显示的功率
        :return: 显示的功率（瓦特）
        """
        return self.read(Config.REG_DISPLAYED_POWER, 2) / self.W_dot

    def OVP(self, OVP_input: float = None):
        """
        读取或写入过压保护设置
        :param OVP_input: 过压保护设置
        :return: 过压保护设置
        """
        if OVP_input is None:
            return self.read(Config.REG_OVP) / self.V_dot
        else:
            self.write(Config.REG_OVP, int(OVP_input * self.V_dot + 0.5))
            return self.read(Config.REG_OVP) / self.V_dot

    def OCP(self, OCP_input: float = None):
        """
        读取或写入过流保护设置
        :param OCP_input: 过流保护设置
        :return: 过流保护设置
        """
        if OCP_input is None:
            return self.read(Config.REG_OCP) / self.A_dot
        else:
            self.write(Config.REG_OCP, int(OCP_input * self.A_dot + 0.5))
            return self.read(Config.REG_OCP) / self.A_dot

    def OPP(self, OPP_input: float = None):
        """
        读取或写入过功率保护设置
        :param OPP_input: 过功率保护设置
        :return: 过功率保护设置
        """
        if OPP_input is None:
            return self.read(Config.REG_OPP, 2) / self.W_dot
        else:
            self.write(Config.REG_OPP, int(OPP_input * self.W_dot + 0.5), 2)
            return self.read(Config.REG_OPP, 2) / self.W_dot

    def Addr(self, addr_input: int = None):
        """
        读取或更改从设备地址
        :param addr_input: 要设置的从设备地址，范围1到250
        :return: 从设备地址
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
        logging.info(f"将目标电压从 {old_volt} V 设置为 {V_input} V")
        self.V(V_input)
        start_time = time.time()
        while True:
            current_volt = self.V()  # 读取实际电压
            if abs(current_volt - V_input) <= error_range:
                break
            if (time.time() - start_time) > timeout:
                raise ValueError("电压设置超时")
            time.sleep(0.1)
        elapsed_time = time.time() - start_time
        logging.info(f"电压设置为 {current_volt} V，用时 {elapsed_time:.2f} 秒")

    def operative_mode(self, mode_input: int = None):
        """
        读取或写入操作模式
        :param mode_input: 操作模式，1: 启用输出; 0: 禁用输出
        :return: 当前操作模式
        """
        if mode_input is None:
            return self.read(Config.REG_OPERATIVE_MODE)
        else:
            self.write(Config.REG_OPERATIVE_MODE, mode_input)
            return self.read(Config.REG_OPERATIVE_MODE)
class PlotWindow:
    def __init__(self, master):
        self.master = master
        self.master.title("实时数据绘图")

        # 创建Matplotlib图形
        self.fig, (self.ax_voltage, self.ax_current, self.ax_power) = plt.subplots(3, 1, figsize=(8, 6))
        self.fig.tight_layout(pad=3.0)

        self.voltage_line, = self.ax_voltage.plot([], [], label='电压 (V)', color='blue')
        self.current_line, = self.ax_current.plot([], [], label='电流 (A)', color='green')
        self.power_line, = self.ax_power.plot([], [], label='功率 (W)', color='red')

        self.ax_voltage.set_title('电压随时间变化')
        self.ax_voltage.set_xlabel('时间 (s)')
        self.ax_voltage.set_ylabel('电压 (V)')
        self.ax_voltage.legend()
        self.ax_voltage.grid(True)

        self.ax_current.set_title('电流随时间变化')
        self.ax_current.set_xlabel('时间 (s)')
        self.ax_current.set_ylabel('电流 (A)')
        self.ax_current.legend()
        self.ax_current.grid(True)

        self.ax_power.set_title('功率随时间变化')
        self.ax_power.set_xlabel('时间 (s)')
        self.ax_power.set_ylabel('功率 (W)')
        self.ax_power.legend()
        self.ax_power.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 数据存储
        self.start_time = None  # 记录首次数据接收的时间戳
        self.times = []
        self.voltages = []
        self.currents = []
        self.powers = []
        self.lock = threading.Lock()

    def update_plot(self, timestamp, voltage, current):
        with self.lock:
            # 将时间戳归一化为从0开始
            if self.start_time is None:
                self.start_time = timestamp  # 记录开始时间
            normalized_time = timestamp - self.start_time

            self.times.append(normalized_time)
            self.voltages.append(voltage)
            self.currents.append(current)
            self.powers.append(voltage * current)

            # 限制绘图数据点数量以保持图形流畅
            MAX_DATA_POINTS = 1000
            if len(self.times) > MAX_DATA_POINTS:
                self.times = self.times[-MAX_DATA_POINTS:]
                self.voltages = self.voltages[-MAX_DATA_POINTS:]
                self.currents = self.currents[-MAX_DATA_POINTS:]
                self.powers = self.powers[-MAX_DATA_POINTS:]

            # 更新绘图数据
            self.voltage_line.set_data(self.times, self.voltages)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()

            self.current_line.set_data(self.times, self.currents)
            self.ax_current.relim()
            self.ax_current.autoscale_view()

            self.power_line.set_data(self.times, self.powers)
            self.ax_power.relim()
            self.ax_power.autoscale_view()

            # 刷新图形
            self.canvas.draw()

    def start_animation(self, plot_queue, stop_event):
        """ 启动绘图更新线程 """
        def animate():
            while not stop_event.is_set():
                try:
                    timestamp, voltage, current = plot_queue.get(timeout=0.1)
                    self.update_plot(timestamp, voltage, current)
                except queue.Empty:
                    continue
        threading.Thread(target=animate, daemon=True).start()
# 串口管理模块
class SerialManager:
    def __init__(self):
        self.power_supply = None

    def get_serial_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        logging.debug(f"可用的串口: {ports}")
        return ports

    def connect(self, port):
        if port:
            try:
                self.power_supply = PowerSupply(port, 1)
                logging.info(f"成功连接到串口: {port}")
                return True, f"已连接到 {port}"
            except Exception as e:
                logging.error(f"连接到串口 {port} 失败: {e}")
                return False, f"连接到 {port} 失败\n{e}"
        else:
            return False, "未选择串口。"

    def disconnect(self):
        if self.power_supply and self.power_supply.client:
            self.power_supply.client.close()
            logging.info("已关闭Modbus客户端连接")
            self.power_supply = None
# 阶段管理模块
class StageManager:
    def __init__(self):
        self.stages = []

    def add_stage(self, voltage_start, voltage_end, time_duration):
        stage = {
            "voltage_start": voltage_start,
            "voltage_end": voltage_end,
            "time": time_duration
        }
        self.stages.append(stage)
        logging.info(f"添加实验阶段: {stage}")
        return stage

    def delete_stage(self, indices):
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.stages):
                removed_stage = self.stages.pop(index)
                logging.info(f"删除实验阶段: {removed_stage}")

    def get_stages(self):
        return self.stages
# 数据存储管理模块
class StorageManager:
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.storage_file = None
        self.storage_writer = None
        self.lock = threading.Lock()

    def initialize_storage(self):
        if not self.storage_path:
            logging.error("未指定数据存储路径")
            return False, "未指定存储路径。"

        file_path = os.path.join(self.storage_path, f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            self.storage_file = open(file_path, mode='w', newline='')
            self.storage_writer = csv.writer(self.storage_file)
            self.storage_writer.writerow(["Timestamp", "Voltage (V)", "Current (A)", "Power (W)"])
            logging.info(f"初始化数据存储文件: {file_path}")
            return True, f"数据存储已初始化于 {file_path}"
        except Exception as e:
            logging.exception(f"初始化数据存储文件时出错: {e}")
            return False, f"创建CSV文件失败。\n{e}"

    def store_data(self, timestamp, voltage, current):
        if self.storage_writer:
            power = voltage * current
            with self.lock:
                self.storage_writer.writerow([timestamp, voltage, current, power])
                self.storage_file.flush()
            logging.debug(f"存储数据: {timestamp}, {voltage}, {current}, {power}")

    def close_storage(self):
        if self.storage_file:
            self.storage_file.close()
            logging.info("已关闭存储文件")
# 数据采集模块
class DataCollector:
    def __init__(self, power_supply, storage_manager, plot_queue):
        self.power_supply = power_supply
        self.storage_manager = storage_manager
        self.plot_queue = plot_queue

    def collect_data_for_stage(self):
        try:
            voltage = self.power_supply.V()
            if voltage is None:
                logging.error("读取电压失败，跳过此采样")
                return
            current = self.power_supply.A()
            if current is None:
                logging.error("读取电流失败，跳过此采样")
                return
            timestamp = time.time()
            self.plot_queue.put((timestamp, voltage, current))
            self.storage_manager.store_data(timestamp, voltage, current)
            logging.debug(f"收集数据: {timestamp}, {voltage}, {current}")
        except Exception as e:
            logging.exception(f"收集实验阶段数据时出错: {e}")
# 实验控制模块
class ExperimentController:
    def __init__(self, serial_manager, stage_manager, storage_manager, data_collector, plot_window, plot_stop_event, storage_stop_event, experiment_done_event):
        self.serial_manager = serial_manager
        self.stage_manager = stage_manager
        self.storage_manager = storage_manager
        self.data_collector = data_collector
        self.plot_window = plot_window
        self.plot_stop_event = plot_stop_event
        self.storage_stop_event = storage_stop_event
        self.experiment_done_event = experiment_done_event
        self.is_experiment_running = False
        self.storage_thread = None

    def collect_data_once_per_second(self, sample_rate=1):
        for stage in self.stage_manager.get_stages():
            voltage_start = stage["voltage_start"]
            voltage_end = stage["voltage_end"]
            duration = stage["time"]

            if duration == 0:
                voltage_increment = 0
            else:
                voltage_increment = (voltage_end - voltage_start) / duration

            logging.debug(
                f"阶段开始 - 初始电压: {voltage_start} V, 终止电压: {voltage_end} V, 持续时间: {duration} s, 电压增量: {voltage_increment} V/s")

            current_voltage = voltage_start
            start_time = time.time()
            end_time = start_time + duration

            self.serial_manager.power_supply.set_volt(current_voltage)

            while time.time() < end_time:
                cycle_start = time.time()

                # 更新电压
                current_voltage += voltage_increment

                # 确保电压不超过终止电压
                if voltage_increment > 0 and current_voltage > voltage_end:
                    current_voltage = voltage_end
                elif voltage_increment < 0 and current_voltage < voltage_end:
                    current_voltage = voltage_end

                # 设置新的电压
                self.serial_manager.power_supply.set_volt(current_voltage)

                # 采集数据
                self.data_collector.collect_data_for_stage()

                # 计算本周期已用时间
                elapsed = time.time() - cycle_start
                # 计算剩余时间以保证循环间隔为1秒
                sleep_time = max(0, (1.0 / sample_rate) - elapsed)
                time.sleep(sleep_time)

            logging.info("完成此阶段的数据采集")

        self.experiment_done_event.set()
        logging.info("实验完成")

    def collect_data_with_sample_rate(self, sample_rate):
        sample_interval = 1.0 / sample_rate
        logging.info(f"开始数据采集，采样频率: {sample_rate} Hz")

        try:
            for stage in self.stage_manager.get_stages():
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                if duration == 0:
                    voltage_increment = 0
                else:
                    voltage_increment = (voltage_end - voltage_start) * sample_interval / duration

                logging.debug(
                    f"阶段开始 - 初始电压: {voltage_start} V, 终止电压: {voltage_end} V, 持续时间: {duration} s, 电压增量: {voltage_increment} V")

                current_voltage = voltage_start
                start_time = time.perf_counter()
                end_time = start_time + duration

                self.serial_manager.power_supply.set_volt(current_voltage)

                while True:
                    current_time = time.perf_counter()
                    if current_time >= end_time:
                        break

                    # 更新电压
                    current_voltage += voltage_increment
                    if (voltage_increment > 0 and current_voltage > voltage_end) or \
                            (voltage_increment < 0 and current_voltage < voltage_end):
                        current_voltage = voltage_end
                    self.serial_manager.power_supply.set_volt(current_voltage)

                    # 采集数据
                    self.data_collector.collect_data_for_stage()

                    # 计算下一次采样的时间
                    next_sample_time = current_time + sample_interval
                    sleep_duration = next_sample_time - time.perf_counter()
                    if sleep_duration > 0:
                        time.sleep(sleep_duration)

                logging.info("完成此阶段的数据采集")

        except Exception as e:
            logging.error(f"数据采集过程中发生错误: {e}")
        finally:
            self.experiment_done_event.set()
            logging.info("实验完成")

    def start_experiment(self, sample_rate):
        if self.is_experiment_running:
            logging.warning("尝试启动实验，但已有实验在运行中")
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        # 启动绘图窗口
        self.plot_window.start_animation(self.data_collector.plot_queue, self.plot_stop_event)
        logging.info("绘图窗口已启动")

        # 启动存储线程
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()
        logging.info("存储消费者线程已启动")

        # 启动数据采集线程
        data_thread = threading.Thread(target=self.collect_data_once_per_second, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("数据采集线程已启动")

    def storage_consumer(self):
        while not self.storage_stop_event.is_set():
            time.sleep(0.05)  # 简单的等待机制，可以根据需要优化

    def monitor_experiment(self):
        self.experiment_done_event.wait()
        logging.info("接收到实验完成信号")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("存储消费者线程已结束")

        self.storage_manager.close_storage()
        self.serial_manager.disconnect()

        self.is_experiment_running = False
        messagebox.showinfo("实验完成", "实验完成，数据已保存。")
        logging.info("显示实验完成消息")
# 主GUI类
class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("实验控制面板")

        # 初始化模块
        self.serial_manager = SerialManager()
        self.stage_manager = StageManager()
        self.storage_manager = None  # 初始化时为空
        self.plot_queue = queue.Queue()
        self.plot_stop_event = threading.Event()
        self.storage_stop_event = threading.Event()
        self.experiment_done_event = threading.Event()
        self.plot_window = None
        self.data_collector = None
        self.experiment_controller = None

        # GUI组件创建
        self.create_widgets()

    def create_widgets(self):
        # 串口选择
        self.label_serial = tk.Label(self.root, text="选择串口:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        self.serial_ports = self.serial_manager.get_serial_ports()
        self.combo_serial = ttk.Combobox(self.root, values=self.serial_ports, state="readonly")
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)

        # 电压和时间设置
        self.label_voltage_start = tk.Label(self.root, text="初始电压 (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.entry_voltage_start = tk.Entry(self.root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        self.label_voltage_end = tk.Label(self.root, text="终止电压 (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.entry_voltage_end = tk.Entry(self.root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        self.label_time = tk.Label(self.root, text="设定时间 (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.entry_time = tk.Entry(self.root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.label_sample_rate = tk.Label(self.root, text="采样率 (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5, sticky='e')
        self.entry_sample_rate = tk.Entry(self.root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))

        # 数据存储路径
        self.label_storage_path = tk.Label(self.root, text="存储路径:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5, sticky='e')
        self.entry_storage_path = tk.Entry(self.root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5, sticky='w')
        self.button_browse = tk.Button(self.root, text="浏览", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5, sticky='w')

        # 按钮框架
        self.frame_buttons = tk.Frame(self.root)
        self.frame_buttons.grid(row=6, column=0, columnspan=3, padx=5, pady=5)
        self.button_add_stage = tk.Button(self.frame_buttons, text="添加阶段", command=self.add_stage, width=15)
        self.button_add_stage.pack(side='left', padx=5)
        self.button_delete_stage = tk.Button(self.frame_buttons, text="删除选定阶段", command=self.delete_stage, width=20)
        self.button_delete_stage.pack(side='left', padx=5)
        self.button_start = tk.Button(self.frame_buttons, text="开始实验", command=self.start_experiment, width=15)
        self.button_start.pack(side='left', padx=5)

        # 阶段树视图
        self.frame_stages = tk.Frame(self.root)
        self.frame_stages.grid(row=7, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.root.grid_rowconfigure(7, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.tree_stages = ttk.Treeview(self.frame_stages, columns=("Stage No.", "Initial Voltage (V)", "Termination Voltage (V)", "Duration (s)"), show='headings', selectmode='extended')
        self.tree_stages.heading("Stage No.", text="阶段编号")
        self.tree_stages.heading("Initial Voltage (V)", text="初始电压 (V)")
        self.tree_stages.heading("Termination Voltage (V)", text="终止电压 (V)")
        self.tree_stages.heading("Duration (s)", text="持续时间 (s)")

        self.tree_stages.column("Stage No.", width=80, anchor='center')
        self.tree_stages.column("Initial Voltage (V)", width=150, anchor='center')
        self.tree_stages.column("Termination Voltage (V)", width=170, anchor='center')
        self.tree_stages.column("Duration (s)", width=100, anchor='center')

        self.scrollbar_stages = ttk.Scrollbar(self.frame_stages, orient="vertical", command=self.tree_stages.yview)
        self.tree_stages.configure(yscroll=self.scrollbar_stages.set)
        self.scrollbar_stages.pack(side='right', fill='y')
        self.tree_stages.pack(fill='both', expand=True)

    # 串口管理
    def set_serial_port(self, event):
        serial_port = self.combo_serial.get()
        if serial_port:
            success, message = self.serial_manager.connect(serial_port)
            if success:
                messagebox.showinfo("串口", message)
            else:
                messagebox.showerror("串口错误", message)

    # 阶段管理
    def add_stage(self):
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())
            stage = self.stage_manager.add_stage(voltage_start, voltage_end, time_duration)

            stage_no = len(self.stage_manager.get_stages())
            self.tree_stages.insert('', 'end', values=(stage_no, voltage_start, voltage_end, time_duration))

            messagebox.showinfo("阶段添加", f"已添加阶段: {stage}")
        except ValueError:
            messagebox.showerror("输入无效", "请输入有效的电压和时间值。")
            logging.error("添加实验阶段时输入无效")

    def delete_stage(self):
        selected_items = self.tree_stages.selection()
        if not selected_items:
            messagebox.showwarning("无选定", "请选择要删除的阶段。")
            logging.warning("尝试删除实验阶段但未选择任何项")
            return

        confirm = messagebox.askyesno("确认删除", "确定要删除选定的阶段吗？")
        if not confirm:
            return

        indices = []
        for item in selected_items:
            values = self.tree_stages.item(item, 'values')
            stage_no = int(values[0]) - 1
            indices.append(stage_no)

        self.stage_manager.delete_stage(indices)

        for item in selected_items:
            self.tree_stages.delete(item)

        # 更新树视图中的阶段编号
        for idx, item in enumerate(self.tree_stages.get_children(), start=1):
            stage = self.stage_manager.get_stages()[idx-1]
            self.tree_stages.item(item, values=(idx, stage["voltage_start"],
                                               stage["voltage_end"],
                                               stage["time"]))

        messagebox.showinfo("阶段删除", "已删除选定的阶段。")
        logging.info(f"已删除实验阶段: {selected_items}")

    # 辅助功能
    def browse_storage_path(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder_selected)
            logging.info(f"选择的数据存储路径: {folder_selected}")

    # 实验控制
    def start_experiment(self):
        if not self.stage_manager.get_stages():
            messagebox.showerror("无阶段", "请至少添加一个实验阶段。")
            logging.error("尝试启动实验但未添加任何阶段")
            return

        if not self.serial_manager.power_supply:
            messagebox.showerror("未选择串口", "请先选择一个串口。")
            logging.error("尝试启动实验但未选择串口")
            return

        if self.experiment_controller and self.experiment_controller.is_experiment_running:
            messagebox.showwarning("实验运行中", "已有实验正在运行。")
            logging.warning("尝试启动实验但已有实验在运行")
            return

        storage_path = self.entry_storage_path.get()
        self.storage_manager = StorageManager(storage_path)
        success, message = self.storage_manager.initialize_storage()
        if not success:
            messagebox.showerror("存储初始化错误", message)
            return

        self.data_collector = DataCollector(self.serial_manager.power_supply, self.storage_manager, self.plot_queue)
        self.plot_window = PlotWindow(tk.Toplevel(self.root))
        self.experiment_controller = ExperimentController(
            self.serial_manager,
            self.stage_manager,
            self.storage_manager,
            self.data_collector,
            self.plot_window,
            self.plot_stop_event,
            self.storage_stop_event,
            self.experiment_done_event
        )

        try:
            sample_rate = int(self.entry_sample_rate.get()) if self.entry_sample_rate.get() else Config.DEFAULT_SAMPLE_RATE
        except ValueError:
            messagebox.showerror("采样率无效", "采样率必须是整数。")
            logging.error("采样率输入无效")
            return

        try:
            self.serial_manager.power_supply.operative_mode(1)  # 设置操作模式为1（启用输出）
            logging.info("操作模式已设置为1（输出已启用）。")
        except Exception as e:
            messagebox.showerror("操作模式错误", f"设置操作模式失败: {e}")
            logging.error(f"设置操作模式失败: {e}")
            return

        # 启动实验控制器
        self.experiment_controller.start_experiment(sample_rate)

        # 启动实验监控线程
        monitor_thread = threading.Thread(target=self.experiment_controller.monitor_experiment, daemon=True)
        monitor_thread.start()
        logging.info("实验监控线程已启动")
# 主程序入口
def main():
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
