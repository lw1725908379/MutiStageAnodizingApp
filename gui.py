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

from control_strategy import LinearStrategy, PIDStrategy, FeedforwardWithFeedbackStrategy

class ExperimentGUI:
    """Main GUI class for the experiment control panel."""

    def __init__(self, root, default_storage_path=None, default_serial_port=None):
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

        # Optional default parameters
        self.default_storage_path = default_storage_path or "./experiment_data"
        self.default_serial_port = default_serial_port or None

        # Create GUI components
        self.create_widgets()

        # Log initialization success
        logging.info("ExperimentGUI initialized successfully with default storage path: "
                     f"{self.default_storage_path} and default serial port: {self.default_serial_port}")

    def create_widgets(self):
        """Create and layout the GUI components."""

        def add_label_and_entry(row, label_text, default_value=None, entry_var=None):
            label = tk.Label(self.root, text=label_text)
            label.grid(row=row, column=0, padx=5, pady=5, sticky="e")
            entry = tk.Entry(self.root, textvariable=entry_var)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
            if default_value is not None:
                entry.insert(0, str(default_value))
            return label, entry

        # Serial Port Selection
        tk.Label(self.root, text="Select Serial Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.serial_ports = self.serial_manager.get_serial_ports()
        self.combo_serial = ttk.Combobox(self.root, values=self.serial_ports, state="readonly")
        self.combo_serial.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.combo_serial.bind("<<ComboboxSelected>>", self.set_serial_port)

        # Voltage and Time Inputs
        self.label_voltage_start, self.entry_voltage_start = add_label_and_entry(1, "Initial Voltage (V):")
        self.label_voltage_end, self.entry_voltage_end = add_label_and_entry(2, "Termination Voltage (V):")
        self.label_time, self.entry_time = add_label_and_entry(3, "Set Time (s):")
        self.label_sample_rate, self.entry_sample_rate = add_label_and_entry(4, "Sample Rate (Hz):", Config.DEFAULT_SAMPLE_RATE)

        # Control Mode
        tk.Label(self.root, text="Control Mode:").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.combo_control_mode = ttk.Combobox(self.root, values=["Linear", "PID", "Feedforward"], state="readonly")
        self.combo_control_mode.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.combo_control_mode.current(0)
        self.combo_control_mode.bind("<<ComboboxSelected>>", self.on_control_mode_changed)

        # PID Parameters
        self.label_kp, self.entry_kp = add_label_and_entry(6, "Kp:", default_value="2.0")
        self.label_ki, self.entry_ki = add_label_and_entry(7, "Ki:", default_value="5.0")
        self.label_kd, self.entry_kd = add_label_and_entry(8, "Kd:", default_value="1.0")

        # Feedforward K Parameter
        self.label_k_ff, self.entry_k_ff = add_label_and_entry(9, "K (Feedforward):", default_value="0.01")

        # Data Storage Path
        tk.Label(self.root, text="Storage Path:").grid(row=10, column=0, padx=5, pady=5, sticky="e")
        self.entry_storage_path = tk.Entry(self.root)
        self.entry_storage_path.grid(row=10, column=1, padx=5, pady=5, sticky="w")
        self.button_browse = tk.Button(self.root, text="Browse", command=self.browse_storage_path)
        self.button_browse.grid(row=10, column=2, padx=5, pady=5, sticky="w")

        # Buttons Frame
        self.frame_buttons = tk.Frame(self.root)
        self.frame_buttons.grid(row=11, column=0, columnspan=3, padx=5, pady=5)
        tk.Button(self.frame_buttons, text="Add Stage", command=self.add_stage, width=15).pack(side="left", padx=5)
        tk.Button(self.frame_buttons, text="Delete Selected Stage(s)", command=self.delete_stage, width=20).pack(side="left", padx=5)
        self.button_start = tk.Button(self.frame_buttons, text="Start Experiment", command=self.start_experiment, width=15)
        self.button_start.pack(side="left", padx=5)
        self.button_stop = tk.Button(self.frame_buttons, text="Stop Experiment", command=self.stop_experiment, width=15, state="disabled")
        self.button_stop.pack(side="left", padx=5)

        # Stages Treeview
        self.frame_stages = tk.Frame(self.root)
        self.frame_stages.grid(row=12, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.root.grid_rowconfigure(12, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.tree_stages = ttk.Treeview(
            self.frame_stages,
            columns=("Stage No.", "Initial Voltage (V)", "Termination Voltage (V)", "Duration (s)"),
            show="headings",
            selectmode="extended",
        )
        self.tree_stages.heading("Stage No.", text="Stage No.")
        self.tree_stages.heading("Initial Voltage (V)", text="Initial Voltage (V)")
        self.tree_stages.heading("Termination Voltage (V)", text="Termination Voltage (V)")
        self.tree_stages.heading("Duration (s)", text="Duration (s)")

        self.tree_stages.column("Stage No.", width=80, anchor="center")
        self.tree_stages.column("Initial Voltage (V)", width=150, anchor="center")
        self.tree_stages.column("Termination Voltage (V)", width=170, anchor="center")
        self.tree_stages.column("Duration (s)", width=100, anchor="center")

        self.scrollbar_stages = ttk.Scrollbar(self.frame_stages, orient="vertical", command=self.tree_stages.yview)
        self.tree_stages.configure(yscroll=self.scrollbar_stages.set)
        self.scrollbar_stages.pack(side="right", fill="y")
        self.tree_stages.pack(fill="both", expand=True)

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor="w")
        self.status_bar.grid(row=13, column=0, columnspan=3, sticky="we")

        # Initialize parameter visibility
        self.on_control_mode_changed(None)

    def on_control_mode_changed(self, event=None):
        """Show or hide control parameters based on the selected control mode."""
        mode = self.combo_control_mode.get()

        def toggle_widgets(show, widgets):
            """Helper function to show or hide a list of widgets."""
            for widget in widgets:
                if show:
                    widget.grid()
                else:
                    widget.grid_remove()

        # Define widgets for each control mode
        pid_widgets = [self.label_kp, self.entry_kp, self.label_ki, self.entry_ki, self.label_kd, self.entry_kd]
        feedforward_widgets = [self.label_k_ff, self.entry_k_ff]

        # Toggle visibility based on selected mode
        if mode == "PID":
            toggle_widgets(True, pid_widgets)  # Show PID parameters
            toggle_widgets(False, feedforward_widgets)  # Hide Feedforward parameters
        elif mode == "Feedforward":
            toggle_widgets(True, feedforward_widgets)  # Show Feedforward parameters
            toggle_widgets(False, pid_widgets)  # Hide PID parameters
        else:  # Linear mode
            toggle_widgets(False, pid_widgets)  # Hide PID parameters
            toggle_widgets(False, feedforward_widgets)  # Hide Feedforward parameters

    def set_serial_port(self, event=None):
        """Handle serial port selection."""
        serial_port = self.combo_serial.get()

        if not serial_port:
            # No serial port selected
            self._show_error("No serial port selected.", log_message="No serial port selected.")
            return

        try:
            # Attempt to connect to the selected serial port
            success, message = self.serial_manager.connect(serial_port)
            if success:
                self._show_info("Serial Port", message)
                self.update_status(message)
                self._toggle_start_button(enable=True)
            else:
                self._show_error("Serial Port Error", message, log_message=f"Error: {message}")
        except Exception as e:
            # Handle unexpected exceptions during serial connection
            error_message = f"Unexpected error when connecting to serial port: {e}"
            self._show_error("Serial Port Error", error_message, log_message=error_message)

    def add_stage(self):
        """Add a new experimental stage."""
        try:
            # Validate user inputs
            voltage_start, voltage_end, time_duration = self._validate_stage_inputs()

            # Add the stage to the stage manager
            stage = self.stage_manager.add_stage(voltage_start, voltage_end, time_duration)

            # Update the Treeview with the new stage
            stage_no = len(self.stage_manager.get_stages())
            self.tree_stages.insert('', 'end', values=(stage_no, voltage_start, voltage_end, time_duration))

            # Notify the user and update the status
            self._show_info("Add Stage", f"Added stage: {stage}")
            self.update_status(f"Added stage {stage_no}")
        except ValueError as e:
            self._show_error("Invalid Input", str(e), log_message=f"Error adding stage: {e}")
        except Exception as e:
            self._show_error("Error", "An unexpected error occurred.", log_message=f"Unexpected error: {e}")

    def delete_stage(self):
        """Delete selected experimental stages."""
        try:
            # Validate selected stages
            selected_items = self._get_selected_stages()
            if not selected_items:
                return

            # Confirm deletion
            if not self._confirm_action("Confirm Deletion", "Are you sure you want to delete the selected stage(s)?"):
                return

            # Extract stage indices and delete from stage manager
            indices = self._get_stage_indices(selected_items)
            self.stage_manager.delete_stage(indices)

            # Remove items from Treeview and update stage numbers
            self._update_treeview_after_deletion(selected_items)

            # Notify user and log
            self._show_info("Delete Stage", "Selected stage(s) deleted.")
            self.update_status("Deleted selected stages.")
        except Exception as e:
            self._show_error("Error", "An error occurred while deleting stages.", log_message=f"Error: {e}")

    def browse_storage_path(self):
        """Browse and select storage path."""
        try:
            folder_selected = filedialog.askdirectory()
            if folder_selected:
                # Update the entry field and log the selected path
                self._update_storage_path(folder_selected)
                self.update_status(f"Selected storage path: {folder_selected}")
            else:
                # Log and update status for no selection
                logging.info("Storage path selection canceled by user.")
                self.update_status("Storage path selection canceled.")
        except Exception as e:
            # Handle unexpected errors
            logging.error(f"Error selecting storage path: {e}")
            self.update_status("Error: Failed to select storage path.")

    def start_experiment(self):
        """Start the experiment."""
        try:
            # Validate stages
            if not self.stage_manager.get_stages():
                self._show_error(
                    title="No Stages",
                    message="Please add at least one experimental stage.",
                    log_message="Attempted to start experiment without any stages."
                )
                return

            # Validate serial port connection
            if not self.serial_manager.power_supply:
                self._show_error(
                    title="No Serial Port",
                    message="Please select a serial port first.",
                    log_message="Attempted to start experiment without selecting serial port."
                )
                return

            # Check if an experiment is already running
            if self.experiment_controller and self.experiment_controller.is_experiment_running:
                self._show_error(
                    title="Experiment Running",
                    message="An experiment is already running.",
                    log_message="Attempted to start a new experiment while one is already running."
                )
                return

            # Validate storage path
            storage_path = self.entry_storage_path.get()
            if not storage_path:
                self._show_error(
                    title="No Storage Path",
                    message="Please select a storage path.",
                    log_message="Attempted to start experiment without selecting storage path."
                )
                return

            # Initialize storage manager
            if not self._initialize_storage_manager(storage_path):
                return

            # Initialize data collector
            self.data_collector = DataCollector(self.serial_manager.power_supply, self.storage_manager, self.plot_queue)

            # Create and show plot window
            self.plot_window = PlotWindow(tk.Toplevel(self.root), self.plot_queue)
            logging.info("PlotWindow has been created.")

            # Validate control mode and initialize control strategy
            strategy = self._get_control_strategy()
            if not strategy:
                return

            # Validate sample rate
            sample_rate = self._get_sample_rate()
            if sample_rate is None:
                return

            # Set operative mode to enable output
            if not self._set_operative_mode():
                return

            # Initialize and start experiment controller
            self._initialize_and_start_experiment(strategy, sample_rate)

            # Start monitoring thread
            self._start_monitor_thread()

            # Update button states
            self.button_start.config(state='disabled')
            self.button_stop.config(state='normal')

        except Exception as e:
            handle_exception(e, context="Starting experiment")
            self.update_status("Error: Failed to start experiment.")

    def stop_experiment(self):
        """Stop the running experiment."""
        if not (self.experiment_controller and self.experiment_controller.is_experiment_running):
            messagebox.showinfo("No Experiment Running", "No experiment is currently running.")
            self.update_status("No experiment to stop.", log=False)
            logging.warning("Attempted to stop an experiment, but no experiment was running.")
            return

        try:
            # Signal all experiment threads to stop
            self._signal_experiment_stop()

            # Wait for storage thread to finish
            self._wait_for_storage_thread()

            # Close data collector
            self._close_data_collector()

            # Update experiment state and button states
            self.experiment_controller.is_experiment_running = False
            self.button_start.config(state='normal')
            self.button_stop.config(state='disabled')

            # Notify user and update status
            messagebox.showinfo("Experiment Stopped", "Experiment has been stopped.")
            self.update_status("Experiment stopped.")
        except Exception as e:
            logging.error(f"Error while stopping the experiment: {e}")
            self.update_status("Error: Failed to stop the experiment.")
            handle_exception(e, context="Stopping experiment")

    def monitor_experiment(self):
        """Monitor the experiment for completion."""
        try:
            # Wait for the experiment to complete
            self.experiment_controller.monitor_experiment()
            logging.info("Experiment completion signal received.")

            # Perform post-experiment cleanup
            self._handle_experiment_completion()

            # Notify user and update status
            messagebox.showinfo("Experiment Completed", "Experiment completed and data saved.")
            self.update_status("Experiment completed and data saved.")
        except Exception as e:
            logging.error(f"Error during experiment monitoring: {e}")
            self.update_status("Error: Experiment monitoring failed.")
            handle_exception(e, context="Monitoring experiment")

    def on_closing(self):
        """Handle the window close event, ensuring safe shutdown."""
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            self.update_status("Closing program, please wait...")
            logging.info("User confirmed program closure. Initiating cleanup operations.")

            # Run cleanup in a separate thread to avoid UI freezing
            close_thread = threading.Thread(target=self._cleanup_and_exit, daemon=True)
            close_thread.start()

    def cleanup_and_close(self):
        """Cleanup resources and close the application."""
        try:
            self.update_status("Starting cleanup operations...")
            logging.info("Starting cleanup operations...")

            # Disable operative mode for safety
            self._safe_action(
                action=self.serial_manager.power_supply.operative_mode,
                args=(0,),
                log_message="Disabling operative mode for safety.",
                success_message="Operative mode disabled.",
                error_message="Failed to disable operative mode."
            )

            # Set voltage to 0V for safety
            self._safe_action(
                action=self.serial_manager.power_supply.set_voltage,
                args=(0,),
                log_message="Setting voltage to 0 V for safety.",
                success_message="Voltage set to 0 V.",
                error_message="Failed to set voltage to 0 V."
            )

            # Stop running experiment if necessary
            if self.experiment_controller and self.experiment_controller.is_experiment_running:
                self.update_status("Stopping running experiment...")
                logging.info("Stopping running experiment.")
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
                self._safe_action(
                    action=self.storage_manager.close_storage,
                    log_message="Closing storage manager.",
                    success_message="Storage manager closed.",
                    error_message="Failed to close storage manager."
                )

            # Disconnect serial connection
            self._safe_action(
                action=self.serial_manager.disconnect,
                log_message="Disconnecting serial connection.",
                success_message="Serial connection disconnected.",
                error_message="Failed to disconnect serial connection."
            )

            self.update_status("Cleanup completed. Exiting.")
            logging.info("Cleanup operations completed successfully.")
        except Exception as e:
            logging.error(f"Unexpected error during cleanup: {e}")
            self.update_status("Error: Unexpected cleanup error.")
        finally:
            self.root.quit()
            self.root.destroy()

    def update_status(self, message, log=True):
        """
        Update the status bar and optionally log the message.

        Args:
            message (str): The message to display in the status bar.
            log (bool): Whether to log the message (default: True).
        """
        self.status_var.set(message)
        if log:
            logging.info(message)
        self.root.update_idletasks()

    # Helper methods
    def _set_operative_mode(self, mode=1):
        """
        Set the operating mode of the power supply (e.g. enable or disable output).
        mode: 1 for enable, 0 for disable.
        """
        try:
            if self.serial_manager.power_supply:
                self.serial_manager.power_supply.operative_mode(mode)
                logging.info(f"Operative mode set to {mode}.")
                return True
            else:
                logging.error("Power supply is not connected.")
                self.update_status("Error: Power supply not connected.")
                return False
        except Exception as e:
            logging.error(f"Failed to set operative mode: {e}")
            self.update_status("Error: Failed to set operative mode.")
            return False

    def _initialize_and_start_experiment(self, strategy, sample_rate):
        """
        Initialize and start the experiment controller.
        Args:
            strategy: The control strategy to use (e.g., Linear, PID, Feedforward).
            sample_rate: Sampling rate for the experiment.
        """
        try:
            self.experiment_controller = ExperimentController(
                serial_manager=self.serial_manager,
                stage_manager=self.stage_manager,
                storage_manager=self.storage_manager,
                data_collector=self.data_collector,
                plot_window=self.plot_window,
                plot_stop_event=self.plot_stop_event,
                storage_stop_event=self.storage_stop_event,
                experiment_done_event=self.experiment_done_event,
                control_strategy=strategy,
                control_mode=self.combo_control_mode.get()
            )

            # Start the experiment
            self.experiment_controller.start_experiment(sample_rate=sample_rate)
            logging.info("Experiment started successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize and start experiment: {e}")
            self.update_status("Error: Failed to initialize and start experiment.")
            raise

    def _safe_action(self, action, args=(), log_message="", success_message="", error_message=""):
        """
        Safely execute an action with logging and status updates.
        Args:
            action (callable): The function to execute.
            args (tuple): Arguments to pass to the action.
            log_message (str): Log message before execution.
            success_message (str): Message on successful execution.
            error_message (str): Message on execution failure.
        """
        try:
            if log_message:
                logging.info(log_message)
                self.update_status(log_message)
            action(*args)
            if success_message:
                logging.info(success_message)
                self.update_status(success_message)
        except Exception as e:
            if error_message:
                logging.error(f"{error_message}: {e}")
                logging.critical(f"Unhandled error in action: {e}")
                self.update_status(error_message)

    def _cleanup_and_exit(self):
        """Perform cleanup tasks and exit the application."""
        try:
            # Disable operative mode for safety
            if self.serial_manager.power_supply:
                logging.info("Disabling operative mode for safety.")
                self.serial_manager.power_supply.operative_mode(0)
                self.update_status("Operative mode disabled.")

            # Set voltage to 0V for safety
            if self.serial_manager.power_supply:
                logging.info("Setting voltage to 0V for safety.")
                self.serial_manager.power_supply.set_voltage(0)
                self.update_status("Voltage set to 0V.")

            # Stop experiment if running
            if self.experiment_controller and self.experiment_controller.is_experiment_running:
                logging.info("Stopping running experiment.")
                self.experiment_controller.experiment_done_event.set()
                self.experiment_controller.plot_stop_event.set()
                self.experiment_controller.storage_stop_event.set()
                self.experiment_controller.is_experiment_running = False
                self.update_status("Experiment stopped.")

            # Close data collector
            if self.data_collector:
                logging.info("Closing data collector.")
                self.data_collector.close()

            # Close storage manager
            if self.storage_manager:
                logging.info("Closing storage manager.")
                self.storage_manager.close_storage()

            # Disconnect serial connection
            self.serial_manager.disconnect()
            logging.info("Serial connection disconnected.")

            # Update status and exit
            self.update_status("Cleanup completed. Exiting...")
            logging.info("Cleanup completed successfully. Exiting program.")

        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            self.update_status("Error: Cleanup failed.")
            handle_exception(e, context="Cleanup during program exit")
        finally:
            # Ensure the GUI is properly closed
            self.root.quit()
            self.root.destroy()

    def _handle_experiment_completion(self):
        """Handle cleanup tasks after the experiment is completed."""
        # Stop all background threads
        self.plot_stop_event.set()
        self.storage_stop_event.set()
        logging.info("Background threads stopped after experiment completion.")

        # Reset button states
        self.button_start.config(state='normal')
        self.button_stop.config(state='disabled')
        logging.info("Experiment buttons reset to default state.")

    def _close_data_collector(self):
        """Close the data collector."""
        if self.data_collector:
            self.data_collector.close()
            logging.info("Data collector closed.")
            self.update_status("Data collector closed.")

    def _wait_for_storage_thread(self):
        """Wait for the storage thread to stop."""
        if self.experiment_controller.storage_thread:
            self.experiment_controller.storage_thread.join(timeout=5)
            logging.info("Storage consumer thread stopped.")
            self.update_status("Storage consumer thread stopped.")

    def _signal_experiment_stop(self):
        """Signal all threads to stop the experiment."""
        self.experiment_controller.experiment_done_event.set()
        self.experiment_controller.plot_stop_event.set()
        self.experiment_controller.storage_stop_event.set()
        logging.info("Experiment stop signal sent.")
        self.update_status("Stopping experiment...")

    def _get_sample_rate(self):
        """Validate and return the sample rate."""
        try:
            sample_rate = float(self.entry_sample_rate.get())
            if sample_rate <= 0:
                raise ValueError("Sample rate must be positive.")
            return sample_rate
        except ValueError as e:
            self._show_error(
                title="Invalid Sample Rate",
                message="Sample rate must be a positive number.",
                log_message=f"Invalid sample rate input: {e}"
            )
            return None

    def _get_control_strategy(self):
        """Get the selected control strategy based on the control mode."""
        control_mode = self.combo_control_mode.get()
        try:
            if control_mode == "Linear":
                return LinearStrategy()
            elif control_mode == "PID":
                Kp = float(self.entry_kp.get())
                Ki = float(self.entry_ki.get())
                Kd = float(self.entry_kd.get())
                logging.info(f"PID parameters set to Kp={Kp}, Ki={Ki}, Kd={Kd}")
                return PIDStrategy(Kp, Ki, Kd, output_limits=(0, 12))
            elif control_mode == "Feedforward":
                K_ff = float(self.entry_k_ff.get())
                logging.info(f"Feedforward K set to {K_ff}")
                return FeedforwardWithFeedbackStrategy(Kp=K_ff, output_limits=(0, 12))
        except ValueError as e:
            if control_mode == "PID":
                self._show_error(
                    title="Invalid PID Parameters",
                    message="Please enter valid numerical values for Kp, Ki, and Kd.",
                    log_message=f"Invalid PID parameters input: {e}"
                )
            elif control_mode == "Feedforward":
                self._show_error(
                    title="Invalid Feedforward K",
                    message="Please enter a valid numerical value for K.",
                    log_message=f"Invalid Feedforward K input: {e}"
                )
            return None

    def _initialize_storage_manager(self, storage_path):
        """Initialize the storage manager."""
        self.storage_manager = StorageManager(storage_path)
        success, message = self.storage_manager.initialize_storage()
        if not success:
            self._show_error(
                title="Storage Initialization Error",
                message=message,
                log_message="Failed to initialize storage manager."
            )
            return False
        self.update_status(message)
        return True

    def _update_treeview_after_deletion(self, selected_items):
        """
        Update Treeview after deletion of stages.
        Args:
            selected_items (list): List of selected Treeview items.
        """
        # Remove selected items from Treeview
        for item in selected_items:
            self.tree_stages.delete(item)

        # Rebuild Treeview with updated stages
        for idx, item in enumerate(self.tree_stages.get_children(), start=1):
            stage = self.stage_manager.get_stages()[idx - 1]
            self.tree_stages.item(item, values=(idx, stage["voltage_start"], stage["voltage_end"], stage["time"]))

    def _get_stage_indices(self, selected_items):
        """
        Extract stage indices from selected Treeview items.
        Args:
            selected_items (list): List of selected Treeview items.
        Returns:
            list: List of stage indices to delete.
        """
        indices = []
        for item in selected_items:
            values = self.tree_stages.item(item, 'values')
            stage_no = int(values[0]) - 1  # Convert Treeview row number to index
            indices.append(stage_no)
        return indices

    def _confirm_action(self, title, message):
        """
        Confirm an action with the user.
        Args:
            title (str): Title of the confirmation dialog.
            message (str): Message to display.
        Returns:
            bool: True if user confirms, False otherwise.
        """
        return messagebox.askyesno(title, message)

    def _get_selected_stages(self):
        """
        Get selected items from Treeview.
        Returns:
            list: List of selected items.
        """
        selected_items = self.tree_stages.selection()
        if not selected_items:
            self._show_warning("No Selection", "Please select stage(s) to delete.")
            self.update_status("Warning: No stages selected for deletion.")
        return selected_items

    def _validate_stage_inputs(self):
        """
        Validate user inputs for adding a stage.
        Returns:
            tuple: (voltage_start, voltage_end, time_duration) as floats.
        Raises:
            ValueError: If any input is invalid.
        """
        try:
            voltage_start = float(self.entry_voltage_start.get())
            voltage_end = float(self.entry_voltage_end.get())
            time_duration = float(self.entry_time.get())

            if voltage_start < 0 or voltage_end < 0 or time_duration <= 0:
                raise ValueError("Voltage and time values must be positive.")
            return voltage_start, voltage_end, time_duration
        except ValueError as e:
            raise ValueError("Please enter valid numerical values for voltage and time.") from e

    def _show_info(self, title, message):
        """
        Show an informational message box and log the message.
        Args:
            title (str): Title of the info dialog.
            message (str): Message to display.
        """
        messagebox.showinfo(title, message)
        logging.info(message)

    def _show_error(self, title, message, log_message=None):
        """
        Show an error message box and log the error.
        Args:
            title (str): Title of the error dialog.
            message (str): Message to display.
            log_message (str): Log message for the error (optional).
        """
        messagebox.showerror(title, message)
        if log_message:
            logging.error(log_message)

    def _toggle_start_button(self, enable):
        """Enable or disable the start button."""
        self.button_start.config(state='normal' if enable else 'disabled')

    def _show_warning(self, title, message):
        """
        Show a warning message box and log the warning.
        Args:
            title (str): Title of the warning dialog.
            message (str): Message to display.
        """
        messagebox.showwarning(title, message)
        logging.warning(message)

    def _update_storage_path(self, path):
        """
        Update the storage path entry field.
        Args:
            path (str): The selected storage path.
        """
        self.entry_storage_path.delete(0, tk.END)
        self.entry_storage_path.insert(0, path)
        logging.info(f"Storage path updated to: {path}")
