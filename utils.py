# utils.py
import logging
from tkinter import messagebox

def handle_exception(e, context=""):
    """Handle exceptions by logging and showing a message box."""
    logging.exception(f"Exception in {context}: {e}")
    messagebox.showerror("Error", f"An error occurred in {context}:\n{e}")
