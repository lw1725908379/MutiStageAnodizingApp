# stage_manager.py
import logging

class StageManager:
    """Stage Manager for managing experimental stages."""

    def __init__(self):
        self.stages = []

    def add_stage(self, voltage_start, voltage_end, time_duration):
        """Add a new stage to the experiment."""
        stage = {
            "voltage_start": voltage_start,
            "voltage_end": voltage_end,
            "time": time_duration
        }
        self.stages.append(stage)
        logging.info(f"Added experiment stage: {stage}")
        return stage

    def delete_stage(self, indices):
        """Delete stages by indices."""
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.stages):
                removed_stage = self.stages.pop(index)
                logging.info(f"Deleted experiment stage: {removed_stage}")

    def get_stages(self):
        """Get the list of stages."""
        return self.stages
