import networkx as nx
import matplotlib.pyplot as plt
from networkx.readwrite import json_graph
import json
import math
import textwrap
from collections import defaultdict

src = "chem_yan.json"

# --------------------------
# 1. 数据加载与关键信息提取
# --------------------------
with open(src, "r") as f:
    json_data = json.load(f)
graph = json_graph.node_link_graph(
    json_data, directed=True, multigraph=True, edges="links"
)
nodes = list(graph.nodes)
node_count = len(nodes)

# 提取节点类型、连接关系（用于归簇）
node_type_dict = {node: graph.nodes[node].get("type", "default") for node in nodes}
# 构建节点连接字典：key=节点，value=直接连接的所有节点
node_connections = defaultdict(list)
for u, v, _ in graph.edges:  # 多重图，边格式为(u, v, edge_id)
    node_connections[u].append(v)
    node_connections[v].append(u)  # 双向记录，确保无向连接也能识别

# --------------------------
# 2. 核心步骤：Valve为中心的簇划分
# --------------------------
# 2.1 提取所有Valve节点（作为簇中心）
valve_centers = [node for node in nodes if node_type_dict[node] == "valve"]
# 若没有Valve，用default节点当中心（避免报错）
if not valve_centers:
    valve_centers = [nodes[0]]  # 降级方案：用第一个节点当中心

# 2.2 设备归簇：将非Valve设备分配到有连接的Valve簇
# 格式：cluster_dict[valve_center] = [所属设备1, 所属设备2, ...]
cluster_dict = defaultdict(list)
# 已分配的非Valve节点（避免重复分配）
assigned_nodes = set()

# 遍历每个Valve簇中心，找其直接连接的非Valve设备
for valve in valve_centers:
    # 找到与当前Valve直接连接的非Valve节点
    connected_nodes = [
        node
        for node in node_connections[valve]
        if node_type_dict[node] != "valve" and node not in assigned_nodes
    ]
    # 将这些节点分配给当前Valve簇
    cluster_dict[valve].extend(connected_nodes)
    assigned_nodes.update(connected_nodes)

# 处理未分配的非Valve节点（无任何Valve连接，归为"默认簇"）
unassigned_nodes = [
    node for node in nodes if node not in valve_centers and node not in assigned_nodes
]
if unassigned_nodes:
    # 若有未分配节点，新增一个"默认簇"（用最后一个Valve当中心，或新建虚拟中心）
    default_center = valve_centers[-1] if valve_centers else nodes[0]
    cluster_dict[default_center].extend(unassigned_nodes)

# --------------------------
# 3. 簇状布局计算（Valve中心+簇内放射+簇间均匀分布）
# --------------------------
pos = {}  # 最终节点位置字典

# 3.1 簇间间距配置（控制簇与簇的距离，避免拥挤）
cluster_horizontal_gap = 8.0  # 簇之间的横向间距（核心参数，可调整）
cluster_vertical_range = 3.0  # 簇内设备的纵向分布范围（避免簇过高）

# 3.2 为每个簇分配整体位置（横向排列簇，如Valve1在x=2，Valve2在x=10，Valve3在x=18...）
for cluster_idx, (valve_center, cluster_nodes) in enumerate(cluster_dict.items()):
    # 1. 确定当前簇的中心X坐标（横向均匀分布）
    cluster_center_x = 2.0 + cluster_idx * cluster_horizontal_gap  # 第一个簇从x=2开始
    cluster_center_y = 0.0  # 所有簇的Y坐标统一为0（横向排列，避免上下偏移）

    # 2. 设置Valve中心节点的位置（簇的绝对中心）
    pos[valve_center] = (cluster_center_x, cluster_center_y)

    # 3. 簇内非Valve设备：围绕Valve呈小范围放射状分布（避免簇内拥挤）
    cluster_size = len(cluster_nodes)  # 簇内设备数量
    if cluster_size == 0:
        continue  # 无设备的簇，跳过

    # 簇内放射方向：4个方向（上、右、下、左）循环，避免重叠（比8方向更紧凑）
    cluster_directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # 上、右、下、左
    # 簇内设备与Valve的距离（固定，确保簇内紧凑）
    cluster_radius = 1.5  # 核心参数：越小簇越紧凑

    # 为簇内每个设备分配位置
    for idx, device_node in enumerate(cluster_nodes):
        # 循环选择方向（0→上，1→右，2→下，3→左，4→上...）
        dir_idx = idx % len(cluster_directions)
        dx, dy = cluster_directions[dir_idx]
        # 计算设备节点位置（Valve中心 + 方向*距离）
        pos[device_node] = (
            cluster_center_x + dx * cluster_radius,
            cluster_center_y + dy * cluster_radius,
        )

