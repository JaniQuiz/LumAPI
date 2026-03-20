import numpy as np
import os
import sys
import json
import importlib
import importlib.util
import re, platform

current_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(current_dir, 'config.json')

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
    return os.path.join(lumerical_root, version, "api", "python", "lumapi.py")


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
        
        if not os.path.exists(lumapi_path):
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


def create_cmap(color_list, cmap_name="custom_cmap"):
    """
    根据传入的颜色列表创建自定义的渐变色映射
    
    参数:
    color_list (list): 颜色列表，按顺序定义渐变路径。列表元素支持：
        - 颜色名称 (str): 例如 'black', 'red', 'white'
        - 十六进制色值 (str): 例如 '#000000', '#FF5733', '#FFFFFF'
        - RGB 浮点数元组 (范围 0.0-1.0): 例如 (0.0, 0.0, 0.0)
        - RGB 整数元组 (范围 0-255): 例如 (0, 0, 0)
      例如：[(0, 0, 0), (0.0, 0.0, 1.0), 'red', '#FFFFFF'] 黑色->蓝色->红色->白色
    cmap_name (str): 生成的 Colorbar 的名称，默认为 "custom_cmap"
    
    返回:
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


def Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba', software='+'):
    '''
    基尔霍夫(Kirchhoff) 衍射积分公式

    参数: 
        lamb: 波长
        x_near, y_near: 近场位置数据，x_near和y_near应当是一维ndarry数组
        E_near: 近场的电场数据，E_near应当是二维ndarry数组
        x_far, y_far, z_far: 远场的位置数据，应当是一维数据或者数值
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
    from tqdm.auto import tqdm

    # 确定相位约定符号
    software = software.upper()
    if software in ['+', 'FDTD', 'LUMERICAL']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    # 确保近场坐标也是数组
    x_near, y_near = np.atleast_1d(x_near), np.atleast_1d(y_near)

    # 远场转换为 ndarray
    x_far, y_far, z_far = np.atleast_1d(x_far), np.atleast_1d(y_far), np.atleast_1d(z_far)
    
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
        lamb: 波长
        x_near, y_near: 近场位置数据，x_near和y_near应当是一维ndarry数组
        E_near: 近场的电场数据，E_near应当是二维ndarry数组
        x_far, y_far, z_far: 远场的位置数据，应当是一维数据或者数值
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
    from tqdm.auto import tqdm

    software = software.upper()
    if software in ['+', 'FDTD', 'LUMERICAL']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    # 确保近场坐标也是数组
    x_near, y_near = np.atleast_1d(x_near), np.atleast_1d(y_near)

    # 远场转换为 ndarray
    x_far, y_far, z_far = np.atleast_1d(x_far), np.atleast_1d(y_far), np.atleast_1d(z_far)

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
        lamb: 波长
        x_near, y_near: 近场位置数据，x_near和y_near应当是一维ndarry数组
        E_near: 近场的电场数据，E_near应当是二维ndarry数组
        x_far, y_far, z_far: 远场的位置数据，应当是一维数据或者数值
        mode: 计算模式
            'common'('c')     : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢
            'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，仅windows下可用，需要joblib库
            'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存
            'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**
        software: 波传播相位约定/来源软件类型
            '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)
            '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定
        
    返回:
        E_total: 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))
        E_far_x, E_far_y, E_far_z: 远场电场各个分量数据，形状为 (len(x_far), len(y_far), len(z_far))
    '''
    from tqdm.auto import tqdm

    software = software.upper()
    if software in ['+', 'FDTD', 'LUMERICAL']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    # 确保近场坐标也是数组
    x_near, y_near = np.atleast_1d(x_near), np.atleast_1d(y_near)

    # 远场转换为 ndarray
    x_far, y_far, z_far = np.atleast_1d(x_far), np.atleast_1d(y_far), np.atleast_1d(z_far)


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
        lamb: 波长
        x_near, y_near: 近场平面网格坐标 (一维数组)
        E_near_x, E_near_y: 近场电场横向分量 (二维数组)
        x_far, y_far, z_far: 远场坐标 (允许为单个数字或一维数组)
        mode: ('fft' 或 'numba')
        mode: 计算模式
            'fft'('f')    : 快速傅里叶变换，计算速度极快，占用计算资源很小，严格要求 x_far, y_far 与近场网格完全一致。
            'numba'('n')  : 逆傅里叶积分。允许计算任意形状远场，不受限制，占用计算资源较大。
        software: 'FDTD' (默认) 或 'COMSOL'software: 波传播相位约定/来源软件类型
            '+', 'FDTD' 或 'Lumerical' : 采用 exp(+ikz) 相位约定 (默认)
            '-', 'COMSOL' 或 'CST'     : 采用 exp(-ikz) 相位约定

    返回:
        E_total: 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))
        E_far_x, E_far_y, E_far_z: 远场电场各个分量数据，形状为 (len(x_far), len(y_far), len(z_far))
    '''
    from tqdm.auto import tqdm

    software = software.upper()
    if software in ['+', 'FDTD', 'LUMERICAL']:
        sg = 1.0
    elif software in ['-', 'COMSOL', 'CST']:
        sg = -1.0
    else:
        raise ValueError("software 参数必须是'+', '-', 'FDTD', 'LUMERICAL', 'COMSOL', 或 'CST'")

    x_near, y_near = np.atleast_1d(x_near), np.atleast_1d(y_near)
    x_far, y_far, z_far = np.atleast_1d(x_far), np.atleast_1d(y_far), np.atleast_1d(z_far)

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
    Ax = np.fft.fftshift(np.fft.fft2(E_near_x)) * (dx * dy)
    Ay = np.fft.fftshift(np.fft.fft2(E_near_y)) * (dx * dy)
    
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
    fz = fz_real + 1j * fz_imag
    fz_safe = np.where(np.abs(fz) < 1e-12, 1e-12, fz)
    
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
            E_far_x[:, :, i] = np.fft.ifft2(np.fft.ifftshift(Ax * H)) / (dx * dy)
            E_far_y[:, :, i] = np.fft.ifft2(np.fft.ifftshift(Ay * H)) / (dx * dy)
            E_far_z[:, :, i] = np.fft.ifft2(np.fft.ifftshift(Az * H)) / (dx * dy)
            
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
    """Lumerical 功能基类，处理通用的 API 转发和参数预处理"""
    def __init__(self, target_handle):
        # 隐藏内部句柄，避免与转发逻辑冲突
        self._handle = target_handle

    def _process_arg(self, arg):
        """
        核心预处理逻辑：
        1. 整型 ndarray -> 浮点型
        2. 一维 ndarray (len > 1) -> 二维 [[...]]
        """
        if isinstance(arg, np.ndarray):
            # 规则 1: 检查是否为整型数组并转换
            if np.issubdtype(arg.dtype, np.integer):
                arg = arg.astype(float)
            
            # 规则 2: 检查一维数组且长度不为 1，进行升维
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
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        handle = lumapi.FDTD(filename, key, hide, serverArgs, remoteArgs, **kwargs)
        super().__init__(handle)
        self.filename = filename

class MODE(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        handle = lumapi.MODE(filename, key, hide, serverArgs, remoteArgs, **kwargs)
        super().__init__(handle)
        self.filename = filename

class DEVICE(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        handle = lumapi.DEVICE(filename, key, hide, serverArgs, remoteArgs, **kwargs)
        super().__init__(handle)
        self.filename = filename

class INTERCONNECT(LumFuncBase):
    def __init__(self, lumapi, filename=None, key=None, hide=False, serverArgs={}, remoteArgs={}, **kwargs):
        handle = lumapi.INTERCONNECT(filename, key, hide, serverArgs, remoteArgs, **kwargs)
        super().__init__(handle)
        self.filename = filename
    
lumapi = lumerical()

if __name__ == '__main__':
    um = 1e-6
    nx, ny = 100, 100
    S = 0.5*um
    material_base = 'Au (Gold) - CRC'

    lumapi = lumapi()
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















