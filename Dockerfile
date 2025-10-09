FROM docker.m.daocloud.io/library/python:3.8-bullseye

# 直接装Python依赖（此时opencv是headless版本，无libGL依赖）
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码和启动命令
COPY . .
# 启动时通过 "docker run 镜像名 --step graph" 传递步骤
ENTRYPOINT ["python"]

# 默认显示帮助（可选）
CMD ["--help"]
