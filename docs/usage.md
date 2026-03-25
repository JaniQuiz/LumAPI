## 💻 开发指南

### 1. 基础 FDTD 调用
本库对原生 API 进行了封装。

* **注意**：原脚本命令中的空格需替换为下划线 `_`。
    * 例如：`z min` $\rightarrow$ `z_min`
    * *注：传递给参数的字符串值保持原样，无需修改。*

**代码示例：**
```python
from LumAPI import lumapi

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

### 2. matlab数据文件.mat的读取和写入
本库内置了 matlab数据文件.mat的读取和写入功能。默认使用`matlab`的`v7.3`格式，支持`FDTD`的`24R1`以及更高版本的数据读取和写入。

**代码示例：**
```python
from LumAPI import savemat, loadmat

# 写入mat文件
x = np.array([1, 2, 3])
y = np.array([4, 5, 6])
E_near = np.array([[1+1j, 2+2j], [3+3j, 4+4j]])
data = {
    'x': x,
    'y': y,
    'E_near': E_near
}
savemat('data.mat', data)

# 读取mat文件
data_load = loadmat('data.mat')
x = data_load['x']
y = data_load['y']
E_near = data_load['E_near']
```

### 3. 高级算法库：衍射积分函数
内置多个高性能的近场-远场变换函数，支持多种计算后端以适应不同硬件环境。

示例：Kirchhoff函数  
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