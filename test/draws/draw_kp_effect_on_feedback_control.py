import numpy as np
import matplotlib.pyplot as plt

# 时间设置
time = np.linspace(0, 500, 500)  # 500个数据点，总时间500s
time_zoom = np.linspace(0, 5, 50)  # 放大前5秒

# 设定目标电压变化（前馈控制）
set_point = 0.1 * time  # 从0V到50V，升压速率0.1V/s
set_point_zoom = 0.1 * time_zoom

# 假设实际电压的响应包含滞后和噪声
# 假设系统的响应速度滞后0.5秒，且有一个简单的噪声
actual_voltage = set_point + 0.1 * np.sin(0.1 * time) + 0.05 * np.random.randn(len(time))
actual_voltage_zoom = set_point_zoom + 0.1 * np.sin(0.1 * time_zoom) + 0.05 * np.random.randn(len(time_zoom))

# 定义代表性 Kp 值
kp_values = [0.2, 0.8, 1.5]  # 低、中、高 Kp 值

# 初始化图像
plt.figure(figsize=(12, 8))

# 绘制全局图
plt.subplot(2, 1, 1)
plt.plot(time, set_point, label="Set Point (Ideal Voltage)", linestyle='--', color='blue')
plt.plot(time, actual_voltage, label="Actual Voltage (Without Feedback)", color='red')

for kp in kp_values:
    feedback_correction = kp * (set_point - actual_voltage)
    corrected_voltage = actual_voltage + feedback_correction
    plt.plot(time, corrected_voltage, label=f"Corrected Voltage (Kp={kp})")

plt.xlabel('Time (s)')
plt.ylabel('Voltage (V)')
plt.title('Feedforward Control with Feedback Correction (Full Range)')
plt.legend()
plt.grid(True)

# 绘制局部放大图
plt.subplot(2, 1, 2)
plt.plot(time_zoom, set_point_zoom, label="Set Point (Ideal Voltage)", linestyle='--', color='blue')
plt.plot(time_zoom, actual_voltage_zoom, label="Actual Voltage (Without Feedback)", color='red')

for kp in kp_values:
    feedback_correction_zoom = kp * (set_point_zoom - actual_voltage_zoom)
    corrected_voltage_zoom = actual_voltage_zoom + feedback_correction_zoom
    plt.plot(time_zoom, corrected_voltage_zoom, label=f"Corrected Voltage (Kp={kp})")

plt.xlabel('Time (s)')
plt.ylabel('Voltage (V)')
plt.title('Feedforward Control with Feedback Correction (Zoomed In)')
plt.legend()
plt.grid(True)

# 显示图像
plt.tight_layout()
plt.show()
