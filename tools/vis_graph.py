import networkx as nx
import matplotlib.pyplot as plt
from networkx.readwrite import json_graph
import json
import math
import textwrap

# 1. 加载数据
with open("a.json", "r") as f:
    json_data = json.load(f)
graph = json_graph.node_link_graph(json_data, directed=True, multigraph=True)
nodes = list(graph.nodes)
node_count = len(nodes)

# 2. 米字8方向定义
angles = [0, math.pi/4, math.pi/2, 3*math.pi/4, 
          math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4]
directions = [(math.cos(angle), math.sin(angle)) for angle in angles]

# 3. 紧凑布局核心调整：缩小布局范围，减少留白基础
pos = {}
if node_count > 0:
    center_node = nodes[0]
    pos[center_node] = (0, 0)
    
    nodes_remaining = nodes[1:]
    dir_index = 0
    max_radius = 3.0  # 关键1：缩小最大半径（原5.0→3.0），节点更集中
    base_step = 1.2   # 关键2：减小基础步长（原1.5→1.2），分支更紧凑
    nodes_per_dir = 3
    
    for i, node in enumerate(nodes_remaining):
        dir_level = (i // len(directions)) % nodes_per_dir + 1
        distance = min(base_step * dir_level, max_radius)  # 距离更短
        dx, dy = directions[dir_index]
        pos[node] = (dx * distance, dy * distance)
        dir_index = (dir_index + 1) % 8

# 4. 节点设置：增大尺寸，提升视觉占比
node_sizes = []
for node in graph.nodes:
    if node == nodes[0] and node_count > 0:
        # 关键3：中心节点更大（原800→1000，原600→800）
        node_sizes.append(1000 if node_count < 20 else 800)
    else:
        # 关键4：分支节点增大（原500→700，原350→500）
        node_sizes.append(700 if node_count < 20 else 500)

node_colors = []
for node in graph.nodes:
    node_type = graph.nodes[node].get("type", "default")
    color_map = {
        "reactor": "#FF6B6B",
        "pump": "#4ECDC4",
        "valve": "#45B7D1",
        "flask": "#FFC0CB",
        "default": "#999999"
    }
    if node == nodes[0] and node_count > 0:
        color = color_map.get(node_type, color_map["default"])
        node_colors.append(color.replace('#', '#CC'))
    else:
        node_colors.append(color_map.get(node_type, color_map["default"]))

# 5. 绘制图形：缩小画布+收紧边界
# 关键5：缩小画布尺寸（原10x10→8x8），减少空白区域
plt.figure(figsize=(8, 8))
ax = plt.gca()

# --------------------------
# 关键1：隐藏所有坐标轴黑色边框
# --------------------------
for spine in ax.spines.values():  # spine即上下左右四个边框
    spine.set_visible(False)
# 绘制节点（更大尺寸，视觉占比更高）
nx.draw_networkx_nodes(
    graph, pos,
    node_size=node_sizes,
    node_color=node_colors,
    alpha=0.9,
    edgecolors="black",
    linewidths=2.5  # 关键6：加粗节点边框（原2→2.5），更醒目
)

# 绘制边：加粗线条，提升存在感
nx.draw_networkx_edges(
    graph, pos,
    arrowstyle="->",
    arrowsize=18,  # 关键7：增大箭头（原15→18），更清晰
    edge_color="#333333",
    width=2.0,     # 关键8：加粗边（原1.5→2.0），减少纤细感
    alpha=0.8,
    connectionstyle="arc3,rad=0"
)

# 6. 标签优化：增大字体+减少偏移，贴近节点
# 6.1 换行宽度调整（原10→12），减少换行次数，标签更紧凑
wrapped_labels = {
    node: textwrap.fill(str(node), width=12)
    for node in graph.nodes
}

# 6.2 标签偏移减小（原0.3→0.2），贴近节点，减少空白
label_pos = {}
offset = 0.2  # 关键9：缩小标签与节点的距离
for node in graph.nodes:
    x, y = pos[node]
    if x > 0.1:
        label_pos[node] = (x + offset, y)
    elif x < -0.1:
        label_pos[node] = (x - offset, y)
    elif y > 0.1:
        label_pos[node] = (x, y + offset)
    elif y < -0.1:
        label_pos[node] = (x, y - offset)
    else:
        label_pos[node] = (x, y + offset)

# 6.3 标签字体增大（原最大10→12，最小6→8）
for node in graph.nodes:
    label_text = wrapped_labels[node]
    # 关键10：提升字体基数（原10→12），最小字体提高（原6→8）
    font_size = max(10, 12 - (len(label_text) // 5))
    plt.text(
        label_pos[node][0], label_pos[node][1],
        label_text,
        fontsize=font_size,
        fontweight="bold",
        ha="center",
        va="center"
    )

# 7. 保存：收紧坐标轴范围，彻底消除多余留白
plt.axis("on")
plt.grid(True, linestyle='--', alpha=0.3)
# 关键11：缩小坐标轴范围（原max_radius+1→max_radius+0.5），紧贴节点
plt.xlim(-max_radius-0.5, max_radius+0.5)
plt.ylim(-max_radius-0.5, max_radius+0.5)
# 关键12：关闭tight_layout的额外留白（或保留但配合范围收紧）
# plt.tight_layout(pad=0.5)  # pad控制画布边缘留白，0.5为最小合理值
plt.savefig("graph.png", dpi=300, bbox_inches="tight")
plt.close()