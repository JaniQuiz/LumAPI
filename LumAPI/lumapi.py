import numpy as np
import os
import sys
import json
import importlib
import importlib.util
import re, platform

current_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(current_dir, 'config.json')

# ******************数据处理函数******************
def savemat(filename, data_dict, version='v7.3', auto_transpose=True):
    """
    将字典数据写入 MATLAB .mat 文件。

    参数 (Parameters):
    ------------------
    filename : str
        输出的 .mat 文件路径和名称。
    data_dict : dict
        需要写入的数据字典。
    version : str, 可选 (默认: 'v7.3')
        指定写入的 .mat 文件版本格式 ('v7.3' 或 'v7')。
    auto_transpose : bool, 可选 (默认: True)
        是否自动处理 Python 和 MATLAB 的跨语言内存主序差异。
        如果开启，在写入 v7.3(HDF5) 格式时，会自动将多维数组转置，
        确保 FDTD 或 MATLAB 读入时的维度形状与 Python 中完全一致。

    返回 (Returns):
    ---------------
    bool
        写入成功返回 True。
    """
    # 预处理字典，将所有整型转换为浮点型
    processed_dict = {}
    for key, val in data_dict.items():
        data_array = np.asarray(val)
        
        # 对齐 MATLAB/scipy.io 的底层维度逻辑
        # 强制将标量(0D)和一维数组(1D)提升为二维矩阵(1x1 或 1xN)
        data_array = np.atleast_2d(data_array)
        
        # 针对 FDTD：将所有整数转为双精度浮点数
        if np.issubdtype(data_array.dtype, np.integer):
            data_array = data_array.astype(np.float64)
            
        processed_dict[key] = data_array

    if version == 'v7.3':
        import h5py
        # 预留 512 字节的 userblock 空间给 MATLAB 特征头
        with h5py.File(filename, 'w', userblock_size=512) as f:
            for key, data_array in processed_dict.items():
                
                # 自动转置处理
                if auto_transpose:
                    data_array = data_array.T
                
                # 针对复数的特殊封装
                if np.iscomplexobj(data_array):
                    # 按照 MATLAB 期望的 HDF5 复合格式构造：字段名必须为 'real' 和 'imag'
                    complex_dt = np.dtype([('real', data_array.real.dtype), 
                                           ('imag', data_array.imag.dtype)])
                    mat_complex = np.empty(data_array.shape, dtype=complex_dt)
                    mat_complex['real'] = data_array.real
                    mat_complex['imag'] = data_array.imag
                    f.create_dataset(key, data=mat_complex)
                else:
                    f.create_dataset(key, data=data_array)

        # 受限于底层 HDF5 C 语言库的运行机制，wb模式会清空文件，追加a模式会报错，只能先h5py保存后with open打开写入文件头
        # HDF5 文件写入完成后，以读写模式打开并注入 MATLAB 文件头
        with open(filename, 'r+b') as f:
            # 前 116 字节为文本描述，不足部分用空格补齐
            header_str = 'MATLAB 7.3 MAT-file, created by LumAPI custom script'
            header_bytes = header_str.encode('ascii').ljust(116, b' ')
            
            # 接下来的 8 字节为子系统数据偏移量（全 0 即可）
            subsys_offset = b'\x00' * 8
            
            # 最后 4 字节为版本号和字节序：0x0200 表示 v7.3，'IM' 表示小端序 (Little Endian)
            version_and_endian = b'\x02\x00IM'
            
            f.seek(0)
            f.write(header_bytes + subsys_offset + version_and_endian)
                
    elif version == 'v7':
        import scipy.io
        # scipy.io 内部会自动处理 C-order 和 F-order 的转换，不需要手动转置
        scipy.io.savemat(filename, processed_dict)
    else:
        raise ValueError("不支持的版本格式，请选择 'v7.3' 或 'v7'。")
    
    return True

