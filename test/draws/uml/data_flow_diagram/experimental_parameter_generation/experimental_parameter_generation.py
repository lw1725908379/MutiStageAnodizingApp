from graphviz import Digraph

# Create a new directed graph
dot = Digraph("ExperimentParameterGeneration", comment="Data Flow for Experiment Parameter Generation", format="png")

# Define nodes
dot.node("A", "Input Parameter\nRanges", shape="box", style="rounded,filled", color="lightblue")
dot.node("B", "Generate Voltage\nCombinations", shape="box", style="rounded,filled", color="lightgrey")
dot.node("C", "Calculate Duration", shape="box", style="rounded,filled", color="lightgrey")
dot.node("D", "Combine with Kp\nValues", shape="box", style="rounded,filled", color="lightgrey")
dot.node("E", "Generate\nExperiment Configurations", shape="box", style="rounded,filled", color="lightgrey")
dot.node("F", "Write to CSV\nFile", shape="box", style="rounded,filled", color="lightgreen")

# Add datasets flow directions
dot.edges([
    ("A", "B"),  # Input parameters are used to generate voltage combinations
    ("B", "C"),  # Voltage combinations are used to calculate duration
    ("C", "D"),  # Duration is combined with Kp values
    ("D", "E"),  # Combine all datasets to create experiment configurations
    ("E", "F"),  # Write the experiment configurations to a CSV file
])

# Render the image
output_file = dot.render("experiment_parameter_generation", cleanup=True)
print(f"Experiment Parameter Generation Data Flow Diagram has been successfully generated: {output_file}")
