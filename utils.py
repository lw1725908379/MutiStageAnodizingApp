import logging
import traceback

def handle_exception(e, context=""):
    """
    Handle an exception by logging its details and stack trace.

    Args:
        e (Exception): The exception instance to handle.
        context (str): Context or additional information about where the exception occurred.
    """
    logging.error(f"Exception occurred in {context}: {str(e)}")
    logging.debug("Stack trace:", exc_info=True)  # Log the stack trace at debug level for more detailed information
