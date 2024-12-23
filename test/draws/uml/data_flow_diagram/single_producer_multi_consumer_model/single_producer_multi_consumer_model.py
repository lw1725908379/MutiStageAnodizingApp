from graphviz import Digraph

# Initialize the directed graph
dot = Digraph(format='png', engine='dot')

# Set graph resolution
dot.attr(dpi='1000')  # Set DPI for high resolution

# Set graph attributes
dot.attr(rankdir='LR', fontsize='14')  # Adjust fontsize for better clarity

# Nodes
dot.node('P', 'Producer', shape='ellipse', style='filled', color='lightblue', fontsize='14')
dot.node('Q1', 'Queue 1\n(Data Queue)', shape='box', style='filled', color='lightgrey', fontsize='14')
dot.node('Q2', 'Queue 2\n(Control Queue)', shape='box', style='filled', color='lightgrey', fontsize='14')
dot.node('C1', 'Consumer 1\n(Storage)', shape='ellipse', style='filled', color='lightgreen', fontsize='14')
dot.node('C2', 'Consumer 2\n(Plotting)', shape='ellipse', style='filled', color='lightgreen', fontsize='14')

# Edges
dot.edge('P', 'Q1', label='Collected Data', fontsize='12')
dot.edge('P', 'Q2', label='Control Signals', fontsize='12')
dot.edge('Q1', 'C1', label='Stored in CSV', fontsize='12')
dot.edge('Q1', 'C2', label='Realtime Plot', fontsize='12')

# Render the graph to file
file_path = '/mnt/data/single_producer_multi_consumer_high_res'
dot.render(file_path, format='png', cleanup=True)
