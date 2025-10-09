import networkx as nx
from networkx.readwrite import json_graph
from pyvis.network import Network
import json

# 1. 加载图数据（同上）
with open("a.json", "r") as f:
    json_data = json.load(f)
graph = json_graph.node_link_graph(json_data, directed=True, multigraph=True)

# 2. 初始化 Pyvis 网络（设置尺寸、标题）
net = Network(
    height="800px", width="100%",
    directed=True,  # 有向图需开启
    notebook=False,  # 本地运行设为 False，Jupyter 中设为 True
    cdn_resources="remote",  # 加载远程资源（避免本地依赖）
    heading="Chemputer Hardware Graph (Interactive)" 
)
# net.set_title("Chemputer Hardware Graph (Interactive)")

# 3. 添加节点（含属性信息，点击节点可查看）
for node in graph.nodes:
    # 提取节点属性（如类型、体积、当前状态）
    node_attrs = graph.nodes[node]
    # 节点标签：显示节点 ID，悬停显示属性
    label = f"{node}\nType: {node_attrs.get('type', 'N/A')}"
    # 添加节点（自定义颜色、大小）
    net.add_node(
        n_id=node,  # ✅ 正确：必填参数 n_id（节点唯一标识）
        label=label,
        size=15 if node_attrs.get("type") == "valve" else 25,
        color=node_attrs.get("color", "#FF6B6B")
    )

# 4. 添加边（含端口等属性）
for u, v, edge_data in graph.edges(data=True):
    # 边标签：显示端口信息（如 "(out_main, in_1)"）
    edge_label = edge_data.get("port", "N/A")
    net.add_edge(
        source=u,  # 起点
        to=v,      # 终点
        label=edge_label,
        arrowStrikethrough=False  # 箭头不穿过标签
    )

# 5. 配置布局（Pyvis 自动优化，可手动调整）
net.barnes_hut()  # 力导向布局，适合大规模图
# （可选）添加图例（需手动定义）
# net.add_legend(
#     legend_items=[
#         {"label": "Reactor", "color": "#FF6B6B"},
#         {"label": "Pump", "color": "#4ECDC4"},
#         {"label": "Valve", "color": "#45B7D1"}
#     ]
# )

legend_nodes = [
    {"id": "legend_reactor", "label": "Reactor", "color": "#FF6B6B"},
    {"id": "legend_pump", "label": "Pump", "color": "#4ECDC4"},
    {"id": "legend_valve", "label": "Valve", "color": "#45B7D1"}
]

# 添加图例节点（位置固定在右下角）
for idx, item in enumerate(legend_nodes):
    net.add_node(
        n_id=item["id"],
        label=item["label"],
        color=item["color"],
        size=20,
        x=900 + idx * 100,  # 固定X坐标（靠右）
        y=500,  # 固定Y坐标（靠下）
        physics=False  # 关闭物理引擎，避免被其他节点带动
    )

# 添加图例标题
net.add_node(
    n_id="legend_title",
    label="图例",
    color="black",
    size=25,
    x=850,
    y=450,
    physics=False
)


# 6. 生成 HTML 文件并打开
net.write_html("graph_interactive.html")
print("Interactive graph saved to graph_interactive.html")