# --------------------------
# 4. 视觉样式优化（强化簇与簇的区分）
# --------------------------
# 4.1 节点大小：Valve（簇中心）最大，其他设备按类型区分
node_size_map = {
    "valve": 1500,  # Valve簇中心：最大（视觉焦点）
    "reactor": 1000,  # 反应器：次大
    "pump": 900,  # 泵：中等
    "flask": 900,  # 烧瓶：中等
    "default": 800,  # 其他：较小
    "waste": 800,  # 其他：较小
    "heater": 800,  # 其他：较小
    "vacuum": 800,  # 其他：较小
}
node_sizes = [node_size_map[node_type_dict[node]] for node in nodes]

# 4.2 节点颜色：Valve统一红色（突出中心），其他设备按类型区分，同簇色调协调
node_color_map = {
    "valve": "#E74C3C",  # Valve簇中心：红色（醒目）
    "reactor": "#3498DB",  # 反应器：蓝色（与Valve红色对比）
    "pump": "#2ECC71",  # 泵：绿色
    "flask": "#F39C12",  # 烧瓶：橙色
    "default": "#95A5A6",  # 其他：灰色
    "waste": "#95A5A6",  # 其他：灰色
    "heater": "#95A5A6",  # 其他：灰色
    "vacuum": "#95A5A6",  # 其他：灰色
}
node_colors = [node_color_map[node_type_dict[node]] for node in nodes]

# 4.3 节点边框：Valve加粗（强化中心地位）
node_border_widths = [4.0 if node_type_dict[node] == "valve" else 2.0 for node in nodes]


# --------------------------
# 5. 边样式优化（簇内边粗，簇间边细，避免混乱）
# --------------------------
# 5.1 判断边是否为"簇内边"（连接同一Valve簇的节点）
def is_intra_cluster_edge(u, v):
    """判断边u-v是否在同一簇内"""
    # 找到u所属的簇中心
    u_cluster = None
    for valve, cluster_nodes in cluster_dict.items():
        if u == valve or u in cluster_nodes:
            u_cluster = valve
            break
    # 找到v所属的簇中心
    v_cluster = None
    for valve, cluster_nodes in cluster_dict.items():
        if v == valve or v in cluster_nodes:
            v_cluster = valve
            break
    return u_cluster == v_cluster  # 同一簇返回True


# 5.2 边的宽度：簇内边粗（突出簇内连接），簇间边细（弱化跨簇干扰）
edge_widths = []
edge_colors = []
for u, v, _ in graph.edges:
    if is_intra_cluster_edge(u, v):
        edge_widths.append(3.0)  # 簇内边：粗
        edge_colors.append("#2C3E50CC")  # 深灰半透明（清晰）
    else:
        edge_widths.append(1.2)  # 簇间边：细
        edge_colors.append("#7F8C8D80")  # 浅灰半透明（弱化）

# 5.3 箭头：簇内边箭头更大（突出簇内流向）
edge_arrowsizes = [25 if w == 3.0 else 15 for w in edge_widths]

# --------------------------
# 6. 标签优化（避免簇内标签重叠）
# --------------------------
# 6.1 标签换行：按12字符拆分（簇内空间有限，避免过长）
wrapped_labels = {node: textwrap.fill(str(node), width=12) for node in nodes}

