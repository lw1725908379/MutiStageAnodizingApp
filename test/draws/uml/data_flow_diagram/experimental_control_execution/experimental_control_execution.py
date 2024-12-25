from graphviz import Digraph

# Create a new directed graph
dot = Digraph("ExperimentControlExecution", comment="Data Flow for Experiment Control Execution", format="png")

# Define nodes
dot.node("A", "Load Experiment\nParameters (CSV)", shape="box", style="rounded,filled", color="lightblue")
dot.node("B", "Initialize System\nComponents", shape="box", style="rounded,filled", color="lightblue")
dot.node("C", "Experiment Controller", shape="ellipse", style="filled", color="lightgrey")
dot.node("D", "Control Strategy\n(Feedforward/Feedback)", shape="box", style="rounded,filled", color="lightgrey")
dot.node("E", "Data Collector", shape="ellipse", style="filled", color="lightgrey")
dot.node("F", "Storage Manager", shape="ellipse", style="filled", color="lightgreen")
dot.node("G", "Plot Window", shape="ellipse", style="filled", color="lightgreen")
dot.node("H", "Execute Experiment", shape="box", style="rounded,filled", color="lightblue")

# Add datasets flow directions
dot.edges([
    ("A", "B"),  # Load parameters to initialize components
    ("B", "C"),  # Initialize experiment controller
    ("C", "D"),  # Controller interacts with control strategy
    ("C", "E"),  # Controller interacts with datasets collector
    ("E", "F"),  # Data collector stores datasets in storage manager
    ("E", "G"),  # Data collector sends datasets to plot window for visualization
    ("C", "H"),  # Controller executes the experiment
])

# Render the image
output_file = dot.render("experiment_control_execution", cleanup=True)
print(f"Experiment Control Execution Data Flow Diagram has been successfully generated: {output_file}")
