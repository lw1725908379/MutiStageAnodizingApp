from graphviz import Digraph

# Initialize the directed graph for the flowchart
dot = Digraph("Experiment_Flowchart", comment="Experiment Flowchart", format="png")
dot.attr(dpi="300")

# Set global node attributes for consistent styling
dot.attr("node", shape="box", style="rounded", fontsize="12", fontname="SimSun")

# Define the nodes of the flowchart
dot.node("Start", "实验初始化")
dot.node("Config", "实验参数配置")
dot.node("Execution", "实验执行")
dot.node("Processing", "数据采集与处理")
dot.node("Storage", "结果存储与绘图")
dot.node("End", "实验完成")

# Add directional edges between nodes to indicate flow
dot.edge("Start", "Config", label="")
dot.edge("Config", "Execution", label="")
dot.edge("Execution", "Processing", label="")
dot.edge("Processing", "Storage", label="")
dot.edge("Storage", "End", label="")

# Render the graph to a file
dot.render("experiment_flowchart", cleanup=True)
