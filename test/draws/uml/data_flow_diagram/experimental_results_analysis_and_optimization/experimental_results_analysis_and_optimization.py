from graphviz import Digraph

# Create a new directed graph
dot = Digraph("ExperimentResultAnalysisOptimization", comment="Data Flow for Experiment Result Analysis and Optimization", format="png")

# Define nodes
dot.node("A", "Experiment Controller", shape="ellipse", style="filled", color="lightgrey")
dot.node("B", "Data Collector", shape="ellipse", style="filled", color="lightblue")
dot.node("C", "Storage Manager", shape="box", style="rounded,filled", color="lightgrey")
dot.node("D", "Result Database", shape="cylinder", style="filled", color="lightgrey")
dot.node("E", "Analysis Module", shape="ellipse", style="filled", color="lightgreen")
dot.node("F", "Optimization Algorithm", shape="ellipse", style="filled", color="lightyellow")
dot.node("G", "Updated Parameters", shape="box", style="rounded,filled", color="lightblue")

# Add datasets flow directions
dot.edge("A", "B", label="Control Signals")                # Experiment Controller triggers datasets collection
dot.edge("B", "C", label="Collected Data")                 # Data collected is passed to the Storage Manager
dot.edge("C", "D", label="Save to Database")               # Storage Manager saves datasets to the database
dot.edge("D", "E", label="Load Data for Analysis")         # Data from the database is sent to the Analysis Module
dot.edge("E", "F", label="Analysis Results")               # Analysis Module generates results for optimization
dot.edge("F", "G", label="Optimized Parameters")           # Optimization Algorithm generates updated parameters
dot.edge("G", "A", label="Feedback to Controller")         # Optimized parameters are fed back to the Experiment Controller

# Render the image
output_file = dot.render("experiment_result_analysis_optimization", cleanup=True)
print(f"Experiment Result Analysis and Optimization Data Flow Diagram has been successfully generated: {output_file}")
