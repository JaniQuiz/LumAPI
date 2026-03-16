# Lumerical FDTD Python 自用脚本整理

本项目旨在简化 Lumerical FDTD 软件与 Python 环境的交互流程，提供自动化的路径配置工具，并封装了常用的光学仿真后处理算法（如近场至远场变换）。

## 📖 核心功能
* **自动化环境配置**：自动识别系统中的 Lumerical 安装路径及版本。
* **灵活集成**：支持将 API 库集成至特定 Python 解释器或独立项目目录。
* **API 增强**：支持原本接口，并内置高性能计算函数。

---

## 🚀 快速开始

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
fdtd = lumapi().FDTD(filename)
fdtd.close()
```
或者不进行lumerical配置，直接传入lumerical路径：
```python
from LumAPI import *
lumerical_path = 'C:/Program Files/Lumerical'
version = 'v241
fdtd = lumapi(lumerical_path=lumerical_path, version=version).FDTD(filename)
fdtd.close()
```
或者传入config.json路径：
```python
from LumAPI import *
config_path = './config.json'
fdtd = lumapi(config_path=config_path).FDTD(filename)
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

---

## 💻 开发指南

### 1. 基础 FDTD 调用
本库对原生 API 进行了封装。

* **注意**：原脚本命令中的空格需替换为下划线 `_`。
    * 例如：`z min` $\rightarrow$ `z_min`
    * *注：传递给参数的字符串值保持原样，无需修改。*

**代码示例：**
```python
import LumAPI.lumapi as lumapi  # 根据实际导出结构调整导入路径

# 定义基础参数
um = 1e-6
nx, ny = 100, 100
S = 0.5 * um
material_base = 'Au (Gold) - CRC'

# 初始化 FDTD 会话
filename = 'simulation.fsp'
fdtd = lumapi.FDTD(filename)

# 添加矩形结构 (注意 z_min 的写法)
fdtd.addrect(
    name="base",
    x=0, y=0,
    x_span=nx*S, y_span=ny*S,
    z_min=-0.3*um, z_max=0,
    material=material_base
)

# 修改属性并保存
fdtd.select('base')
fdtd.set('z min', -0.5*um) # 字符串参数值保持带空格的原样
fdtd.save()
fdtd.close()
```

### 2. 高级算法库：Kirchhoff 衍射积分
内置高性能的近场-远场变换函数 Kirchhoff，支持多种计算后端以适应不同硬件环境。

**函数签名：**
```python
def Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba'):
    """
    基于标量衍射理论，计算从近场平面到远场空间的电场分布。

    参数:
        lamb (float): 波长
        x_near, y_near (1D array): 近场区域的网格坐标
        E_near (2D array): 近场复振幅电场数据
        x_far, y_far, z_far (1D array/float): 目标远场区域的坐标
        mode (str): 计算加速模式
            - 'numba' ('n'): [推荐] 使用 JIT 编译加速，兼顾速度与跨平台兼容性 (需安装 numba)。
            - 'threaded' ('t'): 多线程模式，CPU 占用率高 (仅限 Windows，需安装 joblib)。
            - 'common' ('c'): 纯 Python 实现，最稳定但速度较慢。
            - 'vectorized' ('v'): 矢量化模式 (实验性，处理大数据时易内存溢出)。

    返回:
        np.ndarray: 远场电场分布，维度为 (len(x_far), len(y_far), len(z_far))
    """
```

**调用示例：**
```python
import numpy as np
import matplotlib.pyplot as plt
from LumAPI import Kirchhoff

# 1. 定义物理常数与网格
um = 1e-6
nm = 1e-9
lamb = 1 * um
k = 2 * np.pi / lamb
p = 700 * nm   # 采样周期

# 2. 构建近场数据 (模拟一个聚焦光场)
kx, ky = 100, 100
x_near = np.arange(-kx/2, kx/2) * p
y_near = np.arange(-ky/2, ky/2) * p
X, Y = np.meshgrid(x_near, y_near)

focal_length = 20 * um
# 理想透镜相位调制
phi = -k / (2 * focal_length) * (X**2 + Y**2)
# 添加圆形孔径光阑
mask = (X**2 + Y**2) <= ((kx-20)/2 * p)**2
phi[~mask] = 0
E_near = np.zeros_like(X, dtype=complex)
E_near[mask] = 1.0 * np.exp(1j * phi[mask])

# 3. 定义远场观测区域
x_far = 0
y_far = y_near
z_far = np.arange(0, 40 * um, p) # 沿轴向传播 40um

# 4. 执行衍射计算 (推荐使用 numba 模式)
E_far = Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba')

# 5. 可视化结果 (YZ平面光强分布)
plt.figure(figsize=(10, 6))
# 注意：E_far 的维度顺序对应 x_far, y_far, z_far
# 由于 x_far 是标量，我们取切片 [0, :, :] 并转置以适配 imshow (行对应 Z，列对应 Y)
intensity = np.abs(E_far[0, :, :])**2
plt.imshow(intensity.T, 
           extent=[y_far.min()/um, y_far.max()/um, z_far.min()/um, z_far.max()/um],
           origin='lower', cmap='inferno', aspect='auto')
plt.xlabel('Y Position (um)')
plt.ylabel('Z Propagation (um)')
plt.title('Kirchhoff Diffraction Pattern')
plt.colorbar(label='Intensity')
plt.show()
```
