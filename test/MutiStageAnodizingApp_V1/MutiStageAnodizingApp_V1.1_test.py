import time
import threading
import queue
import csv
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os

# --- Start of Simulation of PowerSupply and Serial Port ---

class SimulatedPowerSupply:
    """
    A simulated version of PowerSupply for testing purposes.
    """
    def __init__(self):
        self.voltage = 0.0
        self.current = 0.0

    def V(self, V_input: float = None):
        """
        Simulate voltage control or reading.
        :param V_input: voltage value, unit: volt
        :return: simulated voltage
        """
        if V_input is None:
            return self.voltage
        else:
            self.voltage = V_input
            return self.voltage

    def A(self, A_input: float = None):
        """
        Simulate current control or reading.
        :param A_input: current value, unit: ampere
        :return: simulated current
        """
        if A_input is None:
            return self.current
        else:
            self.current = A_input
            return self.current

class SimulatedSerial:
    """
    A simulated version of the serial communication for testing purposes.
    """
    def __init__(self, port, baudrate, timeout):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    def close(self):
        pass

# --- End of Simulation of PowerSupply and Serial Port ---

# --- Start of GUI and Experiment Logic ---

class Config:
    BAUD_RATE = 9600
    TIMEOUT = 1
    DEFAULT_SAMPLE_RATE = 10  # 10Hz


class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Experiment Control Panel")

        # Initialize serial connection objects (simulated)
        self.serial_obj = None
        self.power_supply = None  # Placeholder for power supply object
        self.is_experiment_running = False  # Flag to prevent multiple experiments
        self.data_queue = queue.Queue()  # Queue for storing experimental datasets
        self.experiment_done_event = threading.Event()  # Event to signal when experiment is done
        self.stage_done_event = threading.Event()  # Event to signal when stage is done
        self.stages = []  # Initialize stages list

        # Serial port selection UI
        self.label_serial = tk.Label(root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5)

        self.combo_serial = ttk.Combobox(root, values=["COM1", "COM2", "COM3"])
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5)
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)

        # Voltage input fields for start and end values
        self.label_voltage_start = tk.Label(root, text="Initial Voltage (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5)

        self.entry_voltage_start = tk.Entry(root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5)

        self.label_voltage_end = tk.Label(root, text="Termination Voltage (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5)

        self.entry_voltage_end = tk.Entry(root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5)

        # Time duration input field
        self.label_time = tk.Label(root, text="Set Time (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5)

        self.entry_time = tk.Entry(root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5)

        # Sampling frequency input field
        self.label_sample_rate = tk.Label(root, text="Sampling Rate (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5)

        self.entry_sample_rate = tk.Entry(root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5)
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))

        # Path selection for datasets storage
        self.label_storage_path = tk.Label(root, text="Storage Path:")
        self.label_storage_path.grid(row=5, column=0, padx=5, pady=5)

        self.entry_storage_path = tk.Entry(root)
        self.entry_storage_path.grid(row=5, column=1, padx=5, pady=5)

        self.button_browse = tk.Button(root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=5, column=2, padx=5, pady=5)

        # Button to add a new experiment stage
        self.button_add_stage = tk.Button(root, text="Add Stage", command=self.add_stage)
        self.button_add_stage.grid(row=6, column=0, columnspan=2, pady=5)

        # Button to initiate the experiment
        self.button_start = tk.Button(root, text="Start Experiment", command=self.start_experiment)
        self.button_start.grid(row=7, column=0, columnspan=2, pady=5)

    def get_serial_ports(self):
        """Get the list of available serial ports"""
        return ["COM1", "COM2", "COM3"]  # Simulated serial ports

    def set_serial_port(self, event):
        """Set serial port when selected from dropdown"""
        port_name = self.combo_serial.get()
        try:
            # Simulate serial port and power supply
            self.serial_obj = SimulatedSerial(port_name, Config.BAUD_RATE, Config.TIMEOUT)
            self.power_supply = SimulatedPowerSupply()  # Use the simulated power supply
            messagebox.showinfo("Serial Port", f"Successfully connected to {port_name}")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {port_name}: {e}")

    def browse_storage_path(self):
        """Open file dialog to browse for storage path"""
        path = filedialog.askdirectory()
        self.entry_storage_path.delete(0, tk.END)
        self.entry_storage_path.insert(0, path)

    def add_stage(self):
        """Add a new stage to the experiment"""
        voltage_start = float(self.entry_voltage_start.get())
        voltage_end = float(self.entry_voltage_end.get())
        time_duration = float(self.entry_time.get())
        sample_rate = int(self.entry_sample_rate.get())

        stage = {"voltage_start": voltage_start, "voltage_end": voltage_end, "time_duration": time_duration, "sample_rate": sample_rate}
        self.stages.append(stage)  # Add stage to the list

        messagebox.showinfo("Stage Added", f"Stage added: {stage}")

    def start_experiment(self):
        """Start the experiment by processing the stages and saving the results"""
        if self.is_experiment_running:
            messagebox.showwarning("Experiment Running", "Experiment is already running.")
            return

        if not self.stages:
            messagebox.showerror("No Stages", "No stages have been added.")
            return

        # Disable the "Start Experiment" button to prevent multiple clicks
        self.button_start.config(state=tk.DISABLED)
        self.is_experiment_running = True
        self.experiment_done_event.clear()

        # Start the experiment thread
        experiment_thread = threading.Thread(target=self.run_experiment)
        experiment_thread.start()

    def run_experiment(self):
        """Run the experiment and collect datasets"""
        try:
            for stage in self.stages:
                voltage_start = stage["voltage_start"]
                voltage_end = stage["voltage_end"]
                time_duration = stage["time_duration"]
                sample_rate = stage["sample_rate"]

                print(f"Starting stage: {stage}")
                # Simulate voltage increment over time
                voltage_increment = (voltage_end - voltage_start) / time_duration

                for elapsed_time in range(int(time_duration * sample_rate)):
                    voltage = voltage_start + voltage_increment * elapsed_time / sample_rate
                    self.power_supply.V(voltage)

                    # Simulate datasets collection at specified sample rate
                    self.data_queue.put([voltage, 0.0, 0.0])  # Collect simulated datasets (voltage, current, power)
                    time.sleep(1.0 / sample_rate)

                self.stage_done_event.set()  # Signal that the stage is done
                self.stage_done_event.wait()  # Wait for consumer to process datasets before continuing

        finally:
            # Mark the experiment as complete
            self.experiment_done_event.set()
            self.button_start.config(state=tk.NORMAL)  # Re-enable start button
            messagebox.showinfo("Experiment Complete", "Experiment is complete.")

# --- End of GUI and Experiment Logic ---

if __name__ == "__main__":
    root = tk.Tk()
    gui = ExperimentGUI(root)
    root.mainloop()
