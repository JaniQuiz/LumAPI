# 瑞利-索末菲标量衍射积分 (Rayleigh-Sommerfeld Scalar Diffraction) 验证报告

本文档旨在验证基于瑞利-索末菲衍射公式（第一类）的 Python 传播函数的正确性与性能。验证场景设定为**近红外超透镜 (Metalens) 的点聚焦模拟**。相比于基尔霍夫近似，瑞利-索末菲积分在近场和广角衍射（高 NA）下具有更严谨的物理与数学基础。  
本文图片生成脚本: [Rayleigh-Sommerfeld_Scalar.py](Rayleigh-Sommerfeld_Scalar.py)

### ⚙️ 仿真物理参数设置
* **工作波长 (λ)**: 1.55 μm (近红外通信波段)
* **超透镜尺寸 (D)**: 60 μm × 60 μm
* **近场网格间距 (dx, dy)**: 0.5 μm (满足 ≤ λ/2 奈奎斯特采样定律，彻底消除相空间混叠)
* **设计焦距 (f)**: 50 μm (数值孔径 NA ≈ 0.51)

---

## 💻 通用初始化代码 (Initialization)
在运行以下任意计算模式前，需要先构建近场物理网格与透镜参数。由于采用了大内存高性能服务器进行计算，所有测试模式均使用统一的高分辨率网格，**不进行任何降采样**，以确保结果的绝对一致性。

```python
import numpy as np
from LumAPI import RayleighSommerfeld_Scalar

# 1. 物理参数定义
lamb = 1.55e-6
k = 2 * np.pi / lamb
D = 60e-6
dx = 0.5e-6
f_design = 50e-6

# 2. 构建近场网格
x_n = np.arange(-D/2, D/2, dx)
y_n = np.arange(-D/2, D/2, dx)
X_n, Y_n = np.meshgrid(x_n, y_n, indexing='xy')

# 3. 透镜圆形光阑截断
aperture = (X_n**2 + Y_n**2) <= (D/2)**2

# 4. 定义远场观察坐标轴 (所有模式统一使用高分辨率)
z_scan = np.linspace(1e-6, 100e-6, 200)       # Z轴扫描 (0 到 2f)
x_f_scan = np.linspace(-10e-6, 10e-6, 100)    # XY焦平面扫描范围
x_xz_scan = np.linspace(-30e-6, 30e-6, 150)   # XZ截面横向扫描范围
```

---

