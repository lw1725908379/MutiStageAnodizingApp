import csv
import logging
from tqdm import tqdm  # 导入 tqdm 以显示进度条
from stage_manager import StageManager
from serial_manager import SerialManager
from storage_manager import StorageManager
from data_collector import DataCollector
from experiment_controller import ExperimentController
from control_strategy import FeedforwardWithFeedbackStrategy
import os
import threading

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_experiment_parameters(file_path):
    """Load experiment parameters from the CSV file."""
    try:
        with open(file_path, mode='r') as file:
            reader = csv.DictReader(file)
            parameters = [row for row in reader]
            logging.info(f"Loaded {len(parameters)} experiment configurations from {file_path}.")
            return parameters
    except Exception as e:
        logging.error(f"Failed to load experiment parameters: {e}")
        return []

def execute_experiment(parameter, serial_manager, stage_manager, storage_manager, data_collector):
    try:
        voltage_start = float(parameter["voltage_start"])
        voltage_end = float(parameter["voltage_end"])
        time_duration = float(parameter["time_duration"])
        kp = float(parameter["Kp"])
        sampling_rate = int(parameter["Sampling Rate (Hz)"])

        # 确保时间为正值
        if time_duration <= 0:
            logging.warning(f"Invalid time_duration ({time_duration}) detected. Adjusting to minimum 1.0 second.")
            time_duration = 1.0

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

        logging.info(f"Starting experiment: {parameter}")
        experiment_controller.start_experiment(sample_rate=sampling_rate)
        experiment_controller.monitor_experiment()

        # 确认数据是否保存
        if not storage_manager.is_data_saved():
            logging.error(f"Data not saved for experiment: {parameter}")
        else:
            logging.info("Data successfully saved.")

    except Exception as e:
        logging.error(f"Error executing experiment: {e}")

def main():
    # 定义文件路径
    parameter_file = "./experiment_parameters.csv"
    result_path = "E:/WORKS/py/projects/MultiStageAnodizingApp/test/MutiStageAnodizingApp_V1/test_datas/experiment_results"

    # 确保结果存储路径存在
    if not os.path.exists(result_path):
        try:
            os.makedirs(result_path)
            logging.info(f"Created result path: {result_path}")
        except Exception as e:
            logging.error(f"Failed to create result path: {e}")
            exit(1)

    # 加载实验参数
    parameters = load_experiment_parameters(parameter_file)

    # 初始化 SerialManager 并连接到电源设备
    serial_manager = SerialManager()
    available_ports = serial_manager.get_serial_ports()
    if not available_ports:
        logging.error("No available serial ports found.")
        exit(1)

    # 尝试连接到第一个可用串口
    connected, message = serial_manager.connect(port=available_ports[0], addr=1)
    if not connected:
        logging.error(f"Failed to connect to serial port: {message}")
        exit(1)

    # 初始化实验组件
    stage_manager = StageManager()
    storage_manager = StorageManager(result_path)
    success, message = storage_manager.initialize_storage()
    if not success:
        logging.error(f"Failed to initialize storage manager: {message}")
        exit(1)

    data_collector = DataCollector(serial_manager.power_supply, storage_manager, None)

    # 遍历并执行所有实验
    batch_size = 10  # 设置每个批次处理的实验数
    total_batches = len(parameters) // batch_size + (1 if len(parameters) % batch_size > 0 else 0)

    for batch_start in range(0, len(parameters), batch_size):
        batch_end = min(batch_start + batch_size, len(parameters))
        logging.info(f"Executing batch {batch_start // batch_size + 1}/{total_batches}: Experiments {batch_start + 1} to {batch_end}")

        # 在当前批次中添加进度条
        for idx, parameter in enumerate(tqdm(parameters[batch_start:batch_end], desc=f"Batch {batch_start // batch_size + 1}/{total_batches}"), start=1):
            logging.info(f"Executing experiment {batch_start + idx}/{len(parameters)} in batch {batch_start // batch_size + 1}")
            execute_experiment(parameter, serial_manager, stage_manager, storage_manager, data_collector)

        logging.info(f"Batch {batch_start // batch_size + 1} completed.")

    # 完成所有实验后清理资源
    data_collector.close()
    storage_manager.close_storage()
    serial_manager.disconnect()
    logging.info("All experiments completed.")

if __name__ == "__main__":
    main()
