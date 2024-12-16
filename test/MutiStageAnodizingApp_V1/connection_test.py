import modbus_tk.modbus_rtu as modbus_rtu
import modbus_tk.defines as cst
import serial
import logging

# 设置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def test_connection(port, baudrate, timeout, addr):
    """
    测试串口连接和读取寄存器
    :param port: 串口端口，例如 "COM5"
    :param baudrate: 波特率，例如 9600
    :param timeout: 超时时间（秒）
    :param addr: 从站地址
    """
    try:
        # 打开串口
        serial_obj = serial.Serial(port, baudrate, timeout=timeout)
        logging.info(f"尝试连接到串口 {port}，波特率: {baudrate}, 超时时间: {timeout}秒")

        # 检查串口是否成功打开
        if serial_obj.is_open:
            logging.info(f"串口 {port} 已成功打开")
        else:
            logging.error(f"无法打开串口 {port}")
            return

        # 初始化Modbus RTU主站
        client = modbus_rtu.RtuMaster(serial_obj)
        client.set_timeout(timeout)
        client.set_verbose(True)

        # 打印RtuMaster的属性以确认是否包含connect方法
        logging.debug(f"RtuMaster的属性: {dir(client)}")

        # 连接Modbus客户端（使用open方法）
        client.open()
        logging.info(f"成功连接到Modbus客户端，端口: {port}")

        # 读取设备名称寄存器（假设地址为0x0003）
        logging.info(f"尝试读取从站地址 {addr} 的寄存器 0x0003")
        name = client.execute(addr, cst.READ_HOLDING_REGISTERS, 0x0003, 1)
        logging.info(f"设备名称寄存器值: {name}")

        # 关闭Modbus客户端连接
        client.close()
        logging.info("已关闭Modbus客户端连接")
    except Exception as e:
        logging.error(f"连接失败: {e}")


if __name__ == "__main__":
    # 请根据实际情况修改端口号、波特率和从站地址
    test_connection("COM5", 9600, 1, 1)
