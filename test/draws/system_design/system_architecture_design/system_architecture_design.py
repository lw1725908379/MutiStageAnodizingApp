from graphviz import Digraph

# Initialize the directed graph
dot = Digraph("Three_Layer_Architecture", comment="Three-Layer Architecture", format="png")
dot.attr(rankdir="TB", dpi="300")

# Define styles for nodes
dot.attr("node", shape="box", style="rounded,filled", fontsize="10", fontname="SimSun")

# Add layers
dot.node("GUI", "图形用户界面 (GUI)", style="filled", color="lightblue")
dot.node("Controller", "实验控制器\n(Controller)", style="filled", color="lightgreen")
dot.node("Logic", "逻辑层\n(Logic Layer)\n包含控制逻辑", style="filled", color="lightyellow")
dot.node("Data", "数据存储与管理\n(Data Layer)", style="filled", color="lightpink")

# Add database or storage
dot.node("Database", "数据库 (CSV 文件存储)", shape="box", style="dashed", color="grey")

# Add arrows between layers
dot.edge("GUI", "Controller", label="用户输入", fontsize="10", fontname="SimSun")
dot.edge("Controller", "Logic", label="控制信号", fontsize="10", fontname="SimSun")
dot.edge("Logic", "Data", label="存储数据", fontsize="10", fontname="SimSun")
dot.edge("Data", "Database", label="写入数据", fontsize="10", fontname="SimSun")

# Render the graph to file
file_path = "three_layer_system_diagram"
dot.render(file_path, format="png", cleanup=True)
print(f"Three-Layer Architecture Diagram has been generated at {file_path}.png")
