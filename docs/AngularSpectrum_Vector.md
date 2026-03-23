# 矢量角谱法 (Vector Angular Spectrum) 验证报告

本文档旨在验证基于矢量角谱衍射理论的 Python 传播函数的正确性与性能。验证场景设定为**近红外超透镜 (Metalens) 的点聚焦模拟**。角谱法通过分解空间频率 (Plane Wave Expansion) 进行严格传播，在处理非傍轴 (Non-paraxial)、高频倏逝波 (Evanescent waves) 时具有极高的理论精度。

### ⚙️ 仿真物理参数设置
* **工作波长 (λ)**: 1.55 μm
* **超透镜尺寸 (D)**: 60 μm × 60 μm
* **近场网格间距 (dx, dy)**: 0.5 μm
* **设计焦距 (f)**: 50 μm (数值孔径 NA ≈ 0.51)
* **入射偏振态**: X 线偏振 (X-polarized)

---

## 💻 通用初始化代码 (Initialization)
角谱法的 FFT 模式要求远场网格与近场严格一致，而 Numba 模式则支持任意坐标点。为实现绝对公平的误差比对，我们在前两节统一使用原生近场网格 `x_n, y_n` 进行计算。

```python
import numpy as np
from LumAPI import AngularSpectrum_Vector

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

# 3. 透镜圆形光阑截断与近场偏振初始化 (纯 X 偏振)
aperture = (X_n**2 + Y_n**2) <= (D/2)**2
z_scan = np.linspace(1e-6, 100e-6, 200)       # 轴向扫描
```

---

