import time
import serial
import serial.tools.list_ports
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import schedule
import numpy as np
import pandas as pd
from time import sleep
from tqdm import tqdm
import seaborn as sns
import matplotlib.pyplot as plt
import datetime


def connect_serial(keyword: str = "", baud_rate: int = None, timeout: int = 1):
    """
    连接串口
    :param keyword: 串口名关键词
    :param baud_rate: 波特率
    :param timeout: 超时时间
    :return: 串口类
    """
    serial_list = list(serial.tools.list_ports.comports())
    serial_list_len = len(serial_list)
    if serial_list_len <= 0:
        raise ValueError("Can't find a serial port")
    else:
        if not keyword:
            print("找到如下串口：")
            for serial_port in serial_list:
                print("\t", str(serial_port))
            print("请输入要连接的串口关键词：")
            keyword = input()
        if not baud_rate:
            print("请输入使用的波特率：")
            baud_rate = input()
            try:
                baud_rate = int(baud_rate)
            except:
                baud_rate = 9600
        for _ in range(serial_list_len):
            if keyword.lower() in str(serial_list[_]).lower():
                serial_port = serial.Serial(serial_list[_].name, baud_rate, timeout=timeout)
                print("与", serial_list[_], "建立连接！")
                return serial_port
        raise ValueError("Can't find the serial port")


class power_supply:
    """
    电源类
    """
    def __init__(self, serial_obj: serial.serialwin32.Serial, addr: int):
        """
        构造函数
        :param serial_obj: 串口类
        :param addr: 从机地址
        """
        self.modbus_rtu_obj = modbus_rtu.RtuMaster(serial_obj)
        self.modbus_rtu_obj.set_timeout(1.0)
        self.addr = addr
        self.name = self.read(0x0003)
        self.class_name = self.read(0x0004)

        dot_msg = self.read(0x0005)
        self.W_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.A_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.V_dot = 10 ** (dot_msg & 0x0F)

        protection_state_int = self.read(0x0002)
        self.isOVP = protection_state_int & 0x01
        self.isOCP = (protection_state_int & 0x02) >> 1
        self.isOPP = (protection_state_int & 0x04) >> 2
        self.isOTP = (protection_state_int & 0x08) >> 3
        self.isSCP = (protection_state_int & 0x10) >> 4

        self.V(0)

    def read(self, reg_addr: int, reg_len: int = 1):
        """
        读取寄存器
        :param reg_addr: 寄存器地址
        :param reg_len: 寄存器个数，1~2
        :return: 数据
        """
        if reg_len <= 1:
            return self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)[0]
        elif reg_len >= 2:
            raw_tuple = self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)
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
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data)
            if self.read(reg_addr) == data:
                return True
            else:
                return False
        elif data_len >= 2:
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data >> 16)
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr + 1, output_value=data & 0xFFFF)
            if self.read(reg_addr) == (data >> 16) and self.read(reg_addr + 1) == (data & 0xFFFF):
                return True
            else:
                return False

    def read_protection_state(self):
        """
        读取保护状态
        :return: 保护状态寄存器原始值
        """
        protection_state_int = self.read(0x0002)
        self.isOVP = protection_state_int & 0x01
        self.isOCP = (protection_state_int & 0x02) >> 1
        self.isOPP = (protection_state_int & 0x04) >> 2
        self.isOTP = (protection_state_int & 0x08) >> 3
        self.isSCP = (protection_state_int & 0x10) >> 4
        return protection_state_int

    def V(self, V_input: float = None):
        """
        读取表显电压或写入目标电压
        :param V_input: 电压值，单位：伏特
        :return: 表显电压或目标电压
        """
        if V_input is None:
            return self.read(0x0010) / self.V_dot
        else:
            self.write(0x0030, int(V_input * self.V_dot + 0.5))
            return self.read(0x0030) / self.V_dot

    def A(self, A_input: float = None):
        """
        读取表显电流或写入限制电流
        :param A_input: 电流值，单位：安
        :return: 表显电流或限制电流
        """
        if A_input is None:
            return self.read(0x0011) / self.A_dot
        else:
            self.write(0x0031, int(A_input * self.A_dot + 0.5))
            return self.read(0x0031) / self.A_dot

    def W(self):
        """
        读取表显功率
        :return: 表显功率，单位：瓦
        """
        return self.read(0x0012, 2) / self.W_dot

    def OVP(self, OVP_input: float = None):
        """
        读取或写入过压保护设定值
        :param OVP_input:过压保护设定值
        :return:过压保护设定值
        """
        if OVP_input is None:
            return self.read(0x0020) / self.V_dot
        else:
            self.write(0x0020, int(OVP_input * self.V_dot + 0.5))
            return self.read(0x0020) / self.V_dot

    def OCP(self, OAP_input: float = None):
        """
        读取或写入过流保护设定值
        :param OAP_input:过流保护设定值
        :return:过流保护设定值
        """
        if OAP_input is None:
            return self.read(0x0021) / self.A_dot
        else:
            self.write(0x0021, int(OAP_input * self.A_dot + 0.5))
            return self.read(0x0021) / self.A_dot

    def OPP(self, OPP_input: float = None):
        """
        读取或写入过功率保护设定值
        :param OPP_input:过功率保护设定值
        :return:过功率保护设定值
        """
        if OPP_input is None:
            return self.read(0x0022, 2) / self.W_dot
        else:
            self.write(0x0022, int(OPP_input * self.W_dot + 0.5), 2)
            return self.read(0x0022, 2) / self.W_dot

    def Addr(self, addr_input: int = None):
        """
        读取或改变从机地址
        :param addr_input: 要设成的从机地址, 1～250
        :return: 从机地址
        """
        if addr_input is None:
            self.addr = self.read(0x9999)
            return self.addr
        else:
            self.write(0x9999, addr_input)
            self.addr = addr_input
            return self.addr

    def set_volt(self, V_input: float, error_range: float = 0.05, timeout: int = 10):
        """
        设置目标电压
        :param V_input:目标电压
        :param error_range: 电压误差范围
        :param timeout: 超时时间，单位：秒
        :return:
        """
        self.V(V_input)
        target_V = V_input
        V_measure = self.V()
        delta_V = abs(target_V - V_measure)
        time_interval = 1
        start_time = time.time()
        while delta_V >= error_range:
            sleep(time_interval)
            V_measure = self.V()
            delta_V = abs(target_V - V_measure)
            if time.time() - start_time > timeout:
                print("设置目标电压失败，超时退出！")
                break
        return V_measure


