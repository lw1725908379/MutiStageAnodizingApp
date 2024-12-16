import time
import serial
import serial.tools.list_ports
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import pandas as pd
import numpy as np
import datetime
from time import sleep
from tqdm import tqdm
import seaborn as sns
import matplotlib.pyplot as plt


def connect_serial(keyword: str = "", baud_rate: int = 9600, timeout: int = 1):
    """
    连接串口
    :param keyword: 串口名关键词
    :param baud_rate: 波特率
    :param timeout: 超时时间
    :return: 串口类
    """
    serial_list = list(serial.tools.list_ports.comports())
    if len(serial_list) <= 0:
        raise ValueError("Can't find any available serial ports.")

    if not keyword:
        print("找到以下串口：")
        for serial_port in serial_list:
            print("\t", serial_port)
        keyword = input("请输入要连接的串口关键词：")

    for port in serial_list:
        if keyword.lower() in str(port).lower():
            serial_port = serial.Serial(port.name, baud_rate, timeout=timeout)
            print(f"与 {port} 建立连接！")
            return serial_port

    raise ValueError("指定的串口未找到！")


class PowerSupply:
    """
    电源类，用于Modbus RTU通讯
    """

    def __init__(self, serial_obj: serial.Serial, addr: int):
        self.modbus_rtu_obj = modbus_rtu.RtuMaster(serial_obj)
        self.modbus_rtu_obj.set_timeout(1.0)
        self.addr = addr
        self.name = self.read(0x0003)
        self.class_name = self.read(0x0004)
        self.V_dot, self.A_dot, self.W_dot = self._parse_dot_info()
        self.protection_states = self._read_protection_state()
        self.V(0)

    def _parse_dot_info(self):
        dot_msg = self.read(0x0005)
        W_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        A_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        V_dot = 10 ** (dot_msg & 0x0F)
        return V_dot, A_dot, W_dot

    def _read_protection_state(self):
        protection_state_int = self.read(0x0002)
        return {
            'OVP': protection_state_int & 0x01,
            'OCP': (protection_state_int & 0x02) >> 1,
            'OPP': (protection_state_int & 0x04) >> 2,
            'OTP': (protection_state_int & 0x08) >> 3,
            'SCP': (protection_state_int & 0x10) >> 4
        }

    def read(self, reg_addr: int, reg_len: int = 1):
        """读取寄存器"""
        if reg_len <= 1:
            return self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)[0]
        elif reg_len >= 2:
            raw_tuple = self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)
            return raw_tuple[0] << 16 | raw_tuple[1]

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        """写入数据"""
        if data_len <= 1:
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data)
            return self.read(reg_addr) == data
        elif data_len >= 2:
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data >> 16)
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr + 1, output_value=data & 0xFFFF)
            return self.read(reg_addr) == (data >> 16) and self.read(reg_addr + 1) == (data & 0xFFFF)

    def V(self, V_input: float = None):
        """读取或设置电压"""
        if V_input is None:
            return self.read(0x0010) / self.V_dot
        else:
            self.write(0x0030, int(V_input * self.V_dot + 0.5))
            return self.read(0x0030) / self.V_dot

    def A(self, A_input: float = None):
        """读取或设置电流"""
        if A_input is None:
            return self.read(0x0011) / self.A_dot
        else:
            self.write(0x0031, int(A_input * self.A_dot + 0.5))
            return self.read(0x0031) / self.A_dot

    def W(self):
        """读取功率"""
        return self.read(0x0012, 2) / self.W_dot

    def set_volt(self, V_input, error_range: float = 0.4, timeout: int = 600):
        """设置电压并等待调整完成"""
        old_volt = self.V()
        self.V(V_input)
        start_time = time.time()
        while abs(self.V() - V_input) > error_range:
            if (time.time() - start_time) > timeout:
                raise ValueError("电压设置超时")
        print(f"电压从 {old_volt} V 变至 {self.V()} V，用时 {time.time() - start_time} 秒")

    def operative_mode(self, mode_input: int = None):
        """读取或设置工作模式"""
        if mode_input is None:
            return self.read(0x0001)
        else:
            self.write(0x0001, mode_input)
            return self.read(0x0001)


def save_data_to_disk(file, data):
    """保存数据到磁盘"""
    timestamp = time.strftime("%Y%m%d%H%M%S")
    file.write(f"{timestamp},{data}\n")


def constant_pressure(set_time, v, df, filename ,power_supply):
    """恒电位阳极氧化"""
    power_supply.set_volt(v)
    print(f"开始以 {v}V 电压，电解 {set_time} 秒")
    start_time = time.time()
    end_time = start_time + set_time
    while time.time() < end_time:
        data = [power_supply.V(), power_supply.A(), power_supply.W()]
        df.loc[len(df)] = data
        save_data_to_disk(open(filename, "a"), data)
        sleep(1)
    print(f"本次程序用时 {time.time() - start_time} 秒")


def variable_pressure(set_time, final_v, df, filename , power_supply):
    """电压线性变化阳极氧化"""
    init_v = power_supply.V()
    speed_v = (final_v - init_v) / set_time
    print(f"电压从 {init_v}V 到 {final_v}V 变化，持续 {set_time} 秒")
    start_time = time.time()
    end_time = start_time + set_time
    while time.time() < end_time:
        new_v = init_v + speed_v * (time.time() - start_time)
        power_supply.set_volt(new_v)
        data = [power_supply.V(), power_supply.A(), power_supply.W()]
        df.loc[len(df)] = data
        save_data_to_disk(open(filename, "a"), data)
        sleep(1)
    print(f"本次程序用时 {time.time() - start_time} 秒")


def TiO2_nanotubes_anodic_oxidation(df, filename,power_supply):
    """TiO2纳米管阳极氧化实验"""
    start_time = time.time()

    # 阶段一：30V -> 30V , 0 V/s ,100s
    print("阶段一开始...")
    for i in range(3):
        constant_pressure(100, 30, df, filename, power_supply)
        variable_pressure(300, 0, df, filename, power_supply)
    print("阶段一结束...")

    # 阶段二：0V -> 0V , 0 V/s , 300s
    print("阶段二开始...")
    variable_pressure(500, 50, df, filename, power_supply)
    print("阶段二结束...")

    # 阶段三：0V -> 50V，0.1V/s，500s
    print("阶段三开始...")
    variable_pressure(500, 50, df, filename ,power_supply )
    constant_pressure(2 * 60 * 60, 50, df, filename, power_supply)
    print("阶段三结束...")


    end_time = time.time()
    print(f"总实验时间：{end_time - start_time} 秒")


if __name__ == "__main__":
    # 电源初始化
    eTM_3020C = PowerSupply(connect_serial("COM4", 9600), 1)
    eTM_3020C.operative_mode(1)
    eTM_3020C.set_volt(0)

    # 结果保存
    df = pd.DataFrame(columns=["Voltage (V)", "Current (A)", "Power (W)"])
    filename = "../data.csv"

    # 阳极氧化实验
    TiO2_nanotubes_anodic_oxidation(df, filename , eTM_3020C)