## 📑 目录 (Table of Contents)
1. [第一组：正相位传播约定 (+)](#1-plus)
   - [1.1 FFT 快速傅里叶模式 (全空间瞬时计算)](#11-fft)
   - [1.2 Numba 连续逆傅里叶积分模式](#12-numba)
2. [第二组：负相位传播约定 (-)](#2-minus)
3. [第三组：误差分析与一致性验证](#3-diff)
4. [第四组：矢量衍射特性与 Numba 无级缩放分析](#4-feature)

---

<h2 id="1-plus">1. 第一组：正相位传播约定 (+)</h2>
<p>采用 <code>software='+'</code> 约定。近场施加负号聚焦相位。</p>

```python
phase_plus = -k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
E_near_x_plus = aperture * np.exp(1j * phase_plus)
E_near_y_plus = np.zeros_like(E_near_x_plus)
```

<h3 id="11-fft">1.1 FFT 快速傅里叶模式 (mode='f')</h3>
<p>利用传递函数 H(fx, fy) 进行极速卷积。一次调用即可返回全空间 3D 矩阵，耗时仅需零点几秒。</p>

```python
# FFT模式要求 x_far, y_far 必须等于 x_near, y_near
E_tot_f, _, _, _ = AngularSpectrum_Vector(lamb, x_n, y_n, E_near_x_plus, E_near_y_plus, x_n, y_n, z_scan, mode='f', software='+')
```

<div style="display: flex; justify-content: space-between; align-items: stretch; gap: 15px; margin-bottom: 15px;">
    <div style="display: flex; flex-direction: column; flex: 1; text-align: center; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_plus_fft_XY.jpg" alt="XY焦平面" style="width: 100%; border-radius: 4px;">
        <p style="margin-top: auto; padding-top: 10px; font-size: 0.9em; color: #333333;"><b>图 1.1a:</b> FFT 焦平面 (全尺寸视野)。</p>
    </div>
    <div style="display: flex; flex-direction: column; flex: 1; text-align: center; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_plus_fft_XZ.jpg" alt="XZ平面" style="width: 100%; border-radius: 4px;">
        <p style="margin-top: auto; padding-top: 10px; font-size: 0.9em; color: #333333;"><b>图 1.1b:</b> FFT XZ 传播截面。</p>
    </div>
</div>

<h3 id="12-numba">1.2 Numba 连续逆傅里叶积分模式 (mode='n')</h3>
<p>不依赖 IFFT，而是通过 JIT 并行显式计算角谱的连续反积分。虽然速度不如 FFT，但这是数学上最严谨的对比基准。</p>

```python
# 针对特定切片坐标进行 Numba 离散化计算
E_tot_n_xy, _, _, _ = AngularSpectrum_Vector(lamb, x_n, y_n, E_near_x_plus, E_near_y_plus, x_n, y_n, actual_f, mode='n', software='+')
E_tot_n_xz, _, _, _ = AngularSpectrum_Vector(lamb, x_n, y_n, E_near_x_plus, E_near_y_plus, x_n, 0.0, z_scan, mode='n', software='+')
```

---

<h2 id="2-minus">2. 第二组：负相位传播约定 (-)</h2>

```python
phase_minus = k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
E_near_x_minus = aperture * np.exp(1j * phase_minus)
# ... 计算略 (代码见 Python 脚本) ...
```

---

<h2 id="3-diff">3. 第三组：误差分析与一致性验证</h2>
<p>角谱法的两种模式：离散快速傅里叶反变换 (FFT) 与 显式连续积分 (Numba) 在数学上完全等价。下图展示了它们计算同一平面时的绝对差值，由于 Colorbar 固定在极低量级，画面呈现零底色，印证了频域解析逻辑的严丝合缝。</p>

<div style="display: flex; justify-content: space-between; align-items: stretch; gap: 10px; margin-bottom: 30px;">
    <div style="display: flex; flex-direction: column; flex: 1; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_diff_numba_fft_XY.jpg" alt="Numba vs FFT XY" style="width: 100%; border-radius: 4px; margin-bottom: 10px;">
        <img src="./pics/AS_vector_diff_numba_fft_XZ.jpg" alt="Numba vs FFT XZ" style="width: 100%; border-radius: 4px;">
        <div style="margin-top: auto; padding-top: 15px; font-size: 0.85em; color: #333333;">
            <p style="margin: 0 0 5px 0;"><b>计算模式差异 (Numba - FFT)</b></p>
            <ul style="margin: 0; padding-left: 15px;">
                <li>XY 最大差值: 1.1892e-10, 平均差值: 1.3582e-13</li>
                <li>XZ 最大差值: 7.7307e-11, 平均差值: 3.8210e-13</li>
            </ul>
        </div>
    </div>
    <div style="display: flex; flex-direction: column; flex: 1; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_diff_minus_plus_XY.jpg" alt="Minus vs Plus XY" style="width: 100%; border-radius: 4px; margin-bottom: 10px;">
        <img src="./pics/AS_vector_diff_minus_plus_XZ.jpg" alt="Minus vs Plus XZ" style="width: 100%; border-radius: 4px;">
        <div style="margin-top: auto; padding-top: 15px; font-size: 0.85em; color: #333333;">
            <p style="margin: 0 0 5px 0;"><b>相位约定差异 (Minus - Plus)</b></p>
            <ul style="margin: 0; padding-left: 15px;">
                <li>XY 最大差值: 4.5475e-13, 平均差值: 1.9947e-16</li>
                <li>XZ 最大差值: 5.6843e-13, 平均差值: 1.0690e-15</li>
            </ul>
        </div>
    </div>
</div>

---

<h2 id="4-feature">4. 矢量衍射特性与 Numba 无级缩放分析</h2>
<p>在传统的 FFT 角谱法中，若想查看焦点的微观细节，往往需要极大地扩展矩阵维度进行补零插值 (Zero-padding)。而通过 LumAPI 的 <b>Numba 逆积分模式</b>，我们可以直接向函数传入微米级别的局部高分辨率坐标点 <code>x_zoom, y_zoom</code>，算法将精确解析出该坐标下的连续角谱场强！</p>
<p>我们对焦平面核心 ±4 μm 区域进行了无级缩放扫描。结果完美复现了高 NA 聚焦下特有的偏振耦合物理现象：<b>散度定理诱导出的双波瓣纵向电场 (|Ez|²)</b>，以及光斑沿偏振方向发生的非对称椭圆化。</p>

<div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-bottom: 30px;">
    <div style="display: flex; flex-direction: column; width: 32%; text-align: center; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_feature_Ex.jpg" alt="Ex Component" style="width: 100%; border-radius: 4px;">
        <p style="margin-top: 10px; font-size: 0.9em; color: #333333;"><b>图 4.1a: 主偏振分量 |Ex|²</b><br>基于 Numba 模式实现的高分辨率光斑无级放大。</p>
    </div>
    <div style="display: flex; flex-direction: column; width: 32%; text-align: center; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_feature_Ez.jpg" alt="Ez Component" style="width: 100%; border-radius: 4px;">
        <p style="margin-top: 10px; font-size: 0.9em; color: #333333;"><b>图 4.1b: 纵向偏振分量 |Ez|²</b><br>沿 X 轴分布的强波瓣，证明散度守恒定律。</p>
    </div>
    <div style="display: flex; flex-direction: column; width: 32%; text-align: center; background-color: #ffffff; padding: 10px; border: 1px solid #eeeeee; border-radius: 8px;">
        <img src="./pics/AS_vector_feature_Total.jpg" alt="Total Intensity" style="width: 100%; border-radius: 4px;">
        <p style="margin-top: 10px; font-size: 0.9em; color: #333333;"><b>图 4.1c: 总光强 |E_total|²</b><br>光斑沿偏振方向产生可见的非对称拉伸。</p>
    </div>
</div>