def constant_pressure(supply: power_supply, target_V: float, run_time: float, save_path: str = 'D:\\LW\\experiment_data.csv', sample_interval: float = 5):
    """
    恒压模式下，输出电压、电流、功率及时间
    :param supply: 电源实例
    :param target_V: 目标电压，单位：V
    :param run_time: 测量运行时间，单位：秒
    :param save_path: 保存路径
    :param sample_interval: 采样间隔，单位：秒
    """
    # 设置目标电压
    print(f'设置目标电压为 {target_V}V')
    supply.set_volt(target_V)

    start_time = time.time()
    data = []
    while time.time() - start_time < run_time:
        elapsed_time = time.time() - start_time
        current_V = supply.V()
        current_A = supply.A()
        current_W = supply.W()

        # 输出实时数据到控制台
        print(f"时间: {elapsed_time:.2f}s, 电压: {current_V:.2f}V, 电流: {current_A:.2f}A, 功率: {current_W:.2f}W")

        data.append([elapsed_time, current_V, current_A, current_W])

        sleep(sample_interval)

    # 将数据保存到CSV文件
    df = pd.DataFrame(data, columns=["时间", "电压", "电流", "功率"])
    df.to_csv(save_path, index=False)

    # 绘制数据图形
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="时间", y="电压", label="电压")
    sns.lineplot(data=df, x="时间", y="电流", label="电流")
    sns.lineplot(data=df, x="时间", y="功率", label="功率")
    plt.legend()
    plt.title(f"恒压模式：{target_V}V, 运行时间：{run_time}s")
    plt.xlabel("时间 (秒)")
    plt.ylabel("测量值")
    plt.tight_layout()
    plt.savefig(save_path.replace(".csv", ".pdf"))
    plt.show()

    print(f"实验数据已保存至 {save_path}")


# 主函数示例
if __name__ == "__main__":
    # 连接串口
    serial_obj = connect_serial(keyword="COM4", baud_rate=9600)

    # 创建电源实例
    psu = power_supply(serial_obj, addr=1)

    # 设置电压并进行恒压模式测试
    constant_pressure(psu, target_V=5.0, run_time=60)
