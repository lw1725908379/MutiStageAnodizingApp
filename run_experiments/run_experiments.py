import csv
import logging
import os
import threading
from datetime import datetime
from tqdm import tqdm  # 导入 tqdm 以显示进度条
from stage_manager import StageManager
from serial_manager import SerialManager
from storage_manager import StorageManager
from data_collector import DataCollector
from experiment_controller import ExperimentController
from control_strategy import FeedforwardWithFeedbackStrategy

# 设置全局日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_experiment_parameters(file_path):
    """
    从 CSV 文件加载实验参数，并记录每个参数的行号。

    返回一个列表，每个元素是一个字典，包含参数和对应的行号。
    """
    parameters = []
    try:
        with open(file_path, mode='r', newline='') as file:
            reader = csv.DictReader(file)
            for line_num, row in enumerate(reader, start=2):  # 假设第一行为表头，从第二行开始
                row['line_num'] = line_num
                parameters.append(row)
        logging.info(f"从 {file_path} 加载了 {len(parameters)} 个实验配置。")
    except Exception as e:
        logging.error(f"加载实验参数失败: {e}")
    return parameters


def initialize_serial_manager():
    """
    初始化 SerialManager 并连接到电源设备。

    返回已连接的 SerialManager 实例，如果连接失败则返回 None。
    """
    serial_manager = SerialManager()
    available_ports = serial_manager.get_serial_ports()
    if not available_ports:
        logging.error("未找到可用的串口。")
        return None

    # 尝试连接到第一个可用串口
    connected, message = serial_manager.connect(port=available_ports[0], addr=1)
    if not connected:
        logging.error(f"连接到串口失败: {message}")
        return None

    logging.info(f"成功连接到串口: {available_ports[0]}")
    return serial_manager


