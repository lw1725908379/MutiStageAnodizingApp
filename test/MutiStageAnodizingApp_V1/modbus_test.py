import logging
from pymodbus.client.sync import ModbusSerialClient
import serial.tools.list_ports
import time
import threading

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("modbus_continuous_test.log"),
        logging.StreamHandler()
    ]
)

# 配置类，集中管理所有常量
class Config:
    # 串口通信配置
    BAUD_RATE = 9600
    PARITY = 'N'  # 'N' - None, 'E' - Even, 'O' - Odd
    STOPBITS = 1
    BYTESIZE = 8
    TIMEOUT = 1  # 秒

    # Modbus从站地址
    SLAVE_ADDR = 1

    # 电源寄存器地址
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

def list_serial_ports():
    """列出所有可用的串口。"""
    ports = serial.tools.list_ports.comports()
    available_ports = [port.device for port in ports]
    if not available_ports:
        logging.error("未找到可用的串口。请检查设备连接。")
    else:
        logging.info("可用的串口:")
        for idx, port in enumerate(available_ports, start=1):
            logging.info(f"{idx}: {port}")
    return available_ports

def get_user_port_choice(available_ports):
    """让用户选择一个串口。"""
    if not available_ports:
        return None
    print("\n请选择一个串口进行测试:")
    for idx, port in enumerate(available_ports, start=1):
        print(f"{idx}: {port}")
    while True:
        try:
            choice = int(input("输入串口编号 (例如 1): "))
            if 1 <= choice <= len(available_ports):
                return available_ports[choice - 1]
            else:
                print(f"请输入1到{len(available_ports)}之间的数字。")
        except ValueError:
            print("无效输入，请输入数字。")

def read_registers(client, reg_addr, count=1):
    """读取寄存器并返回结果。"""
    try:
        response = client.read_holding_registers(reg_addr, count, unit=Config.SLAVE_ADDR)
        if not response.isError():
            return response.registers
        else:
            logging.error(f"读取寄存器 {reg_addr} 时出错: {response}")
            return None
    except Exception as e:
        logging.exception(f"读取寄存器 {reg_addr} 时发生异常: {e}")
        return None

def write_register(client, reg_addr, value):
    """写入寄存器并返回状态。"""
    try:
        response = client.write_register(reg_addr, value, unit=Config.SLAVE_ADDR)
        if not response.isError():
            logging.info(f"成功写入寄存器 {reg_addr} 值: {value}")
            return True
        else:
            logging.error(f"写入寄存器 {reg_addr} 时出错: {response}")
            return False
    except Exception as e:
        logging.exception(f"写入寄存器 {reg_addr} 时发生异常: {e}")
        return False

def continuous_communication(client, interval=5):
    """持续与电源通信，定期读取和写入寄存器。"""
    try:
        while True:
            # 读取设备名称
            name_regs = read_registers(client, Config.REG_NAME, 1)
            if name_regs:
                device_name = name_regs[0]
                logging.info(f"设备名称寄存器值: {device_name}")

            # 读取电压
            voltage_regs = read_registers(client, Config.REG_VOLTAGE, 1)
            if voltage_regs:
                voltage_value = voltage_regs[0] / 10.0  # 根据实际情况调整缩放因子
                logging.info(f"读取到的电压: {voltage_value} V (原始值: {voltage_regs[0]})")

            # 读取电流
            current_regs = read_registers(client, Config.REG_CURRENT, 1)
            if current_regs:
                current_value = current_regs[0] / 10.0  # 根据实际情况调整缩放因子
                logging.info(f"读取到的电流: {current_value} A (原始值: {current_regs[0]})")

            # 读取保护状态
            protection_regs = read_registers(client, Config.REG_PROTECTION_STATE, 1)
            if protection_regs:
                protection_state = protection_regs[0]
                logging.info(f"保护状态寄存器值: {protection_state:#04x}")
                # 解析保护状态
                protection_flags = {
                    'OVP': bool(protection_state & Config.OVP),
                    'OCP': bool((protection_state & Config.OCP) >> 1),
                    'OPP': bool((protection_state & Config.OPP) >> 2),
                    'OTP': bool((protection_state & Config.OTP) >> 3),
                    'SCP': bool((protection_state & Config.SCP) >> 4),
                }
                logging.info("保护状态解析:")
                for key, value in protection_flags.items():
                    logging.info(f"  {key}: {'ON' if value else 'OFF'}")

            # 示例：设置电压为5.0V（仅在需要时启用）
            # set_voltage = 5.0
            # voltage_set_register = int(set_voltage * 10)  # 根据实际情况调整缩放因子
            # if write_register(client, Config.REG_VOLTAGE_SET, voltage_set_register):
            #     # 确认设置后的电压
            #     time.sleep(1)  # 等待设备响应
            #     voltage_confirm_regs = read_registers(client, Config.REG_VOLTAGE_SET, 1)
            #     if voltage_confirm_regs:
            #         voltage_set_value = voltage_confirm_regs[0] / 10.0
            #         logging.info(f"确认设置后的电压: {voltage_set_value} V")

            # 等待下一个周期
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("检测到键盘中断，停止持续通信。")
    except Exception as e:
        logging.exception(f"持续通信过程中发生异常: {e}")

def main():
    print("=== Modbus 持续串口通信测试脚本 ===\n")

    # 列出可用的串口
    available_ports = list_serial_ports()
    if not available_ports:
        print("没有可用的串口。请检查设备连接后重试。")
        return

    # 让用户选择串口
    selected_port = get_user_port_choice(available_ports)
    if not selected_port:
        print("未选择串口，退出。")
        return

    print(f"\n选择的串口: {selected_port}")

    # 验证Config类是否包含必要的属性
    required_attributes = ['OVP', 'OCP', 'OPP', 'OTP', 'SCP']
    missing_attributes = [attr for attr in required_attributes if not hasattr(Config, attr)]
    if missing_attributes:
        logging.error(f"Config类中缺少以下属性: {missing_attributes}")
        return
    else:
        logging.debug("Config类中包含所有必要的保护状态属性。")

    # 初始化Modbus客户端
    client = ModbusSerialClient(
        method='rtu',
        port=selected_port,
        baudrate=Config.BAUD_RATE,
        parity=Config.PARITY,
        stopbits=Config.STOPBITS,
        bytesize=Config.BYTESIZE,
        timeout=Config.TIMEOUT
    )

    # 尝试连接
    if not client.connect():
        logging.error(f"无法连接到串口 {selected_port}。请检查串口设置和设备状态。")
        return
    logging.info(f"成功连接到串口 {selected_port}。开始持续通信测试。")

    try:
        # 启动持续通信
        continuous_communication(client, interval=5)  # 每5秒一次
    finally:
        # 关闭连接
        client.close()
        logging.info("已关闭串口连接。")

if __name__ == "__main__":
    main()
