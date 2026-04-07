# 💻 开发指南
 - [1. 基础 FDTD 调用](#1-基础-fdtd-调用)
    - [1.1 完全支持原生调用](#11-完全支持原生调用)
    - [1.2 对原本API的不足进行优化](#12-对原本api的不足进行优化)
    - [1.3 代码输入提示](#13-代码输入提示v113版本及以后)
 - [2. matlab数据文件.mat的读取和写入](#2-matlab数据文件mat的读取和写入)
 - [3. 高级算法库：衍射积分函数](#3-高级算法库衍射积分函数)
   - [3.1 基尔霍夫衍射积分](#31-kirchhoff函数)
   - [3.2 瑞利-索末菲标量衍射积分](#32-rayleigh-sommerfeld-标量衍射积分函数)
   - [3.3 瑞利-索末菲矢量衍射积分](#33-rayleigh-sommerfeld-矢量衍射积分函数)
   - [3.4 矢量角谱理论衍射积分](#34-angularspectrum-矢量衍射积分函数)
 - [4. 绘图相关](#4-绘图相关)
   - [4.1 自定义colorbar的cmap](#41-自定义colorbar的cmap)
   - [4.2 设置colorbar颜色映射的值域范围](#42-设置colorbar颜色映射的值域范围)


## 1. 基础 FDTD 调用
本程序对原生 API 进行了封装，并对参数进行了优化和改进。

### 1.1 完全支持原生调用
本程序提供了完全的原生调用方式，支持所有原生 API 函数。这里放上一些原生API的[个人使用小技巧](methods.md)。

本程序不仅支持`FDTD`的原生调用，还支持`MODE`，`DEVICE`和`INTERCONNECT`的原生调用和优化。
```python
def FDTD(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs)
def MODE(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs)
def DEVICE(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs)
def INTERCONNECT(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs)
```

对于`FDTD`中的函数，`Lumerical`的官方库中支持在创建结构时直接传入参数的方式，也支持创建后添加或修改属性。代码示例：
```python
um = 1e-6
material_base = 'Au (Gold) - CRC'
# 在创建结构时直接传入参数
fdtd.addrect(
    name="base",
    x=0,
    y=0,
    x_span=0.4*um,
    y_span=0.4*um,
    z_min=-0.3*um,
    z_max=0,
    material=material_base
)
# 创建完毕后修改属性
fdtd.set("z min", -0.5*um)
```

* **注意**：在作为传入参数时，由于传入参数的命名不支持空格，原脚本命令中的空格需替换为下划线 `_`。
    * 例如：`z min` $\rightarrow$ `z_min`
    * *注：作为字符串的参数值则保持原样，无需修改。*

您也可以通过`select`和`set`方法选择已经存在的对象来设置属性。
```python
fdtd.select('base')
fdtd.set("z min", -0.5*um)
```

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
fdtd.close() # 关闭FDTD会话
```

### 1.2 对原本API的不足进行优化
本程序提供了对 Lumerical 原生 API 的优化，使其更易用。

#### **传入参数自动转化**  
本程序会将你传入参数自动转化为`FDTD`格式。虽然`Lumerical`官方说软件中的数组与python的numpy数组一致，但实际二者并不等价。对于类似`[1, 2, 3]`的数组，在`python`中保存的格式就是`[1, 2, 3]`，而在`FDTD`中，数组会实际保存为`[[1,2,3]]`的格式，因此需要将传入的参数进行修改。本程序将会自动将您传入的参数自动转化为`FDTD`格式，无需担心报错问题。  
最典型的示例是调用`FDTD`的积分函数`integrate`时，官方给出的案例：
```matlab
Py = getdata("Monitor1","Py");
x = getdata("Monitor1","x");
y = getdata("Monitor1","y");
z = getdata("Monitor1","z");
f = getdata("Monitor1","f");
power = 0.5 * integrate(real(Py), [1,3], x, z);
```
理论上我们使用`python`调用应该是：
```python
Py = fdtd.getdata("Monitor1","Py")
x = fdtd.getdata("Monitor1","x")
y = fdtd.getdata("Monitor1","y")
z = fdtd.getdata("Monitor1","z")
power = 0.5 * fdtd.integrate(np.real(Py), [1,3], x, z)
```
实际使用中这样调用会报错，你应该这样编写：
```python
Py = fdtd.getdata("Monitor1","Py")
x = fdtd.getdata("Monitor1","x")
y = fdtd.getdata("Monitor1","y")
z = fdtd.getdata("Monitor1","z")
power = 0.5 * fdtd.integrate(np.real(Py), np.array([[1.0,3.0]]), x, z)
```
**使用本程序将无需担心这一点，无论你传入`[1,3]`，还是`[[1,3]]`，亦或者是`np.array([[1,3]])`，本程序都会自动将传入的参数自动转化为符合FDTD要求的格式**

#### **解决整型数据不支持问题**  
本程序会自动将你传入的`int`类型的`numpy`数组转为`float`类型。在`FDTD`中不存在整型数据，即便你定义了`[1,2,3]`，实际在`FDTD`中存储的数组仍然是浮点数`[1.0,2.0,3.0]`。而当你在使用`python`向`FDTD`中传入整型数据时，`FDTD`很显然会报错。本库会将你传入的numpy数组的`int`数据类型自动转为`float`类型，从而避免报错。

### 1.3 代码输入提示(v1.1.3版本及以后)
原生的API中并没有为python提供静态资源以提供代码输入提示功能，本仓库添加了自定义的pyi文件，以提供较为完整的代码输入提示功能。

本仓库提供的`pyi`文件通过`lumerical`的`24R1`版本进行提取，你也可以通过脚本来生成自己的`pyi`文件，包括两种方式：
 - **对于使用打包程序配置的用户**：下载[生成脚本](../gener_stubs.py)，放到与`LumAPI`同级文件夹下，然后运行即可。
 - **对于使用pip安装的用户**：运行`LumGenStubs`命令，会自动生成`pyi`文件。

效果实例：
![代码输入提示](explain_pics/autocompletion.png)


## 2. matlab数据文件.mat的读取和写入
本库内置了`matlab`数据文件`.mat`的读取和写入功能。默认使用`matlab`的`v7.3`格式，支持`FDTD`的`24R1`以及更高版本的数据读取和写入。此外，当保存的数据中包含有`int`类型数据的`numpy`数组，本函数将会自动转换为`float`类型。

 - 通过`scipy`库实现`v7.3`之前的mat文件格式保存和读取
 - 通过`h5py`库实现`v7.3`之后的mat文件格式保存和读取

**函数签名：**
```python
def savemat(filename, data_dict, version='v7.3', auto_transpose=True)
def loadmat(filename, auto_transpose=True, squeeze_me=True)
```

**savemat**

**参数说明：** 
- `filename`: str, 文件名，包含扩展名。
- `data_dict`: dict, 数据字典，键为变量名，值为变量值。
- `version`: str, mat文件格式版本，默认为`v7.3`。
   - `v7.3`: 使用`h5py`库实现mat文件格式保存，通用。
   - `v7`: 使用`scipy`库实现mat文件格式保存，适用于`FDTD`的`24R1`以前的版本。
- `auto_transpose`: bool, 是否自动转置数据，默认为`True`。`python`和`matlab`的数组主序不同，需要进行转置。
*注：`matlab`数据文件`.mat`的数据保存维度顺序与`python`相反，例如`python`中形状为`(3,2,1)`在`matlab`中为`(1,2,3)`。*

**loadmat**

**参数说明：**
- `filename`: str, 文件名，包含扩展名。
- `auto_transpose`: bool, 是否自动转置数据，默认为`True`。`python`和`matlab`的数组主序不同，需要进行转置。
- `squeeze_me`: bool, 是否对数据进行压缩，默认为`True`。对于一维数组和单个数据，`matlab`会自动将其转为`1xN`形状的数组，这里在读取时进行压缩来更符合`python`的习惯。

**返回值：**
- `data_dict`: dict，键为变量名，值为变量值。

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
savemat('data.mat', data) # 默认使用v7.3的格式保存
# savemat('data.mat', data, version='v7.3') # 使用v7.3以后的格式保存
# savemat('data.mat', data, version='v7') # 使用v7.3以前的格式保存

# 读取mat文件
data_load = loadmat('data.mat') # 自动检测两种格式的mat文件，无需设置参数即可读取
x = data_load['x']
y = data_load['y']
E_near = data_load['E_near']
```

## 3. 高级算法库：衍射积分函数
内置多个高性能的近场-远场变换函数，支持多种计算后端以适应不同硬件环境。每种算法函数均进行了验证，详见[目录](menu.md)
下面的所有函数的传入参数均有类型检查和转换，允许传入形如`(nx,ny,1,1,1)`的`numpy`数据。

### 3.1 Kirchhoff函数
标量基尔霍夫(Kirchhoff)衍射积分函数。

```python
def Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba', software='+')
```
**参数说明：**
- **lamb**: float, 波长
- **x_near**: 一维ndarray，近场x轴坐标
- **y_near**: 一维ndarray，近场y轴坐标
- **E_near**: 二维ndarray，近场电场数据或者近场波函数数据
- **x_far**: 一维ndarray或者float, 要计算的远场x轴坐标
- **y_far**: 一维ndarray或者float, 要计算的远场y轴坐标
- **z_far**: 一维ndarray或者float, 要计算的远场z轴坐标
- **mode**: str, 计算模式，分别对应不同的计算后端，默认为`numba`。
   - `numba`, `n`: 使用Numba库将核心计算函数进行编译后运行，速度快，资源占用高，适合大部分情况。
   - `vectorized`, `v`: 使用numpy库进行矢量化运算，速度很快，内存占用非常高，仅适合小规模数据快速计算。
   - `threaded`, `t`: 使用joblib库进行多线程进行计算，速度较快，资源占用高。
   - `common`, `c`: 使用python的`for`循环进行计算，速度慢，资源占用低，仅作为理论基础。
- **software**: str，传播约定，光传播时的两种不同约定，默认为`+`。
   - `+`, `FDTD`, `Lumerical`: 光传播约定`kz-wt`，`FDTD`中采用这种传播约定，当使用`FDTD`模拟的近场数据来计算远场时需要使用这种情况。
   - `-`, `COMSOL`, `CST`: 光传播约定`-kz+wt`，`COMSOL`和`CST`中采用这种传播约定，当使用这几种软件模拟近场来计算远场时需要使用这种情况。

**返回值：**
- **E_far**: 3维ndarray，远场电场数据或者近场波函数数据，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)

详细验证报告见[Kirchhoff验证报告](Kirchhoff.md)
详细调用代码示例参照[Kirchhoff.py](Kirchhoff.py)

### 3.2 Rayleigh-Sommerfeld 标量衍射积分函数
标量瑞利-索末菲(Rayleigh-Sommerfeld)衍射积分函数。

```python
def RayleighSommerfeld_Scalar(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba', software='+')
```
**参数说明：**
- **lamb**: float, 波长
- **x_near**: 一维ndarray，近场x轴坐标
- **y_near**: 一维ndarray，近场y轴坐标
- **E_near**: 二维ndarray，近场电场数据或者波函数数据
- **x_far**: 一维ndarray或者float, 要计算的远场x轴坐标
- **y_far**: 一维ndarray或者float, 要计算的远场y轴坐标
- **z_far**: 一维ndarray或者float, 要计算的远场z轴坐标
- **mode**: str, 计算模式，分别对应不同的计算后端，默认为`numba`。
   - `numba`, `n`: 使用Numba库将核心计算函数进行编译后运行，速度快，资源占用高，适合大部分情况。
   - `vectorized`, `v`: 使用numpy库进行矢量化运算，速度很快，内存占用非常高，仅适合小规模数据快速计算。
   - `threaded`, `t`: 使用joblib库进行多线程进行计算，速度较快，资源占用高。
   - `common`, `c`: 使用python的`for`循环进行计算，速度慢，资源占用低，仅作为理论基础。
- **software**: str，传播约定，光传播时的两种不同约定，默认为`+`。
   - `+`, `FDTD`, `Lumerical`: 光传播约定`kz-wt`，`FDTD`中采用这种传播约定，当使用`FDTD`模拟的近场数据来计算远场时需要使用这种情况。
   - `-`, `COMSOL`, `CST`: 光传播约定`-kz+wt`，`COMSOL`和`CST`中采用这种传播约定，当使用这几种软件模拟近场来计算远场时需要使用这种情况。

**返回值：**
- **E_far**: 3维ndarray，远场电场数据或者近场波函数数据，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)

详细验证报告见[Rayleigh-Sommerfeld_Scalar验证报告](Rayleigh-Sommerfeld_Scalar.md)
详细调用代码示例参照[Rayleigh-Sommerfeld_Scalar.py](Rayleigh-Sommerfeld_Scalar.py)

### 3.3 Rayleigh-Sommerfeld 矢量衍射积分函数
矢量瑞利-索末菲(Rayleigh-Sommerfeld)衍射积分函数。

```python
def RayleighSommerfeld_Vector(lamb, x_near, y_near, E_near_x, E_near_y, x_far, y_far, z_far, mode='numba', software='+')
```
**参数说明：**
- **lamb**: float, 波长
- **x_near**: 一维ndarray，近场x轴坐标
- **y_near**: 一维ndarray，近场y轴坐标
- **E_near_x**: 二维ndarray，近场电场数据x分量或者波函数数据x分量
- **E_near_y**: 二维ndarray，近场电场数据y分量或者波函数数据y分量
- **x_far**: 一维ndarray或者float, 要计算的远场x轴坐标
- **y_far**: 一维ndarray或者float, 要计算的远场y轴坐标
- **z_far**: 一维ndarray或者float, 要计算的远场z轴坐标
- **mode**: str, 计算模式，分别对应不同的计算后端，默认为`numba`。
   - `numba`, `n`: 使用Numba库将核心计算函数进行编译后运行，速度快，资源占用高，适合大部分情况。
   - `vectorized`, `v`: 使用numpy库进行矢量化运算，速度很快，内存占用非常高，仅适合小规模数据快速计算。
   - `threaded`, `t`: 使用joblib库进行多线程进行计算，速度较快，资源占用高。
   - `common`, `c`: 使用python的`for`循环进行计算，速度慢，资源占用低，仅作为理论基础。
- **software**: str，传播约定，光传播时的两种不同约定，默认为`+`。
   - `+`, `FDTD`, `Lumerical`: 光传播约定`kz-wt`，`FDTD`中采用这种传播约定，当使用`FDTD`模拟的近场数据来计算远场时需要使用这种情况。
   - `-`, `COMSOL`, `CST`: 光传播约定`-kz+wt`，`COMSOL`和`CST`中采用这种传播约定，当使用这几种软件模拟近场来计算远场时需要使用这种情况。

**返回值：**
- **E_total**: 3维ndarray，远场电场数据或者近场波函数数据，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_x**: 3维ndarray，远场电场数据或者近场波函数数据x分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_y**: 3维ndarray，远场电场数据或者近场波函数数据y分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_z**: 3维ndarray，远场电场数据或者近场波函数数据z分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)

详细验证报告见[Rayleigh-Sommerfeld_Vector验证报告](Rayleigh-Sommerfeld_Vector.md)
详细调用代码示例参照[Rayleigh-Sommerfeld_Vector.py](Rayleigh-Sommerfeld_Vector.py)

### 3.4 AngularSpectrum 矢量衍射积分函数
矢量角谱(Angular Spectrum)衍射积分函数。

```python
def AngularSpectrum_Vector(lamb, x_near, y_near, E_near_x, E_near_y, x_far, y_far, z_far, mode='numba', software='+')
```
**参数说明：**
- **lamb**: float, 波长
- **x_near**: 一维ndarray，近场x轴坐标
- **y_near**: 一维ndarray，近场y轴坐标
- **E_near_x**: 二维ndarray，近场电场数据x分量或者波函数数据x分量
- **E_near_y**: 二维ndarray，近场电场数据y分量或者波函数数据y分量
- **x_far**: 一维ndarray或者float, 要计算的远场x轴坐标
- **y_far**: 一维ndarray或者float, 要计算的远场y轴坐标
- **z_far**: 一维ndarray或者float, 要计算的远场z轴坐标
- **mode**: str, 计算模式，分别对应不同的计算后端，默认为`numba`。
   - `numba`, `n`: 使用Numba库将核心计算函数进行编译后运行，速度快，资源占用高，适合大部分情况。
   - `fft`, `f`: 使用快速傅里叶变换进行计算，速度极快，资源占用很小，但严格要求 x_far, y_far 与近场网格完全一致，适合快速查看衍射情况。
- **software**: str，传播约定，光传播时的两种不同约定，默认为`+`。
   - `+`, `FDTD`, `Lumerical`: 光传播约定`kz-wt`，`FDTD`中采用这种传播约定，当使用`FDTD`模拟的近场数据来计算远场时需要使用这种情况。
   - `-`, `COMSOL`, `CST`: 光传播约定`-kz+wt`，`COMSOL`和`CST`中采用这种传播约定，当使用这几种软件模拟近场来计算远场时需要使用这种情况。

**返回值：**
- **E_total**: 3维ndarray，远场电场数据或者近场波函数数据，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_x**: 3维ndarray，远场电场数据或者近场波函数数据x分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_y**: 3维ndarray，远场电场数据或者近场波函数数据y分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)
- **E_far_z**: 3维ndarray，远场电场数据或者近场波函数数据z分量，形状为`(x_far.shape, y_far.shape, z_far.shape)`(如果传入为数字，对应的`shape`为`1`)

详细验证报告见[AngularSpectrum_Vector验证报告](AngularSpectrum_Vector.md)
详细调用代码示例参照[AngularSpectrum_Vector.py](AngularSpectrum_Vector.py)

## 4. 绘图相关
### 4.1 自定义colorbar的cmap
对于matplotlib库自带的cmap构建较为复杂，这里提供了自定义cmap的函数，支持多种颜色输入，可以方便地从论文中提取好看的绘图颜色来应用到自己的绘图中。

函数签名：
```python
def create_cmap(color_list, cmap_name="custom_cmap")
```
**参数说明：**
 - **color_list**: list, 颜色列表，按顺序定义渐变路径。列表元素支持：
   - 颜色名称: str, 例如 'black', 'red', 'white'
   - 十六进制色值: str, 例如 '#000000', '#FF5733', '#FFFFFF'
   - RGB值: 浮点数元组 (范围 0.0-1.0), 例如 (0.0, 0.0, 1.0)
   - RGB值: 整数元组 (范围 0-255), 例如 (0, 0, 255)
 - **cmap_name**: str, 生成的 Colorbar 的名称，默认为 "custom_cmap"

**返回值：**
- **cmap**: matplotlib.colors.LinearSegmentedColormap, 自定义的colorbar颜色映射

**代码示例：**
```python
cmap = create_cmap([(0, 0, 0), (0.0, 0.0, 1.0), 'red', '#FFFFFF']) #  黑色->蓝色->红色->白色
plt.figure()
plt.imshow(img, cmap=cmap)
plt.colorbar()
plt.show()
```

### 4.2 设置colorbar颜色映射的值域范围
我们当然可以在绘图时就传入`vmin`和`vmax`参数，来设置colorbar的取值范围。但在希望动态更新图表时，使用这个函数可以帮助我们随时随地修改已经画好的颜色映射范围，而不需要重新绘制图表。

函数签名：
```python
def set_colorbar_range(mappable, vmin, vmax)
```

**参数说明：**
 - **mappable**: matplotlib 绘图对象 (例如 plt.imshow(), plt.scatter() 的返回值)或者是一个 colorbar 对象。
 - **vmin**: float, colorbar 的最小值
 - **vmax**: float, colorbar 的最大值

**代码示例：**
```python
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# --- 图 1：默认范围 ---
im1 = ax1.imshow(data, cmap='viridis')
cb1 = fig.colorbar(im1, ax=ax1)
ax1.set_title("默认 Colorbar 范围\n(根据数据自动缩放)")

# --- 图 2：使用自定义函数设置范围 ---
im2 = ax2.imshow(data, cmap='viridis')
cb2 = fig.colorbar(im2, ax=ax2)
ax2.set_title("自定义 Colorbar 范围\n(限制在 -5 到 5 之间)")

# 调用函数，这里可以传入图像对象 im2 或颜色条 cb2
set_colorbar_range(im2, vmin=-5, vmax=5) 

plt.tight_layout()
plt.show()
```