# 6.2 标签位置：簇内设备标签向远离Valve的方向偏移（避免遮挡）
label_pos = {}
label_offset = 0.4  # 标签与节点的间距
for node in nodes:
    x, y = pos[node]
    # 若为Valve（簇中心）：标签放在正下方（不遮挡周围设备）
    if node_type_dict[node] == "valve":
        label_pos[node] = (x, y - label_offset - 0.2)  # 额外下移0.2，远离簇内设备
    else:
        # 非Valve设备：找到其所属Valve簇中心，标签向远离中心的方向偏移
        cluster_center = None
        for valve, cluster_nodes in cluster_dict.items():
            if node in cluster_nodes or node == valve:
                cluster_center = valve
                break
        if cluster_center:
            cx, cy = pos[cluster_center]
            # 计算设备相对于Valve的方向（远离方向偏移标签）
            if abs(x - cx) > abs(y - cy):  # 水平方向（左/右）
                label_x = x + label_offset if x > cx else x - label_offset
                label_y = y
            else:  # 垂直方向（上/下）
                label_x = x
                label_y = y + label_offset if y > cy else y - label_offset
            label_pos[node] = (label_x, label_y)
        else:
            label_pos[node] = (x + label_offset, y)  # 默认右移

# 6.3 标签字体：Valve标签最大，其他按节点大小适配
label_font_sizes = [12 if node_type_dict[node] == "valve" else 10 for node in nodes]

# --------------------------
# 7. 画布与最终绘制（适配簇状布局）
# --------------------------
# 7.1 画布大小：按簇的分布范围自适应（避免留白）
min_x = min(pos[node][0] for node in nodes) - 2.0
max_x = max(pos[node][0] for node in nodes) + 2.0
min_y = min(pos[node][1] for node in nodes) - 2.0
max_y = max(pos[node][1] for node in nodes) + 2.0
fig_width = max(12, (max_x - min_x) * 0.9)  # 横向足够宽，容纳所有簇
fig_height = max(6, (max_y - min_y) * 1.5)  # 纵向适中，避免过高
plt.figure(figsize=(fig_width, fig_height))
ax = plt.gca()

# 7.2 隐藏坐标轴边框和刻度（干净的簇状图）
for spine in ax.spines.values():
    spine.set_visible(False)
ax.set_xticks([])
ax.set_yticks([])

# 7.3 绘制节点（Valve中心突出）
nx.draw_networkx_nodes(
    graph,
    pos,
    node_size=node_sizes,
    node_color=node_colors,
    alpha=0.9,
    edgecolors="black",
    linewidths=node_border_widths,
)

# 7.4 绘制边（簇内/簇间区分明显）
nx.draw_networkx_edges(
    graph,
    pos,
    arrowstyle="->",
    arrowsize=edge_arrowsizes,
    edge_color=edge_colors,
    width=edge_widths,
    alpha=0.9,
    connectionstyle="arc3,rad=0.03",  # 轻微弧度，避免簇内边重叠
)

# 7.5 绘制标签（Valve标签突出，其他不重叠）
for node in nodes:
    plt.text(
        label_pos[node][0],
        label_pos[node][1],
        wrapped_labels[node],
        fontsize=label_font_sizes[list(nodes).index(node)],
        fontweight="bold",
        ha="center",
        va="center",
        bbox=dict(
            boxstyle="round,pad=0.2", facecolor="white", alpha=0.9
        ),  # 白色背景，避免被边遮挡
    )

# 7.6 添加簇区分辅助线（可选，用虚线框住每个簇，更清晰）
for cluster_idx, (valve_center, cluster_nodes) in enumerate(cluster_dict.items()):
    cx, cy = pos[valve_center]
    # 簇的虚线框范围（比簇内设备大0.5）
    box_x_min = cx - cluster_radius - 0.5
    box_x_max = cx + cluster_radius + 0.5
    box_y_min = cy - cluster_radius - 0.5
    box_y_max = cy + cluster_radius + 0.5
    # 绘制虚线框（灰色，不干扰主体）
    rect = plt.Rectangle(
        (box_x_min, box_y_min),
        box_x_max - box_x_min,
        box_y_max - box_y_min,
        fill=False,
        edgecolor="#BDC3C7",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
    )
    ax.add_patch(rect)

# 7.7 保存图片（高分辨率，无多余留白）
plt.xlim(min_x, max_x)
plt.ylim(min_y, max_y)
plt.tight_layout()
plt.savefig("graph_valve_cluster.png", dpi=300, bbox_inches="tight", facecolor="white")
plt.close()

print(f"簇状拓扑图生成完成！共{len(valve_centers)}个Valve簇，已保存为 graph_valve_cluster.png")
