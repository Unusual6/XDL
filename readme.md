<!-- 1 建图-->
docker run --rm xdl_v1:latest -m xdl.scripts.test --step graph

<!-- 2 编译-->
docker run --rm xdl_v1:latest -m xdl.scripts.test --step compile

<!-- 3 运行-->
docker run --rm xdl_v1:latest -m xdl.scripts.test --step run

<!-- 4 可视化-->
docker run --rm xdl_v1:latest tools/vis_graph.py