import tkinter as tk
from gui import ExperimentGUI

def main():
    root = tk.Tk()
    app = ExperimentGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
