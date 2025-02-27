
## 🚀 一款用于自动化 LayerEdge 节点操作的 Python 机器人。

### 功能特点

    🔄 每12小时自动重启节点
    ✅ 自动完成每日签到
    💎 积分追踪管理
    🌐 支持代理功能
    📊 随机UA头

### 安装步骤

    克隆仓库


```
git clone https://github.com/pig2048/LayerEdge-Bot.git
cd LayerEdge-Bot
```

    创建虚拟环境

```
python -m venv venv
./venv/Scripts/activate (windows)
source venv/bin/activate (linux)
```

    安装依赖

```
pip install -r requirements.txt
```

    配置机器人

在accounts.txt中添加你的钱包私钥，每行一个
在proxy.txt中添加你的代理，每行一个（格式：http://ip:port）

    启动机器人

```
python main.py
```

