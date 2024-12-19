# Experiment Control System

## Overview
This project is an experiment control system designed to manage scientific or engineering experiments. It includes modules for data acquisition, real-time plotting, experiment control, and data storage. The system communicates with a power supply device using the Modbus RTU protocol and provides a graphical user interface (GUI) for user interaction. The system is modularly designed for flexibility and scalability.

---

## Features
- **Graphical User Interface (GUI):**
  - Parameter configuration.
  - Real-time experiment control.
  - Stage management (add, delete, and configure experiment stages).

- **Real-Time Plotting:**
  - Visualization of voltage, current, and power in real-time.
  - Autoscaling and time axis formatting.

- **Data Storage:**
  - Save experiment data in CSV format, including timestamps.
  - Include control parameters (e.g., PID gains).

- **Flexible Control Strategies:**
  - Linear control.
  - PID control.
  - Feedforward control combined with feedback correction.

- **Device Communication:**
  - Communicate with the power supply device via Modbus RTU protocol.
  - Dynamically handle voltage, current, and power settings.

---

## Requirements

### Software Requirements
- **Python Version:** Python 3.8+
- **Dependencies:**
  - `pymodbus`
  - `matplotlib`
  - `tkinter`

### Hardware Requirements
- **Power Supply Device:** Must support Modbus RTU communication.
- **Serial Communication Interface:** RS-485 or similar interface.

---

## Project Structure

### 1. Core Modules
#### `gui.py`
Main graphical user interface for experiment control. Users can:
- Configure serial ports, voltage, current, and time.
- Select control strategies (Linear, PID, or Feedforward).
- Add and delete experiment stages.
- Start and stop experiments.
- View real-time plots of voltage, current, and power.

#### `experiment_controller.py`
Manages overall experiment execution. Responsibilities include:
- Managing experiment stages.
- Controlling the power supply device based on the selected control strategy.
- Handling sampling rates and data acquisition.

#### `data_collector.py`
Manages data collection and storage tasks using multithreading. Features include:
- Collecting data from the power supply device.
- Adding data to plotting and storage queues.

#### `storage_manager.py`
Handles data storage in CSV format. Responsibilities include:
- Initializing the storage file.
- Writing experiment data.
- Safely closing storage.

#### `plot_window.py`
Provides real-time plotting of experiment data using Matplotlib. Features include:
- Three subplots for voltage, current, and power.
- Autoscaling and readable time formatting.

#### `serial_manager.py`
Manages serial port communication with the power supply device. Features include:
- Listing available serial ports.
- Connecting and disconnecting from the power supply device.

#### `power_supply.py`
Encapsulates all communication with the power supply device. Features include:
- Reading and writing memory registers.
- Setting and getting voltage, current, and power values.
- Reading protection states (e.g., over-voltage protection).

### 2. Utility Modules
#### `config.py`
Contains global configuration parameters, such as:
- Default baud rate and timeout.
- Memory addresses for Modbus communication.
- Default sampling rate and scaling factors.

#### `exceptions.py`
Defines custom exception classes:
- Modbus communication errors (`ModbusConnectionError`).
- Data storage issues (`DataStorageError`).

#### `control_interface.py`
Defines the interface for control strategies, including:
- Abstract methods for setting setpoints, updating outputs, and resetting states.

#### `control_strategy.py`
Implements the following control strategies:
- **LinearStrategy:** Directly outputs the setpoint.
- **PIDStrategy:** Implements a PID controller.
- **FeedforwardWithFeedbackStrategy:** Combines feedforward control with feedback correction.

#### `utils.py`
Provides utility functions, including:
- `handle_exception`: Logs detailed information and stack traces for exceptions.

#### `stage_manager.py`
Manages the list of experiment stages. Responsibilities include:
- Adding, deleting, and retrieving stages.

---

## How to Run

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd <repository_name>
   ```
2. Install required dependencies:
   ```bash
   pip install pymodbus matplotlib
   ```
3. Run the main program:
   ```bash
   python main.py
   ```

---

## Usage

### Step 1: Configure Serial Port
- Select an available serial port from the dropdown menu.
- Click "Connect" to establish a connection with the power supply device.

### Step 2: Add Experiment Stages
- Set the starting voltage, ending voltage, and duration for each stage.
- Add multiple stages as needed.

### Step 3: Select Control Mode
- Choose a control mode (Linear, PID, or Feedforward).
- Configure parameters as needed (e.g., PID gains).

### Step 4: Start the Experiment
- Specify the sampling rate.
- Choose a storage path for saving data.
- Click the "Start Experiment" button to begin.

### Step 5: Monitor and Save Results
- Monitor real-time plots of voltage, current, and power.
- Experiment data will be automatically saved to the selected storage path.

---

## Sample Output

### CSV File
```csv
Timestamp,TargetVoltage,MeasuredVoltage,ControlSignal,ControlMode,Current,FeedforwardKp,PIDKp,PIDKi,PIDKd
1692851020,5.0,4.98,4.99,PID,0.15,,,2.0,5.0,1.0
```

### Real-Time Plot
![Sample Plot](example_plot.png)

---

## Known Issues
- Ensure the power supply device supports Modbus RTU and is connected to the correct serial port.
- Large datasets may cause performance issues in real-time plotting.

---

## Contribution
Feel free to submit issues or pull requests to fix bugs or enhance features. Contributions are welcome!

---

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Acknowledgments
- **Pymodbus Library:** For Modbus RTU communication.
- **Matplotlib:** For real-time data visualization.
- **Tkinter:** For the GUI framework.

---


