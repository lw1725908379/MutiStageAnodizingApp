# experiment_controller.py
import time
import logging
import threading
import math
from queue import Queue
from pid_controller import PIDController  # 导入 PID 控制器

class ExperimentController:
    """Experiment Controller for managing experiment execution."""

    def __init__(self, serial_manager, stage_manager, storage_manager, data_collector, plot_window, plot_stop_event, storage_stop_event, experiment_done_event, Kp=2.0, Ki=5.0, Kd=1.0):
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

        # 初始化 PID 控制器
        self.pid = PIDController(Kp=Kp, Ki=Ki, Kd=Kd, setpoint=0.0, output_limits=(0, 12))  # output_limits 根据硬件调整

    def collect_data_with_sample_rate(self, sample_rate):
        """根据采样率使用 PID 控制进行数据采集。"""
        sample_interval = 1.0 / sample_rate
        logging.info(f"Starting data collection with sample rate: {sample_rate} Hz")

        try:
            for stage_idx, stage in enumerate(self.stage_manager.get_stages(), start=1):
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                duration = stage["time"]

                logging.debug(f"Starting stage {stage_idx} - Start Voltage: {voltage_start} V, End Voltage: {voltage_end} V, Duration: {duration} s")

                # 设置初始电压
                self.serial_manager.power_supply.set_voltage(voltage_start)
                self.pid.set_setpoint(voltage_start)

                start_time = time.perf_counter()
                end_time = start_time + duration

                while time.perf_counter() < end_time:
                    cycle_start = time.perf_counter()

                    # 计算当前阶段的时间比例
                    elapsed_time = time.perf_counter() - start_time
                    voltage_progress = elapsed_time / duration
                    voltage_progress = min(voltage_progress, 1.0)  # 确保不超过 1.0

                    # 计算目标电压（线性升压）
                    target_voltage = voltage_start + voltage_progress * (voltage_end - voltage_start)
                    self.pid.set_setpoint(target_voltage)

                    # 读取当前电压
                    measured_voltage = self.serial_manager.power_supply.get_voltage()
                    if measured_voltage is None:
                        logging.error("Failed to read voltage, skipping this sample.")
                        continue

                    # 更新 PID 输出
                    control_signal = self.pid.update(measured_voltage)

                    # 将 PID 输出用于设置电压
                    self.serial_manager.power_supply.set_voltage(control_signal)

                    # 收集数据
                    self.data_collector.collect_data_for_stage()

                    # 计算下一个采样时间
                    next_sample_time = cycle_start + sample_interval
                    sleep_duration = next_sample_time - time.perf_counter()
                    if sleep_duration > 0:
                        time.sleep(sleep_duration)

                    logging.debug(f"Stage {stage_idx}, Time: {elapsed_time:.2f}s, Target Voltage: {target_voltage:.2f} V, Measured Voltage: {measured_voltage:.2f} V, Control Signal: {control_signal:.2f} V")

                # 确保达到最终电压
                self.serial_manager.power_supply.set_voltage(voltage_end)
                self.data_collector.collect_data_for_stage()

                logging.info(f"Completed data collection for stage {stage_idx}.")

            self.experiment_done_event.set()
            logging.info("Experiment completed.")
        except Exception as e:
            logging.error(f"Error during data collection: {e}")
            self.experiment_done_event.set()

    def start_experiment(self, sample_rate):
        """Start the experiment with the given sample rate."""
        if self.is_experiment_running:
            logging.warning("Attempted to start an experiment, but one is already running.")
            return

        self.is_experiment_running = True
        self.experiment_done_event.clear()

        # PlotWindow 不需要额外调用 start_animation，因为它已在初始化时处理 plot_queue
        logging.info("Plot window started.")

        # Start storage consumer thread
        self.storage_stop_event.clear()
        self.storage_thread = threading.Thread(target=self.storage_consumer, daemon=True)
        self.storage_thread.start()
        logging.info("Storage consumer thread started.")

        # Start data collection thread
        data_thread = threading.Thread(target=self.collect_data_with_sample_rate, args=(sample_rate,), daemon=True)
        data_thread.start()
        logging.info("Data collection thread started.")

    def storage_consumer(self):
        """Storage consumer thread function."""
        while not self.storage_stop_event.is_set():
            time.sleep(0.05)  # Simple wait mechanism; can be optimized if needed

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        self.experiment_done_event.wait()
        logging.info("Experiment completion signal received.")

        self.plot_stop_event.set()
        self.storage_stop_event.set()

        if self.storage_thread is not None:
            self.storage_thread.join()
            logging.info("Storage consumer thread has ended.")

        # Do not disconnect serial here; leave to the GUI's on_closing
        self.is_experiment_running = False
        # GUI will show a message externally
