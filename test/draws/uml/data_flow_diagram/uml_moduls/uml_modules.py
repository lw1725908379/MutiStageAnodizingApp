from graphviz import Digraph

# Create a new directed graph
dot = Digraph("UML_DataFlow", comment="UML Data Flow Diagram", format="png")

# Define modules with English names corresponding to the program's naming convention
dot.node("A", "GUI", shape="box", style="rounded,filled", color="lightblue")
dot.node("B", "ExperimentController", shape="box", style="rounded,filled", color="lightblue")
dot.node("C", "SerialManager", shape="box", style="rounded,filled", color="lightblue")
dot.node("D", "DataCollector", shape="box", style="rounded,filled", color="lightblue")
dot.node("E", "StorageManager", shape="box", style="rounded,filled", color="lightblue")
dot.node("F", "PlotWindow", shape="box", style="rounded,filled", color="lightblue")
dot.node("G", "ControlStrategy", shape="box", style="rounded,filled", color="lightblue")
dot.node("H", "PowerSupply", shape="box", style="rounded,filled", color="lightblue")

# Add data flow directions
dot.edges([
    ("A", "B"),  # GUI sends user inputs to ExperimentController
    ("B", "G"),  # ExperimentController calls ControlStrategy
    ("B", "C"),  # ExperimentController communicates with SerialManager
    ("C", "H"),  # SerialManager interacts with PowerSupply
    ("H", "D"),  # PowerSupply sends data to DataCollector
    ("D", "E"),  # DataCollector sends data to StorageManager
    ("D", "F"),  # DataCollector sends data to PlotWindow for real-time visualization
    ("B", "D"),  # ExperimentController manages DataCollector
    ("G", "B"),  # ControlStrategy sends feedback signals to ExperimentController
])

# Render the image
output_file = dot.render("uml_data_flow", cleanup=True)
print(f"UML Data Flow Diagram has been successfully generated: {output_file}")
