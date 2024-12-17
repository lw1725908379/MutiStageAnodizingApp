# gui.py
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import logging
from serial_manager import SerialManager
from stage_manager import StageManager
from storage_manager import StorageManager
from data_collector import DataCollector
from plot_window import PlotWindow
from experiment_controller import ExperimentController
import threading
from utils import handle_exception
from config import Config
import queue

class ExperimentGUI:
    """Main GUI class for the experiment control panel."""

    def __init__(self, root):
        self.root = root
        self.root.title("Experiment Control Panel")

        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize modules
        self.serial_manager = SerialManager()
        self.stage_manager = StageManager()
        self.storage_manager = None  # Will be initialized when starting experiment
        self.plot_queue = queue.Queue()
        self.plot_stop_event = threading.Event()
        self.storage_stop_event = threading.Event()
        self.experiment_done_event = threading.Event()
        self.plot_window = None
        self.data_collector = None
        self.experiment_controller = None

        # Create GUI components
        self.create_widgets()

    def create_widgets(self):
        """Create and layout the GUI components."""
        # Serial port selection
        self.label_serial = tk.Label(self.root, text="Select Serial Port:")
        self.label_serial.grid(row=0, column=0, padx=5, pady=5, sticky='e')

        self.serial_ports = self.serial_manager.get_serial_ports()
        self.combo_serial = ttk.Combobox(self.root, values=self.serial_ports, state="readonly")
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)

        # Voltage and time settings
        self.label_voltage_start = tk.Label(self.root, text="Initial Voltage (V):")
        self.label_voltage_start.grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.entry_voltage_start = tk.Entry(self.root)
        self.entry_voltage_start.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        self.label_voltage_end = tk.Label(self.root, text="Termination Voltage (V):")
        self.label_voltage_end.grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.entry_voltage_end = tk.Entry(self.root)
        self.entry_voltage_end.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        self.label_time = tk.Label(self.root, text="Set Time (s):")
        self.label_time.grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.entry_time = tk.Entry(self.root)
        self.entry_time.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.label_sample_rate = tk.Label(self.root, text="Sample Rate (Hz):")
        self.label_sample_rate.grid(row=4, column=0, padx=5, pady=5, sticky='e')
        self.entry_sample_rate = tk.Entry(self.root)
        self.entry_sample_rate.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        self.entry_sample_rate.insert(0, str(Config.DEFAULT_SAMPLE_RATE))

        # PID 参数设置
        self.label_pid = tk.Label(self.root, text="PID 参数设置:")
        self.label_pid.grid(row=5, column=0, padx=5, pady=5, sticky='e')

        self.label_kp = tk.Label(self.root, text="Kp:")
        self.label_kp.grid(row=6, column=0, padx=5, pady=5, sticky='e')
        self.entry_kp = tk.Entry(self.root)
        self.entry_kp.grid(row=6, column=1, padx=5, pady=5, sticky='w')
        self.entry_kp.insert(0, "2.0")  # 默认值

        self.label_ki = tk.Label(self.root, text="Ki:")
        self.label_ki.grid(row=7, column=0, padx=5, pady=5, sticky='e')
        self.entry_ki = tk.Entry(self.root)
        self.entry_ki.grid(row=7, column=1, padx=5, pady=5, sticky='w')
        self.entry_ki.insert(0, "5.0")  # 默认值

        self.label_kd = tk.Label(self.root, text="Kd:")
        self.label_kd.grid(row=8, column=0, padx=5, pady=5, sticky='e')
        self.entry_kd = tk.Entry(self.root)
        self.entry_kd.grid(row=8, column=1, padx=5, pady=5, sticky='w')
        self.entry_kd.insert(0, "1.0")  # 默认值

        # 数据存储路径
        self.label_storage_path = tk.Label(self.root, text="Storage Path:")
        self.label_storage_path.grid(row=9, column=0, padx=5, pady=5, sticky='e')
        self.entry_storage_path = tk.Entry(self.root)
        self.entry_storage_path.grid(row=9, column=1, padx=5, pady=5, sticky='w')
        self.button_browse = tk.Button(self.root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=9, column=2, padx=5, pady=5, sticky='w')

        # Buttons frame
        self.frame_buttons = tk.Frame(self.root)
        self.frame_buttons.grid(row=10, column=0, columnspan=3, padx=5, pady=5)
        self.button_add_stage = tk.Button(self.frame_buttons, text="Add Stage", command=self.add_stage, width=15)
        self.button_add_stage.pack(side='left', padx=5)
        self.button_delete_stage = tk.Button(self.frame_buttons, text="Delete Selected Stage(s)", command=self.delete_stage, width=20)
        self.button_delete_stage.pack(side='left', padx=5)
        self.button_start = tk.Button(self.frame_buttons, text="Start Experiment", command=self.start_experiment, width=15)
        self.button_start.pack(side='left', padx=5)
        self.button_stop = tk.Button(self.frame_buttons, text="Stop Experiment", command=self.stop_experiment, width=15, state='disabled')
        self.button_stop.pack(side='left', padx=5)

        # Stages Treeview
        self.frame_stages = tk.Frame(self.root)
        self.frame_stages.grid(row=11, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.root.grid_rowconfigure(11, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.tree_stages = ttk.Treeview(
            self.frame_stages,
            columns=("Stage No.", "Initial Voltage (V)", "Termination Voltage (V)", "Duration (s)"),
            show='headings',
            selectmode='extended'
        )
        self.tree_stages.heading("Stage No.", text="Stage No.")
        self.tree_stages.heading("Initial Voltage (V)", text="Initial Voltage (V)")
        self.tree_stages.heading("Termination Voltage (V)", text="Termination Voltage (V)")
        self.tree_stages.heading("Duration (s)", text="Duration (s)")

        self.tree_stages.column("Stage No.", width=80, anchor='center')
        self.tree_stages.column("Initial Voltage (V)", width=150, anchor='center')
        self.tree_stages.column("Termination Voltage (V)", width=170, anchor='center')
        self.tree_stages.column("Duration (s)", width=100, anchor='center')

        self.scrollbar_stages = ttk.Scrollbar(self.frame_stages, orient="vertical", command=self.tree_stages.yview)
        self.tree_stages.configure(yscroll=self.scrollbar_stages.set)
        self.scrollbar_stages.pack(side='right', fill='y')
        self.tree_stages.pack(fill='both', expand=True)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor='w')
        self.status_bar.grid(row=12, column=0, columnspan=3, sticky='we')

    def set_serial_port(self, event):
        """Handle serial port selection."""
        serial_port = self.combo_serial.get()
        if serial_port:
            success, message = self.serial_manager.connect(serial_port)
            if success:
                messagebox.showinfo("Serial Port", message)
                self.update_status(message)
                self.button_start.config(state='normal')
            else:
                messagebox.showerror("Serial Port Error", message)
                self.update_status(f"Error: {message}")
        else:
            logging.warning("No serial port selected.")
            self.update_status("No serial port selected.")

    def add_stage(self):
        """Add a new experimental stage."""
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())
            stage = self.stage_manager.add_stage(voltage_start, voltage_end, time_duration)

            stage_no = len(self.stage_manager.get_stages())
            self.tree_stages.insert('', 'end', values=(stage_no, voltage_start, voltage_end, time_duration))

            messagebox.showinfo("Add Stage", f"Added stage: {stage}")
            self.update_status(f"Added stage {stage_no}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid voltage and time values.")
            logging.error("Invalid input when adding experiment stage.")
            self.update_status("Error: Invalid input for adding stage.")

    def delete_stage(self):
        """Delete selected experimental stages."""
        selected_items = self.tree_stages.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select stage(s) to delete.")
            logging.warning("Attempted to delete stages without selection.")
            self.update_status("Warning: No stages selected for deletion.")
            return

        confirm = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected stage(s)?")
        if not confirm:
            return

        indices = []
        for item in selected_items:
            values = self.tree_stages.item(item, 'values')
            stage_no = int(values[0]) - 1
            indices.append(stage_no)

        self.stage_manager.delete_stage(indices)

        for item in selected_items:
            self.tree_stages.delete(item)

        # Update stage numbers in Treeview
        for idx, item in enumerate(self.tree_stages.get_children(), start=1):
            stage = self.stage_manager.get_stages()[idx -1]
            self.tree_stages.item(item, values=(idx, stage["voltage_start"], stage["voltage_end"], stage["time"]))

        messagebox.showinfo("Delete Stage", "Selected stage(s) deleted.")
        logging.info(f"Deleted stages: {selected_items}")
        self.update_status("Deleted selected stages.")

    def browse_storage_path(self):
        """Browse and select storage path."""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_storage_path.delete(0, tk.END)
            self.entry_storage_path.insert(0, folder_selected)
            logging.info(f"Selected storage path: {folder_selected}")
            self.update_status(f"Selected storage path: {folder_selected}")

    def start_experiment(self):
        """Start the experiment."""
        if not self.stage_manager.get_stages():
            messagebox.showerror("No Stages", "Please add at least one experimental stage.")
            logging.error("Attempted to start experiment without any stages.")
            self.update_status("Error: No stages added.")
            return

        if not self.serial_manager.power_supply:
            messagebox.showerror("No Serial Port", "Please select a serial port first.")
            logging.error("Attempted to start experiment without selecting serial port.")
            self.update_status("Error: No serial port selected.")
            return

        if self.experiment_controller and self.experiment_controller.is_experiment_running:
            messagebox.showwarning("Experiment Running", "An experiment is already running.")
            logging.warning("Attempted to start a new experiment while one is already running.")
            self.update_status("Warning: Experiment already running.")
            return

        storage_path = self.entry_storage_path.get()
        if not storage_path:
            messagebox.showerror("No Storage Path", "Please select a storage path.")
            logging.error("Attempted to start experiment without selecting storage path.")
            self.update_status("Error: No storage path selected.")
            return

        # 初始化 storage manager
        self.storage_manager = StorageManager(storage_path)
        success, message = self.storage_manager.initialize_storage()
        if not success:
            messagebox.showerror("Storage Initialization Error", message)
            logging.error("Failed to initialize storage manager.")
            self.update_status(f"Error: {message}")
            return
        else:
            self.update_status(message)

        # 初始化 data collector
        self.data_collector = DataCollector(self.serial_manager.power_supply, self.storage_manager, self.plot_queue)

        # 创建并显示 plot window
        self.plot_window = PlotWindow(tk.Toplevel(self.root), self.plot_queue)
        logging.info("PlotWindow has been created.")

        # 读取 PID 参数
        try:
            Kp = float(self.entry_kp.get())
            Ki = float(self.entry_ki.get())
            Kd = float(self.entry_kd.get())
        except ValueError:
            messagebox.showerror("Invalid PID Parameters", "Please enter valid numerical values for Kp, Ki, and Kd.")
            logging.error("Invalid PID parameters input.")
            self.update_status("Error: Invalid PID parameters.")
            return

        # 初始化 experiment_controller 时传递 PID 参数
        self.experiment_controller = ExperimentController(
            self.serial_manager,
            self.stage_manager,
            self.storage_manager,
            self.data_collector,
            self.plot_window,
            self.plot_stop_event,
            self.storage_stop_event,
            self.experiment_done_event,
            Kp=Kp,
            Ki=Ki,
            Kd=Kd
        )
        logging.info(f"PID parameters set to Kp={Kp}, Ki={Ki}, Kd={Kd}")
        self.update_status(f"PID parameters set to Kp={Kp}, Ki={Ki}, Kd={Kd}")

        # 获取采样率
        try:
            sample_rate = float(self.entry_sample_rate.get())
            if sample_rate <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Sample Rate", "Sample rate must be a positive number.")
            logging.error("Invalid sample rate input.")
            self.update_status("Error: Invalid sample rate.")
            return

        # 设置操作模式为 1（启用输出）
        try:
            self.serial_manager.power_supply.operative_mode(1)
            logging.info("Operative mode set to 1 (output enabled).")
            self.update_status("Operative mode enabled.")
        except Exception as e:
            handle_exception(e, context="Setting operative mode")
            self.update_status("Error: Failed to set operative mode.")
            return

        # 启动实验
        self.experiment_controller.start_experiment(sample_rate)
        logging.info("Experiment started.")
        self.update_status("Experiment started.")

        # 启动监控线程
        monitor_thread = threading.Thread(target=self.monitor_experiment, daemon=True)
        monitor_thread.start()

        # 更新按钮状态
        self.button_start.config(state='disabled')
        self.button_stop.config(state='normal')

    def stop_experiment(self):
        """Stop the running experiment."""
        if self.experiment_controller and self.experiment_controller.is_experiment_running:
            self.experiment_controller.experiment_done_event.set()
            self.experiment_controller.plot_stop_event.set()
            self.experiment_controller.storage_stop_event.set()
            logging.info("Experiment stop signal sent.")
            self.update_status("Stopping experiment...")

            # Wait for storage thread to finish
            if self.experiment_controller.storage_thread:
                self.experiment_controller.storage_thread.join(timeout=5)
                logging.info("Storage consumer thread stopped.")
                self.update_status("Storage consumer thread stopped.")

            # Close data collector
            if self.data_collector:
                self.data_collector.close()
                logging.info("Data collector closed.")
                self.update_status("Data collector closed.")

            self.experiment_controller.is_experiment_running = False

            # Update button states
            self.button_start.config(state='normal')
            self.button_stop.config(state='disabled')

            messagebox.showinfo("Experiment Stopped", "Experiment has been stopped.")
            self.update_status("Experiment stopped.")

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        self.experiment_controller.monitor_experiment()

        # After experiment is done
        self.plot_stop_event.set()
        self.storage_stop_event.set()

        # Update button states
        self.button_start.config(state='normal')
        self.button_stop.config(state='disabled')

        messagebox.showinfo("Experiment Completed", "Experiment completed and data saved.")
        self.update_status("Experiment completed and data saved.")

    def on_closing(self):
        """Handle the window close event, ensuring safe shutdown."""
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            logging.info("Program closing, starting cleanup operations.")
            # Start a new thread for cleanup to avoid blocking
            close_thread = threading.Thread(target=self.cleanup_and_close, daemon=True)
            close_thread.start()

    def cleanup_and_close(self):
        """Cleanup resources and close the application."""
        # Disable operative mode
        if self.serial_manager.power_supply:
            try:
                logging.info("Disabling operative mode for safety.")
                self.serial_manager.power_supply.operative_mode(0)
                logging.info("Operative mode disabled.")
                self.update_status("Operative mode disabled.")
            except Exception as e:
                logging.error(f"Error disabling operative mode: {e}")
                self.update_status("Error: Failed to disable operative mode.")

        # Set voltage to 0
        if self.serial_manager.power_supply:
            try:
                logging.info("Setting voltage to 0 V for safety.")
                self.serial_manager.power_supply.set_voltage(0)
                logging.info("Voltage set to 0 V.")
                self.update_status("Voltage set to 0 V.")
            except Exception as e:
                logging.error(f"Error setting voltage to 0: {e}")
                self.update_status("Error: Failed to set voltage to 0 V.")

        # If experiment is running, stop it
        if self.experiment_controller and self.experiment_controller.is_experiment_running:
            logging.info("Experiment is running, attempting to stop.")
            self.experiment_controller.experiment_done_event.set()
            self.experiment_controller.plot_stop_event.set()
            self.experiment_controller.storage_stop_event.set()

            # Wait for storage thread to finish
            if self.experiment_controller.storage_thread:
                self.experiment_controller.storage_thread.join(timeout=5)
                logging.info("Storage consumer thread stopped.")
                self.update_status("Storage consumer thread stopped.")

            # Close data collector
            if self.data_collector:
                self.data_collector.close()
                logging.info("Data collector closed.")
                self.update_status("Data collector closed.")

            self.experiment_controller.is_experiment_running = False

        # Close storage
        if self.storage_manager:
            self.storage_manager.close_storage()
            logging.info("Storage manager closed.")
            self.update_status("Storage manager closed.")

        # Disconnect serial port
        self.serial_manager.disconnect()
        logging.info("Serial connection disconnected.")
        self.update_status("Serial connection disconnected.")

        logging.info("Cleanup operations completed. Exiting program.")
        self.update_status("Cleanup completed. Exiting.")

        self.root.quit()
        self.root.destroy()

    def update_status(self, message):
        """Update the status bar."""
        self.status_var.set(message)
        self.root.update_idletasks()