def create_experiment_folder(base_path, experiment_id):
    """
    创建独立的实验结果文件夹，文件夹名称包含实验编号和时间戳。

    返回创建的文件夹路径。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_folder = os.path.join(base_path, f"experiment_{experiment_id}_{timestamp}")
    os.makedirs(experiment_folder, exist_ok=True)
    logging.info(f"为实验 {experiment_id} 创建文件夹: {experiment_folder}")
    return experiment_folder


def setup_logger(experiment_folder, experiment_id):
    """
    为每个实验设置独立的日志记录器。

    返回设置好的日志记录器。
    """
    logger = logging.getLogger(f"Experiment_{experiment_id}")
    logger.setLevel(logging.INFO)

    # 创建文件处理器
    log_file = os.path.join(experiment_folder, f"experiment_{experiment_id}.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # 创建格式器并添加到处理器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    # 防止重复添加处理器
    if not logger.handlers:
        logger.addHandler(fh)

    return logger


def save_experiment_result(experiment_folder, experiment_id, parameter, result_data):
    """
    将实验结果保存到独立的 CSV 文件中。
    """
    result_file = os.path.join(experiment_folder, f"result_{experiment_id}.csv")
    fieldnames = list(parameter.keys()) + list(result_data.keys())

    try:
        with open(result_file, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            combined_data = {**parameter, **result_data}
            writer.writerow(combined_data)
        logging.info(f"实验 {experiment_id} 的结果已保存到 {result_file}")
    except Exception as e:
        logging.error(f"保存实验 {experiment_id} 结果失败: {e}")


def execute_experiment(parameter, serial_manager, stage_manager, base_result_path):
    """
    执行单个实验并将数据保存到独立的文件夹中。

    参数：
        parameter (dict): 实验参数，包括 'line_num' 作为实验编号。
    """
    experiment_id = parameter.get('line_num', 'unknown')-1
    # 为每个实验设置独立的日志记录器
    experiment_folder = create_experiment_folder(base_result_path, experiment_id)
    logger = setup_logger(experiment_folder, experiment_id)

    try:
        voltage_start = float(parameter["voltage_start"])
        voltage_end = float(parameter["voltage_end"])
        time_duration = float(parameter["time_duration"])
        kp = float(parameter["Kp"])
        sampling_rate = int(parameter["Sampling Rate (Hz)"])

        # 确保时间为正值
        if time_duration <= 0:
            logger.warning(f"检测到无效的 time_duration ({time_duration})。调整为最小值 1.0 秒。")
            time_duration = 1.0

        # 初始化 StorageManager 为当前实验
        storage_manager = StorageManager(experiment_folder)
        success, message = storage_manager.initialize_storage()
        if not success:
            logger.error(f"初始化 StorageManager 失败: {message}")
            return

        # 初始化 DataCollector 为当前实验
        data_collector = DataCollector(serial_manager.power_supply, storage_manager, None)

        # 清空 StageManager 的阶段列表
        stage_manager.stages.clear()  # 清空所有阶段

        # 添加实验阶段
        stage_manager.add_stage(voltage_start, voltage_end, time_duration)

        # 初始化控制策略
        control_strategy = FeedforwardWithFeedbackStrategy(Kp=kp, output_limits=(0, 50))

        # 初始化实验控制器
        experiment_controller = ExperimentController(
            serial_manager=serial_manager,
            stage_manager=stage_manager,
            storage_manager=storage_manager,
            data_collector=data_collector,
            plot_window=None,
            plot_stop_event=threading.Event(),
            storage_stop_event=threading.Event(),
            experiment_done_event=threading.Event(),
            control_strategy=control_strategy,
            control_mode="Feedforward"
        )

        logger.info(f"开始执行实验 {experiment_id}: {parameter}")
        experiment_controller.start_experiment(sample_rate=sampling_rate)
        experiment_controller.monitor_experiment()

        # 确保实验完成后，数据被保存
        if not storage_manager.is_data_saved():
            logger.error(f"实验 {experiment_id} 的数据未保存。")
        else:
            logger.info(f"实验 {experiment_id} 的数据已成功保存。")

        # 假设 result_data 是从 storage_manager 或其他组件获取的实验结果
        result_data = {
            "status": "Success",
            "duration": time_duration,
            "timestamp": datetime.now().isoformat()
        }

        # 保存实验结果到独立文件
        save_experiment_result(experiment_folder, experiment_id, parameter, result_data)

        # 确保实验结束后电压被置为零
        serial_manager.power_supply.set_voltage(0)
        logger.info(f"实验 {experiment_id} 完成，电压已被重置为零。")

        # 清理当前实验的资源
        data_collector.close()
        storage_manager.close_storage()
        logger.info(f"实验 {experiment_id} 资源已清理。")

    except Exception as e:
        logger.error(f"执行实验 {experiment_id} 时出错: {e}")




def main():
    # 定义文件路径
    parameter_file = "./experiment_parameters.csv"
    base_result_path = "./experiment_results"

    # 确保结果存储路径存在
    if not os.path.exists(base_result_path):
        try:
            os.makedirs(base_result_path)
            logging.info(f"已创建结果路径: {base_result_path}")
        except Exception as e:
            logging.error(f"创建结果路径失败: {e}")
            exit(1)

    # 加载实验参数
    parameters = load_experiment_parameters(parameter_file)
    if not parameters:
        logging.error("没有加载到任何实验参数。退出程序。")
        exit(1)

    # 初始化 SerialManager 并连接到电源设备
    serial_manager = initialize_serial_manager()
    if not serial_manager:
        logging.error("SerialManager 初始化失败。退出程序。")
        exit(1)

    # 初始化 StageManager
    stage_manager = StageManager()

    # 遍历并执行所有实验
    total_experiments = len(parameters)
    logging.info(f"开始执行 {total_experiments} 个实验。")

    # 使用 tqdm 显示总体进度条
    for parameter in tqdm(parameters, desc="执行实验"):
        execute_experiment(parameter, serial_manager, stage_manager, base_result_path)

    # 完成所有实验后清理资源
    serial_manager.disconnect()
    logging.info("所有实验已完成。")


if __name__ == "__main__":
    main()
