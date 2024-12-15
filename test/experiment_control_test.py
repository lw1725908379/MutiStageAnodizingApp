import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time
import threading
import numpy as np
import csv
import os
from datetime import datetime


# Configuration class, centralized management of all constants
class Config:
    DEFAULT_SAMPLE_RATE = 10  # 10Hz


class ExperimentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Experiment Control Panel")

        # Initialize serial connection objects (here simulated)
        self.stages = []

        # Serial port selection UI (not functional for testing)
        self.label_serial = tk.Label(root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5)

        self.serial_ports = ["COM1", "COM2", "COM3"]  # Simulated serial ports
        self.combo_serial = ttk.Combobox(root, values=self.serial_ports)
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5)
        self.combo_serial.set("COM1")  # Default selection

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
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))  # Default value: 10 Hz

        # Path selection for data storage
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

        # Plot area (to display real-time data)
        self.fig, self.ax = plt.subplots(figsize=(5, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.set_title("Real-time Experiment Data")
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().grid(row=8, column=0, columnspan=3, padx=5, pady=5)

    def browse_storage_path(self):
        """Opens a file dialog to choose the storage location"""
        folder = filedialog.askdirectory()
        if folder:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder)

    def add_stage(self):
        """Adds a new stage to the experiment"""
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())
            sample_rate = float(self.entry_sample_rate.get())

            self.stages.append({
                'voltage_start': voltage_start,
                'voltage_end': voltage_end,
                'time_duration': time_duration,
                'sample_rate': sample_rate,
            })
            messagebox.showinfo("Success", "Stage added successfully!")
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numerical values.")

    def start_experiment(self):
        """Starts the experiment in a separate thread to avoid freezing the GUI"""
        if not self.stages:
            messagebox.showerror("No Stages", "Please add at least one stage before starting.")
            return

        # Start the simulated experiment in a separate thread
        experiment_thread = threading.Thread(target=self.run_experiment)
        experiment_thread.start()

    def run_experiment(self):
        """Simulates the experiment logic with fake data"""
        for stage in self.stages:
            voltage_start = stage['voltage_start']
            voltage_end = stage['voltage_end']
            time_duration = stage['time_duration']
            sample_rate = stage['sample_rate']

            num_samples = int(time_duration * sample_rate)
            voltage_values = np.linspace(voltage_start, voltage_end, num_samples)
            current_values = np.random.uniform(0.1, 1.0, num_samples)  # Random current values for testing

            # Update the plot with the simulated data
            for i in range(num_samples):
                # Simulate data update
                self.ax.clear()
                self.ax.plot(np.linspace(0, time_duration, num_samples), voltage_values, label="Voltage (V)")
                self.ax.plot(np.linspace(0, time_duration, num_samples), current_values, label="Current (A)")
                self.ax.set_xlabel("Time (s)")
                self.ax.set_ylabel("Current (A)")
                self.ax.set_title("Experiment Data")
                self.ax.legend()

                # Redraw the canvas
                self.canvas.draw()

                # Simulate a time delay based on the sampling rate
                time.sleep(1 / sample_rate)

            # Optionally save the simulated data to a CSV file
            self.save_data(voltage_values, current_values)

    def save_data(self, voltage_values, current_values):
        """Saves the simulated data to a CSV file"""
        folder = self.entry_storage_path.get()
        if not folder:
            messagebox.showerror("Storage Path", "Please specify a storage path.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"simulated_experiment_data_{timestamp}.csv"
        filepath = os.path.join(folder, filename)

        # Write simulated data to CSV file
        with open(filepath, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Time (s)", "Voltage (V)", "Current (A)"])

            for i, voltage in enumerate(voltage_values):
                writer.writerow([i / len(voltage_values), voltage, current_values[i]])

        messagebox.showinfo("Data Saved", f"Simulated data saved to {filepath}")


# Create the root Tkinter window
root = tk.Tk()
app = ExperimentGUI(root)
root.mainloop()
