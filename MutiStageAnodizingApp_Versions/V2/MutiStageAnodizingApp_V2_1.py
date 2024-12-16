import time
import serial
import serial.tools.list_ports
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import schedule
import time
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
            return self.read(0x9999)

    # timeout = 60
    def set_volt(self, V_input, error_range: int = 0.4, timeout: int = 600):
        """
        设置目标电压，等待转换完成并测量响应时间
        :param V_input: 目标电压，单位：伏特
        :param error_range: 容许的误差大小
        :param timeout: 超时时间
        :return:
        """
        old_volt = self.V()
        self.V(V_input)
        start_time = time.time()
        while abs(self.V() - V_input) > error_range:
            if (time.time() - start_time) > timeout:
                raise ValueError("Set volt timeout")
        print("从", old_volt, "V跳至", self.V(), "V, 用时", time.time() - start_time, "秒")

    def operative_mode(self, mode_input: int = None):
        """
        读取或写入工作状态
        :param mode_input: 工作状态，1: 开启输出; 0: 关闭输出
        :return: 当前工作状态
        """
        if mode_input is None:
            return self.read(0x0001)
        else:
            if mode_input:
                self.write(0x0001, 1)
            else:
                self.write(0x0001, 0)
            return self.read(0x0001)


# 定义实时存储数据功能
# file 存入数据文件对象
# data 数据
def save_data_to_disk(file, data):
    timestamp = time.strftime("%Y%m%d%H%M%S")
    file.write(f"{timestamp},{data}\n")


# 恒电位阳极氧化
def constant_pressure(set_time, v, df, filename):
    """
    在指定时间内，以固定电压进行电解过程，并实时记录电压、电流和功率数据。
    :param set_time: int, 设定的电解时间（秒）
    :param v: float, 设定的电解电压（伏特）
    :param df: DataFrame, 用于存储电解过程中收集的数据
    :param filename: str, 用于存储数据的文件名
    """
    eTM_3020C.set_volt(v)  # 将电压上升至v
    print("当前表显电压：", eTM_3020C.V())
    print("开始以", eTM_3020C.V(), "V电压，电解", set_time, "s")
    #  计时开始
    start_time_s = time.perf_counter()
    start_time = time.time()
    # 设定循环的时限（set_time s）
    end_time = time.time() + set_time
    # 开始无限循环
    while True:
        # 任务条
        for i in tqdm(range(1, set_time + 1)):
            # 取样点为1s
            sleep(1)
            # 记录当前取样点电压值、电流值和功率
            data = [eTM_3020C.V(), eTM_3020C.A(), eTM_3020C.W()]
            df.loc[len(df)] = data
            data_str = ','.join(str(j) for j in data)
            with open(filename, "a") as file:
                save_data_to_disk(file, data_str)
        # 判断是否超过了时限
        if time.time() > end_time:
            break
    # 循环结束
    print("本次程序共执行", time.perf_counter() - start_time_s, "s")
    print("当前表显电压：", eTM_3020C.V())
    print("循环结束")


# 时间为s，电压为V 可以实现线性上升或线性下降
def variable_pressure(set_time, final_v, df, filename):
    """
    在指定时间内实现电压的线性变化，并记录过程中的电压、电流和功率数据。
    :param set_time: int, 设定的总时间（秒），指定电压变化从初始值到目标值所需的时间。
    :param final_v: float, 目标电压值（伏特），电压变化结束时应达到的电压。
    :param df: DataFrame, 用于存储每秒采集的电压、电流和功率数据。
    :param filename: str, 指定的数据记录文件名，用于将实验数据写入磁盘。
    """
    print("当前表显电压：", eTM_3020C.V())
    # 初始化电压，获取开始时的电压值
    init_v = eTM_3020C.V()
    final_v = final_v
    # 计算电压变化的速度（每秒变化量）
    speed_v = (final_v - init_v) / set_time
    #   time up
    start_time_s = time.perf_counter()
    start_time = time.time()
    # 设定循环的时限（set_time s）
    end_time = time.time() + set_time
    # 开始无限循环
    while True:
        # 在循环体内执行你想要执行的操作
        # 任务条
        for i in range(1, set_time + 1):
            # 取样点间隔 1s
            sleep(1)
            data = [eTM_3020C.V(), eTM_3020C.A(), eTM_3020C.W()]
            # 将采集到的数据添加到DataFrame中
            df.loc[len(df)] = data
            data_str = ','.join(str(j) for j in data)
            # 将数据写入到指定的文件中
            with open(filename, "a") as file:
                save_data_to_disk(file, data_str)
            eTM_3020C.set_volt(init_v + i * speed_v)
        # 判断是否超过了时限
        if time.time() > end_time:
            break
    # 循环结束
    print("本次程序共执行", time.perf_counter() - start_time_s, "s")
    print("当前表显电压：", eTM_3020C.V())
    print("循环结束")


def e_polish(df, filename):
    for i in range(5):
        print("30 V 恒电位下保持100 s.")
        constant_pressure(100, 20, df, filename)
        print("然后以dE / dt = -100 m V/s 进行阴极扫描。...")
        variable_pressure(200, 0, df, filename)
    # 电压归零
    eTM_3020C.set_volt(0)


def TiO2_nanotubes_anodic_oxidation(df, filename):
    start_time = time.perf_counter()
    # 阶段一：“0V ~ 50V 0.1V/S 500s
    print("阶段一开始...")
    variable_pressure(500, 50, df, filename)
    print("阶段一结束...")
    end_time = time.perf_counter()
    print("本次程序用时", end_time - start_time, "s")
    print("当前表显电压：\n")
    print(eTM_3020C.V())
    print("当前表显电流：\n")
    print(eTM_3020C.A())
    # 阶段二：“50V  2*60*60 2h”
    print("阶段二开始...")
    constant_pressure(4 * 60 * 60, 50, df, filename)
    print("阶段二结束...")
    end_time = time.perf_counter()
    print("本次程序用时", end_time - start_time, "s")
    print("当前表显电压：\n")
    print(eTM_3020C.V())
    print("当前表显电流：\n")
    print(eTM_3020C.A())
    print("当前表显功率：", eTM_3020C.W())
    print("切断串口通信...")
    # 关闭串口通信
    eTM_3020C.operative_mode(0)
    # 电压归零
    eTM_3020C.set_volt(0)


eTM_3020C = power_supply(connect_serial("COM8", 9600), 1)

if __name__ == '__main__':
    # 电源初始化
    # 连接电源

    # 开启串口通信
    eTM_3020C.operative_mode(1)
    # 电压归零
    eTM_3020C.set_volt(0)

    # 初始化dataframe用于存储电解过程电压V，电流A，和功率W
    df = pd.DataFrame(columns=['V', 'A', 'W'])
    current_date = datetime.datetime.now().strftime('%Y%m%d')
    save_path = "D:\\LW\\" + current_date + "\\"
    filename = save_path + "20240625_ao.txt"
    TiO2_nanotubes_anodic_oxidation(df, filename)
    #     e_polish(df,filename)

    #     保存数据
    print(df)

    df.to_csv(save_path + datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + "_result.csv")
    sns.lineplot(data=df, x=np.arange(1, len(df) + 1), y='V')
    plt.savefig(save_path + current_date + "_t_v.pdf")
    plt.show()

    sns.lineplot(data=df, x=np.arange(1, len(df) + 1), y='A')
    plt.savefig(save_path + current_date + "_t_A.pdf")
    plt.show()
    sns.lineplot(data=df, x=np.arange(1, len(df) + 1), y='W')
    plt.savefig(save_path + current_date + "_t_W.pdf")
    plt.show()
