## 🚀 快速开始  
本程序提供`pip安装`和`打包程序安装`两种安装方式。

## 📦 pip安装(推荐)

### 1. 库文件下载
通过运行以下命令安装`LumAPI`库
```bash
pip install LumAPI
```
### 2. 配置lumerical路径
在安装完库后运行下面的命令即可打开lumerical路径配置页面
图形界面配置：
```bash
LumAPI
```
命令行配置：
```bash
LumAPI_CLI
```
### 3. 使用
通过下述代码即可调用 Lumerical API：
```python
from LumAPI import *

filename = 'simulation.fsp'
fdtd = lumapi.FDTD(filename)
fdtd.close()
```
或者不进行lumerical配置，直接传入lumerical路径：
```python
from LumAPI import *
lumerical_path = 'C:/Program Files/Lumerical'
version = 'v241'
fdtd = lumerical(lumerical_path=lumerical_path, version=version).FDTD(filename)
fdtd.close()
```
或者传入config.json路径：
```python
from LumAPI import *
config_path = './config.json'
fdtd = lumerical(config_path=config_path).FDTD(filename)
fdtd.close()
```
其中config.json文件内容如下：
```python
{
    "lumerical_path": "C:\\Program Files\\Lumerical",
    "version": "v241"
}
```

## 📦 打包程序安装

### 1. 获取程序
请前往 [Releases 页面](releases) 下载适配您操作系统（Windows/Linux）及架构（AMD64/ARM64）的预编译程序。`LumAPI_GUI`为带图形界面版本的配置程序，`LumAPI_CLI`为无图形界面版本的命令行配置工具，二者选择其一即可。

### 2. 初始化配置
运行下载的配置工具（`LumAPI_GUI` 或 `LumAPI_CLI`），完成 Lumerical API 的路径挂载：
1.  **路径扫描**：程序启动后将自动检索 Lumerical 安装目录；若自动检索失败，支持手动输入或浏览选择。
    > **注意**：选定的根目录下必须包含符合版本规范的文件夹（例如 `v241` 对应 24R1 版本）。
2.  **验证与保存**：程序会自动校验路径有效性。校验通过后，点击 **“保存配置”** 即可锁定环境设置。

---

## 🛠️ 集成模式

配置完成后，本工具提供两种方式将 Lumerical API (`LumAPI`) 接入您的开发环境。

### 方式一：全局集成（推荐）
适用于希望在任意路径下直接调用 `LumAPI` 的场景。
1.  **选择解释器**：在配置工具中指定您日常使用的 Python 解释器路径（支持自动扫描 Conda/System Python）。
2.  **一键注入**：点击 **“导出到 Python 解释器”**。
    * *机制*：工具会将库文件自动部署至该解释器的 `site-packages` 目录。
    * *效果*：无需额外操作，直接在代码中使用 `import LumAPI` 即可。

### 方式二：项目级集成（便携模式）
适用于临时测试或需随项目打包分发的场景。
1.  **本地生成**：点击 **“导出到本地目录”**。
2.  **部署文件**：工具将在当前目录下生成 `lumapi.py` 和 `config.json`。
3.  **使用**：将这两个文件复制到您的 Python 项目根目录，即可作为本地模块导入。
