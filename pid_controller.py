# pid_controller.py
import time

class PIDController:
    """简单的 PID 控制器实现。"""

    def __init__(self, Kp, Ki, Kd, setpoint=0.0, output_limits=(0, 100)):
        """
        初始化 PID 控制器。

        :param Kp: 比例增益
        :param Ki: 积分增益
        :param Kd: 微分增益
        :param setpoint: 目标设定值
        :param output_limits: 输出限制 (最小值, 最大值)
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint

        self._min_output, self._max_output = output_limits

        self._previous_error = 0.0
        self._integral = 0.0
        self._last_time = time.time()

    def update(self, measurement):
        """
        根据当前测量值计算 PID 输出。

        :param measurement: 当前测量值
        :return: PID 输出值
        """
        current_time = time.time()
        delta_time = current_time - self._last_time
        if delta_time <= 0.0:
            delta_time = 1e-16  # 防止除以零

        error = self.setpoint - measurement
        self._integral += error * delta_time
        derivative = (error - self._previous_error) / delta_time

        output = self.Kp * error + self.Ki * self._integral + self.Kd * derivative

        # 限制输出
        output = max(self._min_output, min(output, self._max_output))

        # 保存状态
        self._previous_error = error
        self._last_time = current_time

        return output

    def set_setpoint(self, setpoint):
        """
        更新目标设定点。

        :param setpoint: 新的设定点
        """
        self.setpoint = setpoint
        self._integral = 0.0
        self._previous_error = 0.0

    def set_parameters(self, Kp, Ki, Kd):
        """
        更新 PID 参数。

        :param Kp: 比例增益
        :param Ki: 积分增益
        :param Kd: 微分增益
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
