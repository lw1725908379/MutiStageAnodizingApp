from graphviz import Digraph

# Create a new directed graph
dot = Digraph("RealtimePlottingDataFlow", comment="Data Flow for Real-time Plotting", format="png")

# Define nodes
dot.node("A", "Experiment Controller", shape="ellipse", style="filled", color="lightgrey")
dot.node("B", "Data Collector", shape="ellipse", style="filled", color="lightblue")
dot.node("C", "Plotting Queue", shape="box", style="rounded,filled", color="lightgrey")
dot.node("D", "Plot Window", shape="ellipse", style="filled", color="lightgreen")
dot.node("E", "Data Processor", shape="ellipse", style="filled", color="lightblue")
dot.node("F", "Plot Refresh Loop", shape="box", style="rounded,filled", color="lightgrey")

# Add datasets flow directions
dot.edge("A", "B", label="Trigger Data Collection")  # Experiment controller triggers datasets collection
dot.edge("B", "C", label="Collected Data")          # Data collector places datasets in plotting queue
dot.edge("C", "E", label="Dequeued Data")           # Plotting queue sends datasets to datasets processor
dot.edge("E", "D", label="Processed Data")          # Data processor sends processed datasets to the plot window
dot.edge("D", "F", label="Plot Commands")           # Plot window executes real-time plot updates

# Render the image
output_file = dot.render("realtime_plotting_data_flow", cleanup=True)
print(f"Real-time Plotting Data Flow Diagram has been successfully generated: {output_file}")