def loadmat(filename, auto_transpose=True, squeeze_me=True):
    """
    自动检测版本并读取 MATLAB .mat 文件，支持自动多维数组转置恢复，
    并自动将数据格式转换为符合 Python 直觉的维度习惯。

    参数 (Parameters):
    ------------------
    filename : str
        需要读取的 .mat 文件路径。
    auto_transpose : bool, 可选 (默认: True)
        是否自动处理 Python 和 MATLAB 的跨语言内存主序差异。
    squeeze_me : bool, 可选 (默认: True)
        是否开启数组压缩功能。
        如果开启，会自动将 MATLAB 中的 1xN 或 Nx1 数组降维为真正的 1D NumPy 数组 (N,)。
        同时会将 1x1 的矩阵提取为单纯的标量。

    返回 (Returns):
    ---------------
    dict
        包含文件中所有变量的字典。
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"找不到文件: {filename}")

    # 读取魔法字节进行初步格式检测
    with open(filename, 'rb') as f:
        header = f.read(8)
    
    import h5py
    # 判断是否为 v7.3 HDF5 格式
    is_v73 = h5py.is_hdf5(filename)

    data_dict = {}

    if is_v73:
        with h5py.File(filename, 'r') as f:
            for key in f.keys():
                if not key.startswith('#'): 
                    data = np.array(f[key])
                    
                    # 检测并还原 MATLAB 的复数结构体
                    if data.dtype.names is not None and 'real' in data.dtype.names and 'imag' in data.dtype.names:
                        data = data['real'] + 1j * data['imag']
                    
                    if isinstance(data, np.ndarray):
                        # 标量与转置处理 (必须在 squeeze 之前转置，恢复实际物理形状)
                        if auto_transpose and data.ndim >= 2:
                            data = data.T
                        
                        # 维度压缩
                        if squeeze_me:
                            # np.squeeze 会自动剥离所有大小为 1 的维度
                            data = np.squeeze(data)
                        
                        # 提取标量处理
                        if data.ndim == 0:
                            # 提取 0维 数组为真正的标量值 (但保留 numpy 数据类型)
                            data = data[()]
                        elif not squeeze_me and data.shape == (1, 1):
                            # 如果用户关闭了压缩，但我们依然保持老版本的 1x1 标量提取兜底
                            data = data[0, 0]
                            
                    data_dict[key] = data
    else:
        import scipy.io
        # 对于 scipy，直接利用它内部极其完善的 squeeze_me 参数
        mat_data = scipy.io.loadmat(filename, squeeze_me=squeeze_me)
        for key, val in mat_data.items():
            if not key.startswith('__'):
                if isinstance(val, np.ndarray):
                    # scipy 在开启 squeeze_me 时，也会把 1x1 变成 0 维数组
                    if val.ndim == 0:
                        val = val[()]
                    # 如果用户关闭了压缩，兜底提取 1x1
                    elif not squeeze_me and val.shape == (1, 1):
                        val = val[0, 0]
                data_dict[key] = val

    return data_dict

def save_h5(filename, data_dict, compression=True):
    """
    将字典数据写入标准 HDF5 文件，支持复数处理和压缩。
    不包含 MATLAB 特征头，确保 Origin 和标准 HDF5 查看器完美兼容。

    参数 (Parameters):
    ------------------
    filename : str
        输出的 .h5 文件路径和名称。
    data_dict : dict
        需要写入的数据字典。
    compression : bool, 可选 (默认: True)
        是否进行数据压缩，使文件更小

    返回 (Returns):
    ---------------
    bool
        写入成功返回 True。
    """
    import h5py
    # 自动补全后缀
    if not filename.endswith('.h5') and not filename.endswith('.hdf5'):
        filename += '.h5'
        
    with h5py.File(filename, 'w') as f:
        for key, val in data_dict.items():
            data = np.asarray(val)
            
            # 处理数据类型：将整型转为双精度浮点
            if np.issubdtype(data.dtype, np.integer):
                data = data.astype(np.float64)
            
            # 压缩设置：对于大数据非常有帮助
            dataset_args = {"compression": "gzip", "compression_opts": 4} if compression else {}
            
            if np.iscomplexobj(data):
                # 采用复合类型存储复数
                complex_dt = np.dtype([('real', data.real.dtype), ('imag', data.imag.dtype)])
                mat_complex = np.empty(data.shape, dtype=complex_dt)
                mat_complex['real'] = data.real
                mat_complex['imag'] = data.imag
                f.create_dataset(key, data=mat_complex, **dataset_args)
                # 添加属性标记这是一个复数，方便后续自动读取
                f[key].attrs['is_complex'] = 1
            else:
                f.create_dataset(key, data=data, **dataset_args)
                
    # print(f"[成功] 数据已保存至标准 HDF5: {filename}")
    return True

def load_h5(filename):
    """
    从标准 HDF5 文件读取数据，并自动恢复复数结构。

    参数 (Parameters):
    ------------------
    filename : str
        读取的 .h5 文件路径和名称。

    返回 (Returns):
    ---------------
    dict
        读取的数据字典。
    """
    import h5py
    if not os.path.exists(filename):
        raise FileNotFoundError(f"找不到文件: {filename}")
        
    data_dict = {}
    try:
        with h5py.File(filename, 'r') as f:
            for key in f.keys():
                data = np.array(f[key])
                
                # 自动检测并恢复复数
                # 检查是否存在属性标记，或检查复合类型字段
                is_complex = f[key].attrs.get('is_complex', 0)
                has_fields = data.dtype.names is not None and 'real' in data.dtype.names
                
                if is_complex or has_fields:
                    data = data['real'] + 1j * data['imag']
                
                data_dict[key] = data
        return data_dict
    except Exception as e:
        print(f"错误：读取 H5 文件失败 - {str(e)}")
        return None

# *****************绘图增强函数******************
def create_cmap(color_list, cmap_name="custom_cmap"):
    """
    根据传入的颜色列表创建自定义的渐变色映射
    
    参数:
    ------------------
    color_list (list): 颜色列表，按顺序定义渐变路径。列表元素支持：
        - 颜色名称 (str): 例如 'black', 'red', 'white'
        - 十六进制色值 (str): 例如 '#000000', '#FF5733', '#FFFFFF'
        - RGB 浮点数元组 (范围 0.0-1.0): 例如 (0.0, 0.0, 0.0)
        - RGB 整数元组 (范围 0-255): 例如 (0, 0, 0)
      例如：[(0, 0, 0), (0.0, 0.0, 1.0), 'red', '#FFFFFF'] 黑色->蓝色->红色->白色
    cmap_name (str): 生成的 Colorbar 的名称，默认为 "custom_cmap"
    
    返回:
    ------------------
    LinearSegmentedColormap: 对应的颜色映射对象
    """
    import matplotlib.colors as mcolors
    from matplotlib.colors import LinearSegmentedColormap
    
    if not isinstance(color_list, list) or len(color_list) < 2:
        raise ValueError("color_list 必须是一个包含至少两种颜色的列表")

    processed_colors = []
    
    for color in color_list:
        # 如果是元组或列表格式的 RGB，检查是否需要从 0-255 归一化到 0-1
        if isinstance(color, (tuple, list)):
            if any(v > 1.0 for v in color):
                color = tuple(v / 255.0 for v in color)
                
        # 尝试将颜色转换为 matplotlib 标准的 RGB 格式
        try:
            valid_color = mcolors.to_rgb(color)
            processed_colors.append(valid_color)
        except ValueError:
            raise ValueError(f"无法识别的颜色输入: {color}。请检查格式是否正确。")

    # 根据处理后的颜色列表创建颜色映射
    cmap = LinearSegmentedColormap.from_list(
        cmap_name, 
        processed_colors, 
        N=256
    )
    
    return cmap

def set_colorbar_range(mappable, vmin, vmax):
    """
    方便地设置 matplotlib colorbar 的显示范围。
    
    参数:
    mappable : matplotlib 绘图对象 (例如 plt.imshow(), plt.scatter() 的返回值)
               或者是一个 colorbar 对象。
    vmin     : float, 颜色条的最小值
    vmax     : float, 颜色条的最大值
    """
    import matplotlib.pyplot as plt
    import matplotlib as mpl

    # 如果传入的是 colorbar 对象，则提取其底层的 mappable 对象
    if isinstance(mappable, mpl.colorbar.Colorbar):
        mappable = mappable.mappable
        
    # 设置颜色范围
    mappable.set_clim(vmin=vmin, vmax=vmax)
    
    # 获取当前的 figure 并请求重新绘制以更新显示
    plt.draw()


# *****************近远场变换函数*****************
def Estimate_focal(lamb, r, focal_theory):
    '''
    理论预估焦距偏移率，参考文章：[Focal shift in metasurface based lenses](https://doi.org/10.1364/OE.26.008001)

    参数
    ---------------
    lamb: 波长
    r: 透镜半径
    focal_theory: 理论焦距

    返回
    ---------------    
    focal_real: 实际焦距
    p: 透镜偏移率
    '''
    # 菲涅尔数
    N = r**2/lamb/focal_theory

    # 计算焦点的偏移率
    # 1.4641是圆形的情况
    p = 1.4641/(2*N+1.4641)
    focal_real = focal_theory*(1-p)

    return focal_real, p

def Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba', software='+'):
    '''
    基尔霍夫(Kirchhoff) 衍射积分公式

    参数: 
    ------------------
    lamb: 波长  
    x_near, y_near       : 近场位置数据，x_near和y_near应当是一维ndarry数组  
    E_near               : 近场的电场数据，E_near应当是二维ndarry数组  
    x_far, y_far, z_far  : 远场的位置数据，应当是一维数据或者数值  
    mode: 计算模式  
        'common'('c')     : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢  
        'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，仅windows下可用，需要joblib库  
        'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存  
        'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**  
    software: 波传播相位约定/来源软件类型  
        '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)  
        '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定  

    返回:
        E_far: 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))  
    '''
    # 数据类型检查
    # 检查波长 (必须是正实数)
    if not isinstance(lamb, (int, float)) or lamb <= 0:
        raise ValueError(f"波长 lamb 必须是大于0的实数，当前输入为: {lamb}")

    # 将近场坐标转为 numpy 数组并剔除多余维度
    x_near = np.atleast_1d(np.squeeze(np.asarray(x_near)))
    y_near = np.atleast_1d(np.squeeze(np.asarray(y_near)))
    E_near = np.asarray(E_near, dtype=np.complex128)

    if x_near.ndim != 1 or y_near.ndim != 1:
        raise ValueError(f"x_near 和 y_near 必须是一维数组。当前维度: x_near({x_near.ndim}D), y_near({y_near.ndim}D)")
    if E_near.ndim != 2:
        raise ValueError(f"E_near 必须是二维数组。当前维度: {E_near.ndim}D")

    # 检查近场网格尺寸是否与电场矩阵匹配
    expected_shape = (len(y_near), len(x_near))
    if E_near.shape != expected_shape:
        raise ValueError(f"E_near 的形状 {E_near.shape} 与近场坐标网格不匹配！期望形状为 (len(y_near), len(x_near)): {expected_shape}")

    # 检查远场坐标并转为 1D
    x_far = np.atleast_1d(np.squeeze(np.asarray(x_far)))
    y_far = np.atleast_1d(np.squeeze(np.asarray(y_far)))
    z_far = np.atleast_1d(np.squeeze(np.asarray(z_far)))

    if x_far.ndim != 1 or y_far.ndim != 1 or z_far.ndim != 1:
        raise ValueError("x_far, y_far, z_far 必须是标量或一维数组。")

    # 检查字符串参数类型
    if not isinstance(mode, str) or not isinstance(software, str):
        raise TypeError("mode 和 software 参数必须是字符串。")

    # 开始主体代码部分
    from tqdm.auto import tqdm
    # 确定相位约定符号
    software = software.upper()
    if software in ['+', 'FDTD', 'Lumerical']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")
    
    # 积分面积元 dx * dy，使数值结果与采样密度无关
    dx = x_near[1] - x_near[0] if len(x_near) > 1 else 1.0 # 注意最好用浮点数，避免使用整数值
    dy = y_near[1] - y_near[0] if len(y_near) > 1 else 1.0
    ds = dx * dy 

    k = 2 * np.pi / lamb
    X_far, Y_far, Z_far = np.meshgrid(x_far, y_far, z_far, indexing='ij')
    E_far = np.zeros_like(X_far, dtype=np.complex128)
    
    # 处理 r=0 的极小偏移量，防止除以零崩溃
    eps = 1e-12 

    if mode in ['common', 'c']:
        print(f'Using normal mode... (Phase convention: {software})')
        for ii in tqdm(range(len(y_near)), desc="Common Integration"):
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps) # 防止 r=0
                # 乘上了积分面元 ds，并且应用相位约定 sg
                E_far += (1/(sg*2j*lamb) * E_near[ii,jj]/r * np.exp(sg*1j*k*r) * (1 + Z_far/r)) * ds

    elif mode in ['threaded', 't']:
        print(f'Using joblib threaded mode... (Phase convention: {software})')
        from joblib import Parallel, delayed
        def compute_row(ii):
            row_result = np.zeros_like(X_far, dtype=np.complex128)
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                row_result += (1/(sg*2j*lamb) * E_near[ii,jj]/r * np.exp(sg*1j*k*r) * (1 + Z_far/r)) * ds
            return row_result
        
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) for ii in tqdm(range(len(y_near)), desc="Threaded Integration")
        )
        for row_result in results:
            E_far += row_result

    elif mode in ['vectorized', 'v']:
        print(f'Using vectorized mode... (Warning: High Memory Usage for large arrays) (Phase convention: {software})')
        # 远场占前三个维度: (Nx_f, Ny_f, Nz_f, 1, 1)
        X_f = X_far[..., np.newaxis, np.newaxis]
        Y_f = Y_far[..., np.newaxis, np.newaxis]
        Z_f = Z_far[..., np.newaxis, np.newaxis]
        
        # 近场占后两个维度: (1, 1, 1, Ny_n, Nx_n)
        X_n = x_near.reshape(1, 1, 1, 1, -1)
        Y_n = y_near.reshape(1, 1, 1, -1, 1)
        E_n = E_near.reshape(1, 1, 1, len(y_near), len(x_near))
        
        r = np.sqrt((X_f - X_n)**2 + (Y_f - Y_n)**2 + Z_f**2)
        r = np.maximum(r, eps)
        
        # 核心运算
        integrand = (1/(sg*2j*lamb)) * (E_n / r) * np.exp(sg*1j*k*r) * (1 + Z_f/r)
        
        # 沿着近场的 Y轴(axis=3) 和 X轴(axis=4) 积分求和
        E_far = np.sum(integrand, axis=(3, 4)) * ds

    elif mode in ['numba', 'n']:
        print(f'Using numba hybrid mode... (Phase convention: {software})')
        import numba as nb
        
        # 展平远场网格，以便在外层套用 tqdm 进度条
        shape_orig = X_far.shape
        X_flat = X_far.ravel()
        Y_flat = Y_far.ravel()
        Z_flat = Z_far.ravel()
        E_flat = np.zeros_like(X_flat, dtype=np.complex128)
        
        # 内部 Numba 函数：计算单个远场观察点接收到的所有近场积分 (启用多线程加速)
        @nb.njit(parallel=True, fastmath=True)
        def compute_single_far_point(xf, yf, zf, x_n, y_n, E_n, lamb, k, ds, sg):
            val = 0j
            y_len, x_len = len(y_n), len(x_n)
            # prange 支持对标量 val 的自动线程归约 (Reduction)
            for ii in nb.prange(y_len):
                for jj in range(x_len):
                    r = np.sqrt((xf - x_n[jj])**2 + (yf - y_n[ii])**2 + zf**2)
                    if r < 1e-12: r = 1e-12
                    val += (1/(sg*2j*lamb) * E_n[ii,jj]/r * np.exp(sg*1j*k*r) * (1 + zf/r)) * ds
            return val
        
        # 外层 Python 循环挂载 tqdm
        for i in tqdm(range(len(X_flat)), desc="Numba Integration"):
            E_flat[i] = compute_single_far_point(
                X_flat[i], Y_flat[i], Z_flat[i], 
                x_near, y_near, E_near, lamb, k, ds, sg
            )

        # 还原回 3D 矩阵形状
        E_far = E_flat.reshape(shape_orig)

    else:
        raise ValueError('Invalid mode(请检查输入的mode参数)')
        
    return E_far

def RayleighSommerfeld_Scalar(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba', software='+'):
    '''
    瑞利-索末菲(Rayleigh-Sommerfeld) 标量衍射积分公式
    
    参数: 
    ------------------
    lamb: 波长  
    x_near, y_near       : 近场位置数据，x_near和y_near应当是一维ndarry数组  
    E_near               : 近场的电场数据，E_near应当是二维ndarry数组  
    x_far, y_far, z_far  : 远场的位置数据，应当是一维数据或者数值  
    mode: 计算模式  
        'common'('c')     : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢  
        'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，需要joblib库  
        'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存  
        'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**  
    software: 波传播相位约定/来源软件类型  
        '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)  
        '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定  
        
    返回:
    ------------------
        E_far: 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))
    '''
    # 数据类型检查
    # 检查波长 (必须是正实数)
    if not isinstance(lamb, (int, float)) or lamb <= 0:
        raise ValueError(f"波长 lamb 必须是大于0的实数，当前输入为: {lamb}")

    # 将近场坐标转为 numpy 数组并剔除多余维度
    x_near = np.atleast_1d(np.squeeze(np.asarray(x_near)))
    y_near = np.atleast_1d(np.squeeze(np.asarray(y_near)))
    E_near = np.asarray(E_near, dtype=np.complex128)

    if x_near.ndim != 1 or y_near.ndim != 1:
        raise ValueError(f"x_near 和 y_near 必须是一维数组。当前维度: x_near({x_near.ndim}D), y_near({y_near.ndim}D)")
    if E_near.ndim != 2:
        raise ValueError(f"E_near 必须是二维数组。当前维度: {E_near.ndim}D")

    # 检查近场网格尺寸是否与电场矩阵匹配
    expected_shape = (len(y_near), len(x_near))
    if E_near.shape != expected_shape:
        raise ValueError(f"E_near 的形状 {E_near.shape} 与近场坐标网格不匹配！期望形状为 (len(y_near), len(x_near)): {expected_shape}")

    # 检查远场坐标并转为 1D
    x_far = np.atleast_1d(np.squeeze(np.asarray(x_far)))
    y_far = np.atleast_1d(np.squeeze(np.asarray(y_far)))
    z_far = np.atleast_1d(np.squeeze(np.asarray(z_far)))

    if x_far.ndim != 1 or y_far.ndim != 1 or z_far.ndim != 1:
        raise ValueError("x_far, y_far, z_far 必须是标量或一维数组。")

    # 检查字符串参数类型
    if not isinstance(mode, str) or not isinstance(software, str):
        raise TypeError("mode 和 software 参数必须是字符串。")

    # 主体计算代码
    from tqdm.auto import tqdm

    software = software.upper()
    if software in ['+', 'FDTD', 'Lumerical']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    # 计算近场积分面积元 dx * dy，保证能量量级随采样率守恒
    dx = x_near[1] - x_near[0] if len(x_near) > 1 else 1.0
    dy = y_near[1] - y_near[0] if len(y_near) > 1 else 1.0
    ds = dx * dy 

    k = 2 * np.pi / lamb
    # 生成远场目标网格
    X_far, Y_far, Z_far = np.meshgrid(x_far, y_far, z_far, indexing='ij')
    E_far = np.zeros_like(X_far, dtype=np.complex128)

    # 防止观察点与源点重合导致除以零 (r=0) 的极小偏移量
    eps = 1e-12 

    # 计算模块
    if mode in ['common', 'c']:
        print(f'Using common mode... (Phase convention: {software})')
        for ii in tqdm(range(len(y_near)), desc="Common Integration"):
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                # 瑞利索末菲公式: 1/(1j*lamb) 且倾斜因子为 Z_far/r
                E_far += (1/(sg*1j*lamb) * E_near[ii,jj]/r * np.exp(sg*1j*k*r) * (Z_far/r)) * ds

    elif mode in ['threaded', 't']:
        print(f'Using joblib threaded mode... (Phase convention: {software})')
        from joblib import Parallel, delayed
        def compute_row(ii):
            row_result = np.zeros_like(X_far, dtype=np.complex128)
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                row_result += (1/(sg*1j*lamb) * E_near[ii,jj]/r * np.exp(sg*1j*k*r) * (Z_far/r)) * ds
            return row_result
        
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) for ii in tqdm(range(len(y_near)), desc="Threaded Integration")
        )
        for row_result in results:
            E_far += row_result

    elif mode in ['vectorized', 'v']:
        print(f'Using vectorized mode... (Warning: Very High Memory Usage for large grids) (Phase convention: {software})')
        # 利用 5D 广播：远场占前三个维度，近场占后两个维度
        X_f = X_far[..., np.newaxis, np.newaxis]
        Y_f = Y_far[..., np.newaxis, np.newaxis]
        Z_f = Z_far[..., np.newaxis, np.newaxis]
        
        X_n = x_near.reshape(1, 1, 1, 1, -1)
        Y_n = y_near.reshape(1, 1, 1, -1, 1)
        E_n = E_near.reshape(1, 1, 1, len(y_near), len(x_near))
        
        r = np.sqrt((X_f - X_n)**2 + (Y_f - Y_n)**2 + Z_f**2)
        r = np.maximum(r, eps)
        
        integrand = (1/(sg*1j*lamb)) * (E_n / r) * np.exp(sg*1j*k*r) * (Z_f/r)

        # 对近场的 Y轴(axis=3) 和 X轴(axis=4) 积分求和
        E_far = np.sum(integrand, axis=(3, 4)) * ds

    elif mode in ['numba', 'n']:
        print(f'Using numba hybrid mode... (Phase convention: {software})')
        import numba as nb
        
        # 展平远场网格，以便在外层套用 tqdm 进度条
        shape_orig = X_far.shape
        X_flat = X_far.ravel()
        Y_flat = Y_far.ravel()
        Z_flat = Z_far.ravel()
        E_flat = np.zeros_like(X_flat, dtype=np.complex128)
        
        # 内部 Numba 函数：计算单个远场观察点接收到的所有近场积分 (启用多线程加速)
        @nb.njit(parallel=True, fastmath=True)
        def compute_single_far_point(xf, yf, zf, x_n, y_n, E_n, lamb, k, ds, sg):
            val = 0j
            y_len, x_len = len(y_n), len(x_n)
            # prange 支持对标量 val 的自动线程归约 (Reduction)
            for ii in nb.prange(y_len):
                for jj in range(x_len):
                    r = np.sqrt((xf - x_n[jj])**2 + (yf - y_n[ii])**2 + zf**2)
                    if r < 1e-12: r = 1e-12
                    val += (1/(sg*1j*lamb) * E_n[ii,jj]/r * np.exp(sg*1j*k*r) * (zf/r)) * ds
            return val
            
        # 外层 Python 循环挂载 tqdm
        for i in tqdm(range(len(X_flat)), desc="Numba Integration"):
            E_flat[i] = compute_single_far_point(
                X_flat[i], Y_flat[i], Z_flat[i], 
                x_near, y_near, E_near, lamb, k, ds, sg
            )
            
        # 还原回 3D 矩阵形状
        E_far = E_flat.reshape(shape_orig)

    else:
        raise ValueError('Invalid mode (请检查输入的 mode 参数)')
        
    return E_far

def RayleighSommerfeld_Vector(lamb, x_near, y_near, E_near_x, E_near_y, x_far, y_far, z_far, mode='numba', software='+'):
    '''
    瑞利-索末菲(Rayleigh-Sommerfeld) 矢量衍射积分公式

    参数: 
    ------------------
    lamb: 波长  
    x_near, y_near        : 近场位置数据，x_near和y_near应当是一维ndarry数组  
    E_near                : 近场的电场数据，E_near应当是二维ndarry数组  
    x_far, y_far, z_far   : 远场的位置数据，应当是一维数据或者数值  
    mode: 计算模式  
        'common'('c')     : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢  
        'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，需要joblib库  
        'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存  
        'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**  
    software: 波传播相位约定/来源软件类型
        '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)
        '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定
        
    返回:
    ------------------
    E_total                   : 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))  
    E_far_x, E_far_y, E_far_z : 远场电场各个分量数据，形状为 (len(x_far), len(y_far), len(z_far))
    '''
    # 检查波长 (必须是正实数)
    if not isinstance(lamb, (int, float)) or lamb <= 0:
        raise ValueError(f"波长 lamb 必须是大于0的实数，当前输入为: {lamb}")

    # 将近场坐标转为 1D numpy 数组
    x_near = np.atleast_1d(np.squeeze(np.asarray(x_near)))
    y_near = np.atleast_1d(np.squeeze(np.asarray(y_near)))
    
    if x_near.ndim != 1 or y_near.ndim != 1:
        raise ValueError(f"x_near 和 y_near 必须是一维数组。当前维度: x_near({x_near.ndim}D), y_near({y_near.ndim}D)")

    # 将近场电场分量转为复数数组
    E_near_x = np.asarray(E_near_x, dtype=np.complex128)
    E_near_y = np.asarray(E_near_y, dtype=np.complex128)

    if E_near_x.ndim != 2 or E_near_y.ndim != 2:
        raise ValueError(f"E_near_x 和 E_near_y 必须是二维数组。当前维度: Ex({E_near_x.ndim}D), Ey({E_near_y.ndim}D)")

    # 检查近场网格尺寸是否与电场矩阵匹配
    expected_shape = (len(y_near), len(x_near))
    if E_near_x.shape != expected_shape or E_near_y.shape != expected_shape:
        raise ValueError(f"近场电场矩阵的形状与坐标网格不匹配！\n期望形状: {expected_shape}\n实际形状: E_near_x{E_near_x.shape}, E_near_y{E_near_y.shape}")

    # 检查远场坐标并转为 1D
    x_far = np.atleast_1d(np.squeeze(np.asarray(x_far)))
    y_far = np.atleast_1d(np.squeeze(np.asarray(y_far)))
    z_far = np.atleast_1d(np.squeeze(np.asarray(z_far)))

    if x_far.ndim != 1 or y_far.ndim != 1 or z_far.ndim != 1:
        raise ValueError("x_far, y_far, z_far 必须是标量或一维数组。")

    # 检查字符串参数类型
    if not isinstance(mode, str) or not isinstance(software, str):
        raise TypeError("mode 和 software 参数必须是字符串。")
    
    # 主体代码部分
    from tqdm.auto import tqdm
    software = software.upper()
    if software in ['+', 'FDTD', 'Lumerical']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    # 计算近场积分面积元 dx * dy，保证能量量级随采样率守恒
    dx = x_near[1] - x_near[0] if len(x_near) > 1 else 1.0
    dy = y_near[1] - y_near[0] if len(y_near) > 1 else 1.0
    ds = dx * dy 

    k = 2 * np.pi / lamb
    # 生成远场目标网格
    X_far, Y_far, Z_far = np.meshgrid(x_far, y_far, z_far, indexing='ij')
    
    E_far_x = np.zeros_like(X_far, dtype=np.complex128)
    E_far_y = np.zeros_like(X_far, dtype=np.complex128)
    E_far_z = np.zeros_like(X_far, dtype=np.complex128)

    eps = 1e-12 

    # 计算模块
    if mode in ['common', 'c']:
        print(f'Using common mode... (Phase convention: {software})')
        for ii in tqdm(range(len(y_near)), desc="Common Vector Integration"):
            for jj in range(len(x_near)):
                dx_r = X_far - x_near[jj]
                dy_r = Y_far - y_near[ii]
                r = np.sqrt(dx_r**2 + dy_r**2 + Z_far**2)
                r = np.maximum(r, eps)
                
                # 提取公共核函数
                kernel = (-1/(2*np.pi)) * (np.exp(sg*1j*k*r) / r**2) * (sg*1j*k - 1/r) * ds
                
                Ex_n, Ey_n = E_near_x[ii, jj], E_near_y[ii, jj]
                # Ex和Ey由z距离主导，Ez由波阵面倾斜(x,y投影)主导
                E_far_x += Ex_n * Z_far * kernel
                E_far_y += Ey_n * Z_far * kernel
                E_far_z += (Ex_n * dx_r + Ey_n * dy_r) * kernel

    elif mode in ['threaded', 't']:
        print(f'Using joblib threaded mode... (Phase convention: {software})')
        from joblib import Parallel, delayed
        def compute_row(ii):
            row_x, row_y, row_z = np.zeros_like(X_far, dtype=np.complex128), np.zeros_like(X_far, dtype=np.complex128), np.zeros_like(X_far, dtype=np.complex128)
            for jj in range(len(x_near)):
                dx_r = X_far - x_near[jj]
                dy_r = Y_far - y_near[ii]
                r = np.sqrt(dx_r**2 + dy_r**2 + Z_far**2)
                r = np.maximum(r, eps)
                
                kernel = (-1/(2*np.pi)) * (np.exp(sg*1j*k*r) / r**2) * (sg*1j*k - 1/r) * ds
                Ex_n, Ey_n = E_near_x[ii, jj], E_near_y[ii, jj]
                row_x += Ex_n * Z_far * kernel
                row_y += Ey_n * Z_far * kernel
                row_z += (Ex_n * dx_r + Ey_n * dy_r) * kernel
            return row_x, row_y, row_z
        
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) for ii in tqdm(range(len(y_near)), desc="Threaded Vector Integration")
        )
        for rx, ry, rz in results:
            E_far_x += rx; E_far_y += ry; E_far_z += rz

    elif mode in ['vectorized', 'v']:
        print(f'Using vectorized mode... (Warning: High Memory Usage) (Phase convention: {software})')
        X_f = X_far[..., np.newaxis, np.newaxis]
        Y_f = Y_far[..., np.newaxis, np.newaxis]
        Z_f = Z_far[..., np.newaxis, np.newaxis]
        
        X_n = x_near.reshape(1, 1, 1, 1, -1)
        Y_n = y_near.reshape(1, 1, 1, -1, 1)
        Ex_n = E_near_x.reshape(1, 1, 1, len(y_near), len(x_near))
        Ey_n = E_near_y.reshape(1, 1, 1, len(y_near), len(x_near))
        
        dx_r = X_f - X_n
        dy_r = Y_f - Y_n
        r = np.sqrt(dx_r**2 + dy_r**2 + Z_f**2)
        r = np.maximum(r, eps)
        
        kernel = (-1/(2*np.pi)) * (np.exp(sg*1j*k*r) / r**2) * (sg*1j*k - 1/r) * ds

        # 沿着近场坐标(axis=3, 4)积分求和
        E_far_x = np.sum(Ex_n * Z_f * kernel, axis=(3, 4))
        E_far_y = np.sum(Ey_n * Z_f * kernel, axis=(3, 4))
        E_far_z = np.sum((Ex_n * dx_r + Ey_n * dy_r) * kernel, axis=(3, 4))

    elif mode in ['numba', 'n']:
        print(f'Using numba hybrid mode... (Phase convention: {software})')
        import numba as nb
        
        # 展平远场网格，以便在外层套用 tqdm 进度条
        shape_orig = X_far.shape
        X_flat, Y_flat, Z_flat = X_far.ravel(), Y_far.ravel(), Z_far.ravel()
        E_flat_x = np.zeros_like(X_flat, dtype=np.complex128)
        E_flat_y = np.zeros_like(X_flat, dtype=np.complex128)
        E_flat_z = np.zeros_like(X_flat, dtype=np.complex128)
        
        # 内部 Numba 函数：计算单个远场观察点接收到的所有近场积分 (启用多线程加速)
        @nb.njit(parallel=True, fastmath=True)
        def compute_single_far_point_vector(xf, yf, zf, x_n, y_n, Ex_n, Ey_n, lamb, k, ds, sg):
            val_x, val_y, val_z = 0j, 0j, 0j
            y_len, x_len = len(y_n), len(x_n)
            
            # prange 支持对标量 val 的自动线程归约 (Reduction)
            for ii in nb.prange(y_len):
                for jj in range(x_len):
                    dx_r = xf - x_n[jj]
                    dy_r = yf - y_n[ii]
                    r = np.sqrt(dx_r**2 + dy_r**2 + zf**2)
                    if r < 1e-12: r = 1e-12
                    
                    kernel = (-1/(2*np.pi)) * (np.exp(sg*1j*k*r) / r**2) * (sg*1j*k - 1/r) * ds
                    ex, ey = Ex_n[ii, jj], Ey_n[ii, jj]
                    
                    val_x += ex * zf * kernel
                    val_y += ey * zf * kernel
                    val_z += (ex * dx_r + ey * dy_r) * kernel

            return val_x, val_y, val_z

        # 外层 Python 循环挂载 tqdm 
        for i in tqdm(range(len(X_flat)), desc="Numba Vector Integration"):
            vx, vy, vz = compute_single_far_point_vector(
                X_flat[i], Y_flat[i], Z_flat[i], 
                x_near, y_near, E_near_x, E_near_y, lamb, k, ds, sg
            )
            E_flat_x[i], E_flat_y[i], E_flat_z[i] = vx, vy, vz
        
        # 还原回 3D 矩阵形状
        E_far_x, E_far_y, E_far_z = E_flat_x.reshape(shape_orig), E_flat_y.reshape(shape_orig), E_flat_z.reshape(shape_orig)

    else:
        raise ValueError('Invalid mode')
        
    E_total = np.sqrt(np.abs(E_far_x)**2 + np.abs(E_far_y)**2 + np.abs(E_far_z)**2)
    return E_total, E_far_x, E_far_y, E_far_z

def AngularSpectrum_Vector(lamb, x_near, y_near, E_near_x, E_near_y, x_far, y_far, z_far, mode='numba', software='+'):
    '''
    矢量角谱法 (Vector Angular Spectrum) 衍射传播
    
    参数:
    ------------------
    lamb: 波长  
    x_near, y_near      : 近场平面网格坐标 (一维数组)  
    E_near_x, E_near_y  : 近场电场横向分量 (二维数组)  
    x_far, y_far, z_far : 远场坐标 (允许为单个数字或一维数组)  
    mode: 计算模式  
        'fft'('f')    : 快速傅里叶变换，计算速度极快，占用计算资源很小，严格要求 x_far, y_far 与近场网格完全一致。  
        'numba'('n')  : 逆傅里叶积分。允许计算任意形状远场，不受限制，占用计算资源较大。  
    software: 'FDTD' (默认) 或 'COMSOL'software: 波传播相位约定/来源软件类型  
        '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)  
        '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定  

    返回:  
    ------------------
    E_total                   : 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))  
    E_far_x, E_far_y, E_far_z : 远场电场各个分量数据，形状为 (len(x_far), len(y_far), len(z_far))  
    '''
    # 检查波长 (必须是正实数)
    if not isinstance(lamb, (int, float)) or lamb <= 0:
        raise ValueError(f"波长 lamb 必须是大于0的实数，当前输入为: {lamb}")

    # 将近场坐标转为 1D numpy 数组
    x_near = np.atleast_1d(np.squeeze(np.asarray(x_near)))
    y_near = np.atleast_1d(np.squeeze(np.asarray(y_near)))
    
    if x_near.ndim != 1 or y_near.ndim != 1:
        raise ValueError(f"x_near 和 y_near 必须是一维数组。当前维度: x_near({x_near.ndim}D), y_near({y_near.ndim}D)")

    # 将近场电场分量转为复数数组
    E_near_x = np.asarray(E_near_x, dtype=np.complex128)
    E_near_y = np.asarray(E_near_y, dtype=np.complex128)

    if E_near_x.ndim != 2 or E_near_y.ndim != 2:
        raise ValueError(f"E_near_x 和 E_near_y 必须是二维数组。当前维度: Ex({E_near_x.ndim}D), Ey({E_near_y.ndim}D)")

    # 检查近场网格尺寸是否与电场矩阵匹配
    expected_shape = (len(y_near), len(x_near))
    if E_near_x.shape != expected_shape or E_near_y.shape != expected_shape:
        raise ValueError(f"近场电场矩阵的形状与坐标网格不匹配！\n期望形状: {expected_shape}\n实际形状: E_near_x{E_near_x.shape}, E_near_y{E_near_y.shape}")

    # 检查远场坐标并转为 1D
    x_far = np.atleast_1d(np.squeeze(np.asarray(x_far)))
    y_far = np.atleast_1d(np.squeeze(np.asarray(y_far)))
    z_far = np.atleast_1d(np.squeeze(np.asarray(z_far)))

    if x_far.ndim != 1 or y_far.ndim != 1 or z_far.ndim != 1:
        raise ValueError("x_far, y_far, z_far 必须是标量或一维数组。")

    # 检查字符串参数类型
    if not isinstance(mode, str) or not isinstance(software, str):
        raise TypeError("mode 和 software 参数必须是字符串。")

    # 主体代码部分
    from tqdm.auto import tqdm
    software = software.upper()
    if software in ['+', 'FDTD', 'Lumerical']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    Nx, Ny = len(x_near), len(y_near)
    dx = x_near[1] - x_near[0] if Nx > 1 else 1.0
    dy = y_near[1] - y_near[0] if Ny > 1 else 1.0

    # ==========================================
    # 生成空间频率坐标系 (K-space / F-space)
    # ==========================================
    # 获取傅里叶频率并移位，使其中心为0
    fx = np.fft.fftshift(np.fft.fftfreq(Nx, dx))
    fy = np.fft.fftshift(np.fft.fftfreq(Ny, dy))
    FX, FY = np.meshgrid(fx, fy, indexing='xy')

    # 积分面元
    dfx = fx[1] - fx[0] if Nx > 1 else 1.0
    dfy = fy[1] - fy[0] if Ny > 1 else 1.0
    
    # ==========================================
    # 计算初始平面的角谱 (2D FFT)
    # ==========================================
    # 连续傅里叶变换的离散近似: 需乘以物理面元 dx*dy
    # 必须先用 ifftshift 将物理坐标原点平移到矩阵左上角，再做 FFT，最后再用 fftshift 将低频移回中心。
    Ax = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(E_near_x))) * (dx * dy)
    Ay = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(E_near_y))) * (dx * dy)
    
    # ==========================================
    # 求解纵向空间频率 fz 和 纵向角谱 Az
    # ==========================================
    f_r_sq = FX**2 + FY**2
    limit_sq = 1 / lamb**2
    
    # 区分传播波 (Propagating) 和 倏逝波 (Evanescent)
    # 将 f_z 严格拆分为实部和虚部，彻底消除 COMSOL 倏逝波衰减方向的歧义
    fz_real = np.where(f_r_sq <= limit_sq, np.sqrt(np.maximum(limit_sq - f_r_sq, 0)), 0.0)
    fz_imag = np.where(f_r_sq > limit_sq, np.sqrt(np.maximum(f_r_sq - limit_sq, 0)), 0.0)
    
    # 组合为复数供 Ez 计算使用
    # 无论正负约定，传播方向均向着 +z。
    # 对于 sg=1, kz = fz_real + i*fz_imag; 对于 sg=-1, kz = fz_real - i*fz_imag
    fz_eff = fz_real + sg * 1j * fz_imag
    fz_safe = np.where(np.abs(fz_eff) < 1e-12, 1e-12, fz_eff)
    
    # 散度定理 (k·A = 0) 推导出的 Az 分量
    # 散度定理修正: 高斯定理在两套约定中会导致正负号切换
    Az = -(FX * Ax + FY * Ay) / (sg * fz_safe)

    # ==========================================
    # 传播计算 (根据模式选择)
    # ==========================================
    import warnings
    if mode in ['fft', 'f']:
        # 检查传入的远场 xy 坐标是否与近场等价
        is_x_match = (x_far.shape == x_near.shape) and np.allclose(x_far, x_near)
        is_y_match = (y_far.shape == y_near.shape) and np.allclose(y_far, y_near)

        if not (is_x_match and is_y_match):
            warnings.warn(
                "在 'fft' 模式下, 远场网格必须与近场网格完全相同！\n"
                "程序已自动忽略您输入的 x_far 和 y_far，将强制输出在近场网格上的计算结果。\n"
                "如果需要计算特定坐标点（如轴向扫描），请将 mode 设置为 'numba'。", 
                UserWarning
            )
            
        print(f"Using ultra-fast FFT mode... (Phase convention: {software})")
        E_far_x = np.zeros((Ny, Nx, len(z_far)), dtype=np.complex128)
        E_far_y = np.zeros((Ny, Nx, len(z_far)), dtype=np.complex128)
        E_far_z = np.zeros((Ny, Nx, len(z_far)), dtype=np.complex128)
        
        # 对于每一个 Z 截面，直接用逆傅里叶变换 (IFFT) 还原回空间域
        for i, z in enumerate(tqdm(z_far, desc="FFT Propagating Z-planes")):
            # Z传播传递函数：实部控制相位振荡，虚部强制进行纯物理衰减(不依赖于软件约定)
            H = np.exp(sg * 1j * 2 * np.pi * fz_real * z) * np.exp(-2 * np.pi * fz_imag * z)
            
            # 连续逆变换离散化抵消因子: 1/(dx*dy)
            E_far_x[:, :, i] = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(Ax * H))) / (dx * dy)
            E_far_y[:, :, i] = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(Ay * H))) / (dx * dy)
            E_far_z[:, :, i] = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(Az * H))) / (dx * dy)
            
        E_total = np.sqrt(np.abs(E_far_x)**2 + np.abs(E_far_y)**2 + np.abs(E_far_z)**2)
        return E_total, E_far_x, E_far_y, E_far_z

    elif mode in ['numba', 'n']:
        print(f"Using numba manual inverse-FT mode... (Phase convention: {software})")
        import numba as nb
        X_far, Y_far, Z_far = np.meshgrid(x_far, y_far, z_far, indexing='ij')
        
        shape_orig = X_far.shape
        X_flat, Y_flat, Z_flat = X_far.ravel(), Y_far.ravel(), Z_far.ravel()
        E_flat_x = np.zeros_like(X_flat, dtype=np.complex128)
        E_flat_y = np.zeros_like(X_flat, dtype=np.complex128)
        E_flat_z = np.zeros_like(X_flat, dtype=np.complex128)
        
        # Numba 内核: 将预先用 FFT 算好的角谱，在任意指定空间坐标处积分
        @nb.njit(parallel=True, fastmath=True)
        def compute_inverse_integral(xf, yf, zf, fx, fy, Ax, Ay, Az, dfx, dfy, lamb, sg):
            val_x, val_y, val_z = 0j, 0j, 0j
            Ny, Nx = Ax.shape
            for ii in nb.prange(Ny):
                for jj in range(Nx):
                    f_x, f_y = fx[jj], fy[ii]
                    f_r_sq = f_x**2 + f_y**2
                    
                    f_z_r = np.sqrt(1/lamb**2 - f_r_sq) if f_r_sq <= 1/lamb**2 else 0.0
                    f_z_i = 0.0 if f_r_sq <= 1/lamb**2 else np.sqrt(f_r_sq - 1/lamb**2)
                        
                    # 空间横向频率由FFT基底自带(不反转)，而轴向Z传播应用相位约定sg，并进行强制物理衰减
                    phase = np.exp(1j * 2 * np.pi * (f_x*xf + f_y*yf)) * \
                            np.exp(sg * 1j * 2 * np.pi * f_z_r * zf - 2 * np.pi * f_z_i * zf)
                    
                    val_x += Ax[ii, jj] * phase * dfx * dfy
                    val_y += Ay[ii, jj] * phase * dfx * dfy
                    val_z += Az[ii, jj] * phase * dfx * dfy
            return val_x, val_y, val_z

        for i in tqdm(range(len(X_flat)), desc="Numba Angular Integration"):
            vx, vy, vz = compute_inverse_integral(
                X_flat[i], Y_flat[i], Z_flat[i], 
                fx, fy, Ax, Ay, Az, dfx, dfy, lamb, sg
            )
            E_flat_x[i], E_flat_y[i], E_flat_z[i] = vx, vy, vz

        E_far_x, E_far_y, E_far_z = E_flat_x.reshape(shape_orig), E_flat_y.reshape(shape_orig), E_flat_z.reshape(shape_orig)
        E_total = np.sqrt(np.abs(E_far_x)**2 + np.abs(E_far_y)**2 + np.abs(E_far_z)**2)
        
        return E_total, E_far_x, E_far_y, E_far_z
    else:
        raise ValueError("Invalid mode. Please use 'fft' or 'numba'.")


# ***************lumerical相关函数***************
def detect_version(lumerical_root):
    """检测Lumerical安装目录下的有效版本号"""
    try:
        if not os.path.exists(lumerical_root):
            return None
            
        # 检查是否存在v+三位数字的文件夹
        for item in os.listdir(lumerical_root):
            if os.path.isdir(os.path.join(lumerical_root, item)):
                # 匹配v+三位数字的模式，例如v231, v242
                if re.match(r'^v\d{3}$', item):
                    # 验证该目录下是否存在lumapi.py
                    lumapi_path = os.path.join(lumerical_root, item, "api", "python", "lumapi.py")
                    if os.path.exists(lumapi_path):
                        return item
        return None
    except Exception:
        return None

def get_lumapi_path(lumerical_root, version):
    """从Lumerical根路径和版本获取lumapi.py路径"""
    base = os.path.join(lumerical_root, version)
    p1 = os.path.join(base, "Lumerical", "api", "python", "lumapi.py")
    if os.path.exists(p1): return p1
    p2 = os.path.join(base, "api", "python", "lumapi.py")
    if os.path.exists(p2): return p2
    return None

def validate_path(lumerical_root: str, version: str = None) -> object:
    """验证Lumerical路径有效性并返回lumapi对象
    
    参数:
    lumerical_root: Lumerical安装根目录
    version: 版本号（可选），如"v241"
    
    返回:
    lumapi对象或None
    """
    try:
        if not lumerical_root:
            print("错误：路径不能为空")
            return None
            
        lumerical_root = os.path.abspath(lumerical_root)
        
        # 如果没有提供版本号，尝试自动检测
        if not version:
            version = detect_version(lumerical_root)
            if not version:
                print(f"错误：在指定路径未找到有效的Lumerical版本 (查找路径：{lumerical_root})")
                return None
        
        # 获取lumapi.py的完整路径
        lumapi_path = get_lumapi_path(lumerical_root, version)
        
        if not lumapi_path:
            print(f"错误：在指定路径未找到 lumapi.py 文件（查找路径：{lumapi_path}）")
            return None
            
        # 测试导入
        spec = importlib.util.spec_from_file_location('lumapi', lumapi_path)
        lumapi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lumapi)

        if platform.system() == "Windows":
            # windows系统导入dll目录
            os.add_dll_directory(lumerical_root)
        
        return lumapi
        
    except Exception as e:
        print(f"错误：路径验证失败 - {str(e)}")
        return None

class lumerical:
    def __init__(self, lumerical_path='', version='', config_path=CONFIG_PATH):
        self.config_path = config_path
        self.lumapi = None
        self.lumerical_path = lumerical_path
        self.version = version
        
        # 尝试加载配置
        self._load_config()

    def _load_config(self):
        """内部方法：尝试从参数或配置文件加载 lumapi"""
        try:
            path = self.lumerical_path
            ver = self.version
            
            # 如果初始化时没给路径，尝试读配置
            if not path:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    path = config.get('lumerical_path')
                    ver = config.get('version')
            
            if path:
                self.lumapi = validate_path(path, ver)
                self.lumerical_path = path
                self.version = ver
        except Exception:
            self.lumapi = None

    def __bool__(self):
        """判断配置是否成功，允许直接使用 if lumapi: 来判断"""
        return self.lumapi is not None

    def _check_config_and_prompt(self):
        """核心逻辑：检查配置状态，若无效则引导用户使用 LumAPI 命令"""
        if self.lumapi is None:
            print("\n" + "*" * 60)
            print("【配置错误】未检测到有效的 Lumerical 环境。")
            print("原因可能是：")
            print("1. 尚未进行初始化配置。")
            print("2. 配置文件 config.json 损坏或路径已失效。")
            print("\n请在终端执行以下命令进行配置：")
            print("    LumAPI")
            print("或者使用命令行配置程序：")
            print("    LumAPI_CLI")
            print("*" * 60 + "\n")
            # 退出程序或抛出异常，防止后续调用崩溃
            sys.exit(1)

    def FDTD(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        self._check_config_and_prompt()
        return FDTD(self.lumapi, filename, key, hide, serverArgs, remoteArgs, **kwargs)
    
    def MODE(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        self._check_config_and_prompt()
        return MODE(self.lumapi, filename, key, hide, serverArgs, remoteArgs, **kwargs)
    
    def DEVICE(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        self._check_config_and_prompt()
        return DEVICE(self.lumapi, filename, key, hide, serverArgs, remoteArgs, **kwargs)
    
    def INTERCONNECT(self, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        self._check_config_and_prompt()
        return INTERCONNECT(self.lumapi, filename, key, hide, serverArgs, remoteArgs, **kwargs)

class LumFuncBase:
    """Lumerical 功能基类，处理通用的 API 转发、兼容性初始化和参数预处理"""
    def __init__(self, lumapi_module, product_name, filename=None, key=None, hide=False, serverArgs=None, remoteArgs=None, **kwargs):
        # 修复 Python 可变默认参数陷阱
        if serverArgs is None:
            serverArgs = {}
        if remoteArgs is None:
            remoteArgs = {}

        # 动态获取对应的 Lumerical 构造函数 (例如 lumapi_module.FDTD)
        target_constructor = getattr(lumapi_module, product_name)

        try:
            # 首先尝试 v24R1 及更新版本的完整参数调用
            self._handle = target_constructor(
                filename=filename, key=key, hide=hide, 
                serverArgs=serverArgs, remoteArgs=remoteArgs, **kwargs
            )
        except TypeError as e:
            # 捕获旧版本不支持 remoteArgs 的错误并降级调用
            if 'remoteArgs' in str(e) or 'unexpected keyword argument' in str(e):
                self._handle = target_constructor(
                    filename=filename, key=key, hide=hide, 
                    serverArgs=serverArgs, **kwargs
                )
            else:
                raise # 其他 TypeError 原样抛出

        self.filename = filename

    def _process_arg(self, arg):
        """
        核心预处理逻辑：
        1. 整型 ndarray -> 浮点型
        2. 一维 ndarray (len > 1) -> 二维 [[...]]
        """
        if isinstance(arg, np.ndarray):
            # 检查是否为整型数组并转换
            if np.issubdtype(arg.dtype, np.integer):
                arg = arg.astype(float)
            
            # 检查一维数组且长度不为 1，进行升维
            if arg.ndim == 1 and arg.shape[0] != 1:
                arg = arg[np.newaxis, :]
        return arg

    def __getattr__(self, name):
        # 从 Lumerical 原始句柄中获取属性或方法
        attr = getattr(self._handle, name)
        
        # 如果不是可调用对象（如变量、常量），直接返回
        if not callable(attr):
            return attr

        # 如果是方法，返回包装函数进行参数拦截处理
        def wrapper(*args, **kwargs):
            # 处理位置参数
            new_args = tuple(self._process_arg(arg) for arg in args)
            # 处理关键字参数
            new_kwargs = {k: self._process_arg(v) for k, v in kwargs.items()}
            
            # 调用原始 API 并返回结果
            return attr(*new_args, **new_kwargs)
            
        return wrapper
    
    def __del__(self):
        """析构函数：在对象销毁时自动尝试关闭 Lumerical 进程"""
        try:
            # 检查句柄是否存在且是否有 close 方法
            if hasattr(self, '_handle') and self._handle:
                # print(f"正在自动关闭 Lumerical 句柄...")
                self._handle.close()
        except Exception:
            # 忽略退出时的任何异常，确保不会产生冗余错误信息
            pass
    
class FDTD(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs=None, remoteArgs=None, **kwargs):
        super().__init__(lumapi, 'FDTD', filename, key, hide, serverArgs, remoteArgs, **kwargs)

class MODE(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs=None, remoteArgs=None, **kwargs):
        super().__init__(lumapi, 'MODE', filename, key, hide, serverArgs, remoteArgs, **kwargs)

class DEVICE(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs=None, remoteArgs=None, **kwargs):
        super().__init__(lumapi, 'DEVICE', filename, key, hide, serverArgs, remoteArgs, **kwargs)

class INTERCONNECT(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs=None, remoteArgs=None, **kwargs):
        super().__init__(lumapi, 'INTERCONNECT', filename, key, hide, serverArgs, remoteArgs, **kwargs)
    
lumapi = lumerical()

if __name__ == '__main__':
    um = 1e-6
    nx, ny = 100, 100
    S = 0.5*um
    material_base = 'Au (Gold) - CRC'

    fdtd = lumapi.FDTD()
    fdtd.addrect(
        name="base",
        x=0,
        y=0,
        x_span=nx*S,
        y_span=ny*S,
        z_min=-0.3*um,
        z_max=0,
        material=material_base,
    )
    # fdtd.save()
    # fdtd.run()
    fdtd.close()















