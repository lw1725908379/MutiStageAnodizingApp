# plot_window.py
import matplotlib
matplotlib.use('TkAgg')  # Ensure using TkAgg backend
import matplotlib.pyplot as plt
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import queue
import logging
import tkinter as tk
from matplotlib.ticker import FuncFormatter

class PlotWindow:
    """Plot Window for real-time data plotting."""

    def __init__(self, master, plot_queue):
        self.master = master
        self.master.title("Real-time Data Plotting")

        # Create Matplotlib figure and axes
        self.fig, (self.ax_voltage, self.ax_current, self.ax_power) = plt.subplots(3, 1, figsize=(8, 6))
        self.fig.tight_layout(pad=3.0)

        # Initialize plot lines
        self.voltage_line, = self.ax_voltage.plot([], [], label='Voltage (V)', color='blue')
        self.current_line, = self.ax_current.plot([], [], label='Current (A)', color='green')
        self.power_line, = self.ax_power.plot([], [], label='Power (W)', color='red')

        # Set plot properties
        for ax, title, ylabel in [
            (self.ax_voltage, 'Voltage over Time', 'Voltage (V)'),
            (self.ax_current, 'Current over Time', 'Current (A)'),
            (self.ax_power, 'Power over Time', 'Power (W)')
        ]:
            ax.set_title(title)
            ax.set_xlabel('Time (s)')
            ax.set_ylabel(ylabel)
            ax.legend()
            ax.grid(True)

        # Embed the plot in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Data storage using deque for efficiency
        self.start_time = None
        self.times = deque(maxlen=1000)
        self.voltages = deque(maxlen=1000)
        self.currents = deque(maxlen=1000)
        self.powers = deque(maxlen=1000)
        self.plot_queue = plot_queue  # Receive plot_queue from external
        self.lock = threading.Lock()

        # Define the formatter function
        def seconds_to_hms(x, pos):
            """Convert seconds to HH:MM:SS format for x-axis."""
            hrs = int(x) // 3600
            mins = (int(x) % 3600) // 60
            secs = int(x) % 60
            return f"{hrs:02}:{mins:02}:{secs:02}"

        # Set the formatter for each x-axis
        formatter = FuncFormatter(seconds_to_hms)
        self.ax_voltage.xaxis.set_major_formatter(formatter)
        self.ax_current.xaxis.set_major_formatter(formatter)
        self.ax_power.xaxis.set_major_formatter(formatter)

        # Schedule periodic plot updates
        self.update_interval = 100  # milliseconds
        self.master.after(self.update_interval, self._update_plot)
        logging.debug("PlotWindow initialized and plot update scheduled.")

    def _update_plot(self):
        """Update the plot with new data from the queue."""
        try:
            while not self.plot_queue.empty():
                timestamp, voltage, current = self.plot_queue.get_nowait()
                logging.debug(f"PlotWindow received data: {timestamp}, {voltage}, {current}")
                if self.start_time is None:
                    self.start_time = timestamp
                normalized_time = timestamp - self.start_time
                self.times.append(normalized_time)
                self.voltages.append(voltage)
                self.currents.append(current)
                self.powers.append(voltage * current)
        except queue.Empty:
            pass

        if self.times:
            # Update plot lines
            self.voltage_line.set_data(self.times, self.voltages)
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()

            self.current_line.set_data(self.times, self.currents)
            self.ax_current.relim()
            self.ax_current.autoscale_view()

            self.power_line.set_data(self.times, self.powers)
            self.ax_power.relim()
            self.ax_power.autoscale_view()

            # Redraw the canvas
            self.canvas.draw()

        # Schedule the next update
        self.master.after(self.update_interval, self._update_plot)
        logging.debug("PlotWindow plot updated.")

    def close(self):
        """Close the plot window."""
        self.master.destroy()
        logging.debug("PlotWindow closed.")
