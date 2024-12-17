import logging
import traceback

def handle_exception(e, context=""):
    """Handle an exception by logging its details."""
    logging.error(f"Exception in {context}: {e}")
    traceback.print_exc()
