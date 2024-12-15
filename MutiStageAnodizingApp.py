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
import pymodbus as modbus_rtu  # 假设有一个modbus_rtu模块

# 配置类，集中管理所有常量
class Config:
    # 串口通信配置
    BAUD_RATE = 9600
    TIMEOUT = 1

    # Modbus寄存器地址
    REG_VOLTAGE = 0x0010
    REG_CURRENT = 0x0011
    REG_VOLTAGE_SET = 0x0030
    REG_CURRENT_SET = 0x0031
    REG_NAME = 0x0003
    REG_CLASS_NAME = 0x0004
    REG_DOT = 0x0005
    REG_PROTECTION_STATE = 0x0002

    # 电源保护状态标志
    OVP = 0x01
    OCP = 0x02
    OPP = 0x04
    OTP = 0x08
    SCP = 0x10

    # 默认波特率和超时时间
    TIMEOUT_READ = 1.0

    # 默认文件保存路径
    DEFAULT_SAMPLE_RATE = 10  # 10Hz


class PowerSupply:
    """
    电源类
    """

    def __init__(self, serial_obj: serial.Serial, addr: int):
        """
        构造函数
        :param serial_obj: 串口类
        :param addr: 从机地址
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
        读取寄存器
        :param reg_addr: 寄存器地址
        :param reg_len: 寄存器个数，1~2
        :return: 数据
        """
        if reg_len <= 1:
            return self.modbus_rtu_obj.execute(self.addr, modbus_rtu.READ_HOLDING_REGISTERS, reg_addr, reg_len)[0]
        elif reg_len >= 2:
            raw_tuple = self.modbus_rtu_obj.execute(self.addr, modbus_rtu.READ_HOLDING_REGISTERS, reg_addr, reg_len)
            return raw_tuple[0] << 16 | raw_tuple[1]

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        """
        写入数据
        :param reg_addr: 寄存器地址
        :param data: 待写入的数据
        :param data_len: 数据长度
        :return: 写入状态
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
        读取表显电压或写入目标电压
        :param V_input: 电压值，单位：伏特
        :return: 表显电压或目标电压
        """
        if V_input is None:
            return self.read(Config.REG_VOLTAGE) / self.V_dot
        else:
            self.write(Config.REG_VOLTAGE_SET, int(V_input * self.V_dot + 0.5))
            return self.read(Config.REG_VOLTAGE_SET) / self.V_dot

    def A(self, A_input: float = None):
        """
        读取表显电流或写入限制电流
        :param A_input: 电流值，单位：安
        :return: 表显电流或限制电流
        """
        if A_input is None:
            return self.read(Config.REG_CURRENT) / self.A_dot
        else:
            self.write(Config.REG_CURRENT_SET, int(A_input * self.A_dot + 0.5))
            return self.read(Config.REG_CURRENT_SET) / self.A_dot


class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("实验控制面板")

        # 初始化串口连接
        self.serial_obj = None  # 假设串口对象
        self.power_supply = None  # 假设电源对象

        # 存储实验阶段
        self.stages = []

        # 串口选择
        self.label_serial = tk.Label(root, text="选择串口:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5)

        self.serial_ports = self.get_serial_ports()  # 获取串口列表
        self.combo_serial = ttk.Combobox(root, values=self.serial_ports)
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5)
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)  # 绑定选择事件

        # 选择电压输入框
        self.label_voltage_start = tk.Label(root, text="初始电压(V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5)

        self.entry_voltage_start = tk.Entry(root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5)

        # 终止电压输入框
        self.label_voltage_end = tk.Label(root, text="终止电压(V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5)

        self.entry_voltage_end = tk.Entry(root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5)

        # 时间输入框
        self.label_time = tk.Label(root, text="设置时间(s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5)

        self.entry_time = tk.Entry(root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5)

        # 采样频率输入框
        self.label_sample_rate = tk.Label(root, text="采样频率(Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5)

        self.entry_sample_rate = tk.Entry(root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5)
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))  # 默认10Hz

        # 存储路径选择
        self.label_storage_path = tk.Label(root, text="存储路径:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5)

        self.entry_storage_path = tk.Entry(root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5)

        self.button_browse = tk.Button(root, text="浏览", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5)

        # 添加阶段按钮
        self.button_add_stage = tk.Button(root, text="添加阶段", command=self.add_stage)
        self.button_add_stage.grid(row=6, column=0, columnspan=2, pady=5)

        # 开始实验按钮
        self.button_start = tk.Button(root, text="开始实验", command=self.start_experiment)
        self.button_start.grid(row=7, column=0, columnspan=2, pady=5)

    def get_serial_ports(self):
        """获取并返回可用串口列表"""
        ports = list(serial.tools.list_ports.comports())
        return [port.device for port in ports] if ports else []

    def set_serial_port(self, event):
        """
        设置串口
        :param event: 选择事件
        """
        port = self.combo_serial.get()
        if port:
            self.serial_obj = serial.Serial(port, Config.BAUD_RATE, timeout=Config.TIMEOUT)
            self.power_supply = PowerSupply(self.serial_obj, 1)

    def browse_storage_path(self):
        """
        浏览文件夹选择存储路径
        """
        path = filedialog.askdirectory()
        if path:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, path)

    def add_stage(self):
        """
        添加实验阶段
        """
        voltage_start = float(self.entry_voltage_start.get())
        voltage_end = float(self.entry_voltage_end.get())
        time_duration = float(self.entry_time.get())
        sample_rate = int(self.entry_sample_rate.get())
        storage_path = self.entry_storage_path.get()

        # 保存阶段信息
        self.stages.append({
            'voltage_start': voltage_start,
            'voltage_end': voltage_end,
            'time_duration': time_duration,
            'sample_rate': sample_rate,
            'storage_path': storage_path
        })
        messagebox.showinfo("阶段添加", "阶段添加成功！")

    def start_experiment(self):
        """
        开始实验
        """
        if not self.power_supply:
            messagebox.showerror("错误", "未连接电源！")
            return

        if not self.stages:
            messagebox.showerror("错误", "请添加至少一个实验阶段！")
            return

        # 在新线程中执行实验
        threading.Thread(target=self.run_experiment).start()

    def run_experiment(self):
        """
        运行实验
        """
        for stage in self.stages:
            self.power_supply.V(stage['voltage_start'])
            start_time = time.time()

            # 在文件中保存数据
            data = []

            while time.time() - start_time < stage['time_duration']:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                voltage = self.power_supply.V()
                current = self.power_supply.A()
                data.append([current_time, voltage, current, voltage * current])  # 时间、电压、电流、功率

                time.sleep(1 / stage['sample_rate'])

            # 保存数据到CSV文件
            self.save_to_csv(data, stage['storage_path'])

            messagebox.showinfo("实验结束", "实验完成！")

    def save_to_csv(self, data, storage_path):
        """
        保存数据到CSV文件
        """
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

        filename = os.path.join(storage_path, f"实验数据_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['时间', '电压(V)', '电流(A)', '功率(W)'])
            writer.writerows(data)


# 运行GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()
