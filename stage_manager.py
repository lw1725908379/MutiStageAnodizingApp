import logging

class StageManager:
    """
    Stage Manager for managing experimental stages.
    This class provides methods to add, delete, and retrieve stages for experiments.
    """

    def __init__(self):
        """Initialize the Stage Manager with an empty stage list."""
        self.stages = []

    def add_stage(self, voltage_start, voltage_end, time_duration):
        """
        Add a new stage to the experiment.

        Args:
            voltage_start (float): The starting voltage for the stage.
            voltage_end (float): The ending voltage for the stage.
            time_duration (float): The duration of the stage in seconds.

        Returns:
            dict: The newly added stage as a dictionary.
        """
        if voltage_start < 0 or voltage_end < 0 or time_duration <= 0:
            raise ValueError("Voltage and time values must be positive.")

        stage = {
            "voltage_start": voltage_start,
            "voltage_end": voltage_end,
            "time": time_duration
        }
        self.stages.append(stage)
        logging.info(f"Added experiment stage: {stage}")
        return stage

    def delete_stage(self, indices):
        """
        Delete stages by their indices.

        Args:
            indices (list[int]): A list of indices of the stages to delete.

        Returns:
            None
        """
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.stages):
                removed_stage = self.stages.pop(index)
                logging.info(f"Deleted experiment stage: {removed_stage}")
            else:
                logging.warning(f"Invalid stage index: {index}. Skipped deletion.")

    def get_stages(self):
        """
        Get the list of all stages.

        Returns:
            list[dict]: A list of stages, where each stage is a dictionary.
        """
        return self.stages
