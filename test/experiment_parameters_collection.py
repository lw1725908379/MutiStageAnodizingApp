import itertools
import csv
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Define the parameter ranges and step sizes
voltage_range = list(range(0, 24, 2))  # From 0 to 50 with a step of 5
kp_range = [round(kp, 5) for kp in [i * 0.1 for i in range(11)]]  # From 0 to 1 with a step of 0.1
ramp_rate = 0.1  # V/s
sampling_rate = 1  # Hz

# Ensure parameters are valid
assert ramp_rate > 0, "Ramp rate must be a positive value."
assert sampling_rate > 0, "Sampling rate must be a positive value."

# Generate all combinations of initial and final voltages
voltage_combinations = list(itertools.permutations(voltage_range, 2)) + [(v, v) for v in voltage_range]

# Calculate the duration for each combination based on ramp_rate
experiment_data = []
for initial_voltage, final_voltage in voltage_combinations:
    voltage_difference = abs(final_voltage - initial_voltage)
    duration = voltage_difference / ramp_rate  # Duration in seconds
    for kp in kp_range:
        experiment_data.append({
            "voltage_start": initial_voltage,
            "voltage_end": final_voltage,
            "time_duration": round(duration, 2),
            "Sampling Rate (Hz)": sampling_rate,
            "Kp": kp
        })

# Write the data to a CSV file
csv_file = "experiment_parameters.csv"
try:
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=experiment_data[0].keys())
        writer.writeheader()
        writer.writerows(experiment_data)
    logging.info(f"Experiment parameters saved to {csv_file}")
except Exception as e:
    logging.error(f"Failed to save experiment parameters: {e}")
