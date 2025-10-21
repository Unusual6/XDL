import json
import matplotlib.pyplot as plt
import networkx as nx

# ========== Step 1: 加载你的 JSON ==========
src = "chem_yan.json"

# --------------------------
# 1. 数据加载与关键信息提取
# --------------------------
with open(src, "r") as f:
    data = json.load(f)

# data = {
#     "directed": True,
#     "multigraph": True,
#     # 这里粘贴你的完整 JSON 数据 ↓↓↓
#     "nodes": [...],  # ← 替换成你的完整 nodes 数组
#     "links": [...]   # ← 替换成你的完整 links 数组
# }

# ========== Step 2: 构建图结构 ==========
G = nx.MultiDiGraph()

# 添加节点
for node in data["nodes"]:
    G.add_node(
        node["id"],
        pos=(node["x"], node["y"]),
        type=node["type"],
        label=node.get("label", node["id"]),
    )

# 添加边
for link in data["links"]:
    G.add_edge(link["source"], link["target"])

# ========== Step 3: 提取布局坐标 ==========
# 添加节点
for node in data["nodes"]:
    x = node.get("x", 0)
    y = node.get("y", 0)
    G.add_node(
        node["id"],
        pos=(float(x), float(y)),  # 强制转为 float
        type=node.get("type", "unknown"),
        label=node.get("label", node["id"]),
    )
import math
import math
import matplotlib.pyplot as plt
import networkx as nx

# ========== Step X: 自定义以 reactor 为中心的紧凑布局 ==========
reactors = [n for n in G.nodes if G.nodes[n].get("type") == "reactor"]
center = reactors[0] if reactors else list(G.nodes)[0]

pos = {}
pos[center] = (0, 0)

valves = [n for n in G.nodes if G.nodes[n].get("type") == "valve"]

# ---- 层级半径设置（紧凑比例） ----
R_valve = 5  # reactor 到 valve 距离
R_local = 1.8  # valve 簇内部节点距离
R_outer = R_valve + 3  # 孤立节点外圈

# ---- valve 排布在中心周围 ----
for i, v in enumerate(valves):
    angle = 2 * math.pi * i / len(valves)
    pos[v] = (R_valve * math.cos(angle), R_valve * math.sin(angle))

# ---- valve 的邻居围绕局部环 ----
for v in valves:
    neighbors = list(G.neighbors(v)) + [u for u in G.predecessors(v)]
    neighbors = list(set(neighbors) - {v, center})
    for j, n in enumerate(neighbors):
        if n not in pos:
            angle = 2 * math.pi * j / max(len(neighbors), 1)
            pos[n] = (
                pos[v][0] + R_local * math.cos(angle),
                pos[v][1] + R_local * math.sin(angle),
            )

# ---- 未放置节点（外圈） ----
unplaced = [n for n in G.nodes if n not in pos]
for i, n in enumerate(unplaced):
    angle = 2 * math.pi * i / max(len(unplaced), 1)
    pos[n] = (R_outer * math.cos(angle), R_outer * math.sin(angle))

print(f"✅ 紧凑布局完成，共 {len(pos)} 个节点。")

# ========== Step Y: 绘制（放大比例 + 优化外观） ==========
plt.figure(figsize=(10, 8))
plt.axis("off")

# ---- 放大节点尺寸比例 ----
node_types = {
    "reactor": {"color": "#ff7f0e", "shape": "o", "size": 2500},
    "valve": {"color": "#1f77b4", "shape": "s", "size": 1600},
    "pump": {"color": "#2ca02c", "shape": "D", "size": 1500},
    "flask": {"color": "#9467bd", "shape": "o", "size": 1300},
    "waste": {"color": "#d62728", "shape": "^", "size": 1400},
    "heater": {"color": "#8c564b", "shape": "p", "size": 1500},
    "vacuum": {"color": "#17becf", "shape": "h", "size": 1500},
}

# ---- 绘制节点 ----
for t, style in node_types.items():
    nodelist = [n for n in G.nodes if G.nodes[n].get("type") == t]
    if nodelist:
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=nodelist,
            node_color=style["color"],
            node_shape=style["shape"],
            node_size=style["size"],
            alpha=0.9,
            label=t,
        )

# ---- 绘制边 ----
nx.draw_networkx_edges(
    G,
    pos,
    arrows=True,
    arrowstyle="-|>",
    arrowsize=18,
    width=2,
    edge_color="gray",
    alpha=0.7,
)

# ---- 绘制标签 ----
nx.draw_networkx_labels(
    G,
    pos,
    labels={n: G.nodes[n].get("label", n) for n in G.nodes},
    font_size=9,
    font_color="black",
)

# ---- 背景圈（可选） ----
circle = plt.Circle(
    (0, 0), R_valve + 1, color="lightgray", fill=False, linestyle="--", alpha=0.3
)
plt.gca().add_artist(circle)

plt.legend(fontsize=8, loc="upper right")
plt.tight_layout()
plt.savefig("graph_t.png", dpi=400, bbox_inches="tight")
# plt.show()

print("✅ 拓扑图已保存为 graph_1.png")
