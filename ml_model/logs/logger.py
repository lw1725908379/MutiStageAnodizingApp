import logging
import os

def setup_logging(log_file="E:\\WORKS\\py\\projects\\MultiStageAnodizingApp\\ml_model\\logs\\logs.txt"):
    """
    Configure logging for the entire project.

    Parameters:
    - log_file: str, path to the log file.

    Returns:
    - logger: Configured logging instance.
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)  # Ensure the log directory exists

    logger = logging.getLogger(__name__)
    if not logger.handlers:
        # File handler to save logs to a file
        file_handler = logging.FileHandler(log_file, mode='a')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Stream handler to also log to console
        stream_handler = logging.StreamHandler()
        stream_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(stream_formatter)
        logger.addHandler(stream_handler)

    logger.setLevel(logging.INFO)
    return logger