## 📑 目录 (Table of Contents)
1. [第一组：正相位传播约定 (+)](#1-plus)
   - [1.1 Numba 并行模式 (推荐)](#11-numba)
   - [1.2 Vectorized 矢量化模式](#12-vectorized)
   - [1.3 Threaded 多线程模式](#13-threaded)
   - [1.4 Common 普通循环模式](#14-common)
2. [第二组：负相位传播约定 (-)](#2-minus)
   - [2.1 Numba 并行模式验证](#21-numba)
3. [第三组：误差分析与一致性验证](#3-diff)
   - [3.1 不同计算模式差值分析](#31-mode-diff)
   - [3.2 不同相位约定差值分析](#32-phase-diff)

---

<h2 id="1-plus">1. 第一组：正相位传播约定 (+)</h2>
<p>本组测试采用 <code>software='+'</code>，即空间相位传播项为 exp(+ikz)。为了实现聚焦，超透镜的相位补偿分布设定为负相位：φ = -k√(x² + y² + f²)。</p>

```python
# 生成正相位约定下的近场电场
phase_plus = -k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
E_near_plus = aperture * np.exp(1j * phase_plus)
```

<h3 id="11-numba">1.1 Numba 并行模式 (mode='n')</h3>
<p>在 CPU 上运行最快且内存占用极低的模式，适合大规模 3D 空间的光场扫描。</p>

```python
# 1. Z 轴光强扫描
E_z = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, 0.0, 0.0, z_scan, mode='n', software='+')

# 2. XY 焦平面 2D 扫描 (设定 Z = f_design)
E_xy = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_f_scan, x_f_scan, f_design, mode='n', software='+')

# 3. XZ 传播截面 2D 扫描 (设定 Y = 0)
E_xz = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_xz_scan, 0.0, z_scan, mode='n', software='+')
```

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_plus_numba_Z.jpg" alt="Z轴分布" width="300"><br>
      <sup><b>图 1.1a:</b> Z轴分布。精确吻合设计焦距 50 μm。</sup>
    </td>
    <td align="center">
      <img src="./pics/RS_scalar_plus_numba_XY.jpg" alt="XY焦平面" width="300"><br>
      <sup><b>图 1.1b:</b> 焦平面分布。呈现完美的圆形 Airy 斑。</sup>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="./pics/RS_scalar_plus_numba_XZ.jpg" alt="XZ平面全景" width="600"><br>
      <sup><b>图 1.1c:</b> XZ 传播截面。清晰展示光束的聚焦沙漏形态。</sup>
    </td>
  </tr>
</table>


<h3 id="12-vectorized">1.2 Vectorized 矢量化模式 (mode='v')</h3>
<p>利用 Numpy 矢量计算的方式。单线计算极快，依赖大内存服务器进行全分辨率计算。</p>

```python
E_z_v  = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, 0.0, 0.0, z_scan, mode='v', software='+')
E_xy_v = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_f_scan, x_f_scan, f_design, mode='v', software='+')
E_xz_v = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_xz_scan, 0.0, z_scan, mode='v', software='+')
```

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_plus_vectorized_Z.jpg" width="300"><br>
      <sup><b>图 1.2a:</b> Z轴分布</sup>
    </td>
    <td align="center">
      <img src="./pics/RS_scalar_plus_vectorized_XY.jpg" width="300"><br>
      <sup><b>图 1.2b:</b> 焦平面分布</sup>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="./pics/RS_scalar_plus_vectorized_XZ.jpg" width="600"><br>
      <sup><b>图 1.2c:</b> XZ 传播截面</sup>
    </td>
  </tr>
</table>


<h3 id="13-threaded">1.3 Threaded 多线程模式 (mode='t')</h3>
<p>基于 joblib 的进程级并行，适合未配置 Numba 编译器的环境。</p>

```python
E_z_t  = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, 0.0, 0.0, z_scan, mode='t', software='+')
E_xy_t = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_f_scan, x_f_scan, f_design, mode='t', software='+')
E_xz_t = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_xz_scan, 0.0, z_scan, mode='t', software='+')
```

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_plus_threaded_Z.jpg" width="300"><br>
      <sup><b>图 1.3a:</b> Z轴分布</sup>
    </td>
    <td align="center">
      <img src="./pics/RS_scalar_plus_threaded_XY.jpg" width="300"><br>
      <sup><b>图 1.3b:</b> 焦平面分布</sup>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="./pics/RS_scalar_plus_threaded_XZ.jpg" width="600"><br>
      <sup><b>图 1.3c:</b> XZ 传播截面</sup>
    </td>
  </tr>
</table>


<h3 id="14-common">1.4 Common 普通循环模式 (mode='c')</h3>
<p>纯 Python 嵌套循环，运算耗时最长，作为底层算法等价性验证的基准参考标准。</p>

```python
E_z_c  = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, 0.0, 0.0, z_scan, mode='c', software='+')
E_xy_c = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_f_scan, x_f_scan, f_design, mode='c', software='+')
E_xz_c = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_plus, x_xz_scan, 0.0, z_scan, mode='c', software='+')
```

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_plus_common_Z.jpg" width="300"><br>
      <sup><b>图 1.4a:</b> Z轴分布</sup>
    </td>
    <td align="center">
      <img src="./pics/RS_scalar_plus_common_XY.jpg" width="300"><br>
      <sup><b>图 1.4b:</b> 焦平面分布</sup>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="./pics/RS_scalar_plus_common_XZ.jpg" width="600"><br>
      <sup><b>图 1.4c:</b> XZ 传播截面</sup>
    </td>
  </tr>
</table>

---

<h2 id="2-minus">2. 第二组：负相位传播约定 (-)</h2>
<p>本组测试采用 <code>software='-'</code>，即空间相位传播项为 exp(-ikz)。为了匹配该约定，超透镜的设计相位必须翻转为正：$\phi = +k \sqrt{x^2 + y^2 + f^2}$。</p>

```python
# 生成负相位约定下的近场电场 (注意相位正负号翻转)
phase_minus = k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
E_near_minus = aperture * np.exp(1j * phase_minus)

# 显式指定 software='-'
E_z_m  = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_minus, 0.0, 0.0, z_scan, mode='n', software='-')
E_xy_m = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_minus, x_f_scan, x_f_scan, f_design, mode='n', software='-')
E_xz_m = RayleighSommerfeld_Scalar(lamb, x_n, y_n, E_near_minus, x_xz_scan, 0.0, z_scan, mode='n', software='-')
```

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_minus_numba_Z.jpg" alt="负约定 Z轴" width="300"><br>
      <sup><b>图 2.1a:</b> 负约定 Z 轴光强。与图 1.1a 分布完全相同。</sup>
    </td>
    <td align="center">
      <img src="./pics/RS_scalar_minus_numba_XY.jpg" alt="负约定 XY" width="300"><br>
      <sup><b>图 2.1b:</b> 负约定焦平面分布。物理结果不受数学符号干扰。</sup>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="./pics/RS_scalar_minus_numba_XZ.jpg" alt="负约定 XZ" width="600"><br>
      <sup><b>图 2.1c:</b> 负约定 XZ 传播截面。相位流向已正确映射回实际物理空间。</sup>
    </td>
  </tr>
</table>

---

<h2 id="3-diff">3. 第三组：误差分析与一致性验证</h2>
<p>不同计算模式仅在编程实现手段上存在差异，其底层的瑞利-索末菲积分完全等价。同样，无论是正相位约定还是负相位约定，计算出的物理光强分布应当严格相同。</p>

<h3 id="31-mode-diff">3.1 不同计算模式差值分析</h3>
<p>下图展示了 Numba、Vectorized 和 Threaded 模式与纯 Common 基准模式计算结果的差值。为避免极其微小的机器浮点误差被 Colorbar 放大为色彩噪点，绘图时已将 Colorbar 上限固定为 <code>1e-10</code>。所有图像理论上应呈现为均匀的零值底色，验证了各模式的一致性。</p>

```python
# 提取各模式光强并计算差值 (以 Common 模式为基准)
I_xy_c = np.abs(E_xy_c[:, :, 0])**2
I_xz_c = np.abs(E_xz_c[:, 0, :])**2
# ... (相关差值计算见 Python 脚本)
```

<table align="center" width="100%">
  <tr>
    <td width="33%" align="center" valign="bottom">
      <img src="./pics/RS_scalar_diff_numba_c_XY.jpg" alt="Numba vs Common XY" width="100%"><br>
      <img src="./pics/RS_scalar_diff_numba_c_XZ.jpg" alt="Numba vs Common XZ" width="100%"><br>
      <div align="left">
        <b>Numba - Common</b><br>
        <sup>XY 最大差值: 1.0004e-11, 平均差值: 2.4672e-14<br>
        XZ 最大差值: 9.2086e-12, 平均差值: 2.0479e-14</sup>
      </div>
      <sup><b>图 3.1a:</b> Numba 模式绝对差值</sup>
    </td>
    <td width="33%" align="center" valign="bottom">
      <img src="./pics/RS_scalar_diff_vectorized_c_XY.jpg" alt="Vectorized vs Common XY" width="100%"><br>
      <img src="./pics/RS_scalar_diff_vectorized_c_XZ.jpg" alt="Vectorized vs Common XZ" width="100%"><br>
      <div align="left">
        <b>Vectorized - Common</b><br>
        <sup>XY 最大差值: 1.1482e-11, 平均差值: 2.7307e-14<br>
        XZ 最大差值: 9.2086e-12, 平均差值: 2.1225e-14</sup>
      </div>
      <sup><b>图 3.1b:</b> 矢量化模式绝对差值</sup>
    </td>
    <td width="33%" align="center" valign="bottom">
      <img src="./pics/RS_scalar_diff_threaded_c_XY.jpg" alt="Threaded vs Common XY" width="100%"><br>
      <img src="./pics/RS_scalar_diff_threaded_c_XZ.jpg" alt="Threaded vs Common XZ" width="100%"><br>
      <div align="left">
        <b>Threaded - Common</b><br>
        <sup>XY 最大差值: 1.1823e-11, 平均差值: 2.6729e-14<br>
        XZ 最大差值: 9.5497e-12, 平均差值: 2.1352e-14</sup>
      </div>
      <sup><b>图 3.1c:</b> 多线程模式绝对差值</sup>
    </td>
  </tr>
</table>

<h3 id="32-phase-diff">3.2 不同相位约定差值分析</h3>
<p>下图展示了在 Numba 模式下，采用正相位约定 <code>software='+'</code> 与负相位约定 <code>software='-'</code> 得到的光强分布的绝对差值。这证明了即使复数电场虚部的演化方向完全相反，算法仍能正确保证物理标量场能量的绝对一致性。</p>

<table align="center">
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_diff_minus_plus_XY.jpg" alt="Minus vs Plus XY" width="400">
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="./pics/RS_scalar_diff_minus_plus_XZ.jpg" alt="Minus vs Plus XZ" width="400">
    </td>
  </tr>
  <tr>
    <td align="center">
      <div align="left" style="display:inline-block;">
        <sup>XY 平面最大差值: 7.1623e-12, 平均差值: 1.6898e-14<br>
        XZ 截面最大差值: 9.7771e-12, 平均差值: 1.2292e-14</sup>
      </div><br>
      <sup><b>图 3.2:</b> 负约定 - 正约定绝对差值 (上: XY平面, 下: XZ全景传播截面)</sup>
    </td>
  </tr>
</table>