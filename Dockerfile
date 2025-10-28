# 使用 Python 3.11 基础镜像
FROM python:3.11

# 设置工作目录
WORKDIR /app

# 安装所需模块
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 将代码文件夹挂载到容器中
COPY . /app

# 暴露默认端口
EXPOSE 9000

# 启动 Flask 服务
#CMD ["flask", "run"]
CMD ["python", "main.py"]
