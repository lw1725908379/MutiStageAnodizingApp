import time
import serial
import serial.tools.list_ports
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from time import sleep


def connect_serial(keyword: str = "", baud_rate: int = 9600, timeout: int = 1):
    """
    连接串口
    :param keyword: 串口名关键词
    :param baud_rate: 波特率
    :param timeout: 超时时间
    :return: 串口类
    """
    serial_list = list(serial.tools.list_ports.comports())
    if not serial_list:
        raise ValueError("Can't find a serial port")

    # 默认自动选择
    if not keyword:
        print("找到如下串口：")
        for serial_port in serial_list:
            print(f"\t{serial_port}")
        keyword = input("请输入要连接的串口关键词：")

    if not baud_rate:
        baud_rate = input("请输入使用的波特率：")
        try:
            baud_rate = int(baud_rate)
        except ValueError:
            baud_rate = 9600  # 默认波特率

    for serial_port in serial_list:
        if keyword.lower() in serial_port.description.lower():
            connection = serial.Serial(serial_port.device, baud_rate, timeout=timeout)
            print(f"与 {serial_port} 建立连接！")
            return connection
    raise ValueError("Can't find the serial port")


class PowerSupply:
    """
    电源类，支持Modbus RTU通信
    """
    def __init__(self, serial_obj: serial.Serial, addr: int):
        """
        构造函数
        :param serial_obj: 串口实例
        :param addr: 从机地址
        """
        self.modbus_rtu_obj = modbus_rtu.RtuMaster(serial_obj)
        self.modbus_rtu_obj.set_timeout(1.0)
        self.addr = addr
        self.name = self.read(0x0003)
        self.class_name = self.read(0x0004)
        self._initialize_dots()
        self._initialize_protection_states()

    def _initialize_dots(self):
        """ 初始化点数系数（电压、电流、功率） """
        dot_msg = self.read(0x0005)
        self.W_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.A_dot = 10 ** (dot_msg & 0x0F)
        dot_msg >>= 4
        self.V_dot = 10 ** (dot_msg & 0x0F)

    def _initialize_protection_states(self):
        """ 初始化保护状态 """
        protection_state_int = self.read(0x0002)
        self.isOVP = protection_state_int & 0x01
        self.isOCP = (protection_state_int & 0x02) >> 1
        self.isOPP = (protection_state_int & 0x04) >> 2
        self.isOTP = (protection_state_int & 0x08) >> 3
        self.isSCP = (protection_state_int & 0x10) >> 4

    def read(self, reg_addr: int, reg_len: int = 1):
        """
        读取寄存器
        :param reg_addr: 寄存器地址
        :param reg_len: 寄存器个数
        :return: 读取的数据
        """
        if reg_len == 1:
            return self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)[0]
        elif reg_len == 2:
            raw_tuple = self.modbus_rtu_obj.execute(self.addr, cst.READ_HOLDING_REGISTERS, reg_addr, reg_len)
            return raw_tuple[0] << 16 | raw_tuple[1]

    def write(self, reg_addr: int, data: int, data_len: int = 1):
        """
        写入数据到寄存器
        :param reg_addr: 寄存器地址
        :param data: 待写入的数据
        :param data_len: 数据长度
        :return: 是否写入成功
        """
        if data_len == 1:
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data)
            return self.read(reg_addr) == data
        elif data_len == 2:
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr, output_value=data >> 16)
            self.modbus_rtu_obj.execute(self.addr, cst.WRITE_SINGLE_REGISTER, reg_addr + 1, output_value=data & 0xFFFF)
            return (self.read(reg_addr) == (data >> 16)) and (self.read(reg_addr + 1) == (data & 0xFFFF))

    def set_volt(self, V_input: float, error_range: float = 0.05, timeout: int = 10):
        """
        设置目标电压
        :param V_input: 目标电压
        :param error_range: 电压误差范围
        :param timeout: 超时时间
        :return: 实际设置电压
        """
        self.write(0x0030, int(V_input * self.V_dot + 0.5))
        target_V = V_input
        start_time = time.time()
        while abs(self.V() - target_V) >= error_range:
            if time.time() - start_time > timeout:
                print("设置目标电压失败，超时退出！")
                break
            sleep(1)
        return self.V()

    def V(self):
        """ 读取或设置电压 """
        return self.read(0x0010) / self.V_dot

    def A(self):
        """ 读取或设置电流 """
        return self.read(0x0011) / self.A_dot

    def W(self):
        """ 读取功率 """
        return self.read(0x0012, 2) / self.W_dot


def constant_pressure(supply: PowerSupply, target_V: float, run_time: float, save_path: str = 'experiment_data.csv', sample_interval: float = 5):
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
    serial_obj = connect_serial(keyword="COM4", baud_rate=9600)  # 可根据需要修改
    psu = PowerSupply(serial_obj, addr=1)  # 创建电源实例
    constant_pressure(psu, target_V=5.0, run_time=60)  # 进行恒压测试
