import pandas as pd
import logging
import time
import os
from experiment_controller import ExperimentController
from serial_manager import SerialManager
from storage_manager import StorageManager
from stage_manager import StageManager
from data_collector import DataCollector
from control_strategy import FeedforwardWithFeedbackStrategy
from threading import Event

# Configuration
EXPERIMENT_FILE = "experiment_combinations.xlsx"
STORAGE_PATH = "./experiment_data"
LOG_FILE = "batch_experiment.log"

# Initialize logging
logging.basicConfig(level=logging.INFO, filename=LOG_FILE, filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

def run_experiment(experiment_params):
    """
    Execute a single experiment based on given parameters.
    """
    try:
        # Extract parameters
        start_voltage = experiment_params["Start Voltage (V)"]
        end_voltage = experiment_params["End Voltage (V)"]
        duration = experiment_params["Duration (s)"]
        sampling_rate = experiment_params["Sampling Rate (Hz)"]
        Kp = experiment_params["Kp"]

        logging.info(f"Starting Experiment: Start={start_voltage}V, End={end_voltage}V, "
                     f"Duration={duration}s, Rate={sampling_rate}Hz, Kp={Kp}")

        # Setup components
        serial_manager = SerialManager()
        serial_manager.connect("COM4")  # Update COM port as needed

        storage_manager = StorageManager(STORAGE_PATH)
        success, message = storage_manager.initialize_storage()
        if not success:
            raise Exception(f"Storage Initialization Failed: {message}")

        stage_manager = StageManager()
        stage_manager.add_stage(start_voltage, end_voltage, duration)

        control_strategy = FeedforwardWithFeedbackStrategy(Kp=Kp)
        plot_stop_event = Event()
        storage_stop_event = Event()
        experiment_done_event = Event()
        plot_window = None  # No GUI required in batch mode

        # Initialize Data Collector
        data_collector = DataCollector(serial_manager.power_supply, storage_manager, plot_queue=None)

        # Start the experiment
        experiment_controller = ExperimentController(
            serial_manager, stage_manager, storage_manager, data_collector,
            plot_window, plot_stop_event, storage_stop_event, experiment_done_event,
            control_strategy, "Feedforward"
        )

        experiment_controller.collect_data_with_sample_rate(sampling_rate)

        # Cleanup
        serial_manager.disconnect()
        data_collector.close()
        storage_manager.close_storage()

        logging.info("Experiment Completed Successfully")

    except Exception as e:
        logging.error(f"Experiment Failed: {str(e)}")


def main():
    # Load experiment combinations
    if not os.path.exists(EXPERIMENT_FILE):
        logging.error("Experiment combinations file not found!")
        return

    experiments = pd.read_excel(EXPERIMENT_FILE, engine="openpyxl")

    logging.info(f"Loaded {len(experiments)} experiments from {EXPERIMENT_FILE}")

    # Create storage path if it doesn't exist
    if not os.path.exists(STORAGE_PATH):
        os.makedirs(STORAGE_PATH)

    # Execute each experiment
    for index, experiment in experiments.iterrows():
        logging.info(f"Running Experiment {index + 1}/{len(experiments)}")
        run_experiment(experiment)

        # Add delay to prevent hardware issues
        time.sleep(2)

if __name__ == "__main__":
    main()
