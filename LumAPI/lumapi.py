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

def Kirchhoff(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba'):
    '''
    lamb: 波长
    x_near, y_near: 近场位置数据，x_near和y_near应当是一维ndarry数组
    E_near: 近场的电场数据，E_near应当是二维ndarry数组
    x_far, y_far, z_far: 远场的位置数据，应当是一维数据或者数值
    mode: 计算模式
        'common'('c')，   : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢
        'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，测试仅windows下可用，需要joblib库
        'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存(目前还没写好)
        'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**

    return: 远场电场数据np.ndarray(len(x_far),len(y_far),len(z_far))
    '''
    from tqdm.auto import tqdm
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
        print('Using normal mode...')
        for ii in tqdm(range(len(y_near)), desc="Common Integration"):
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps) # 防止 r=0
                # 乘上了积分面元 ds
                E_far += (1/(2j*lamb) * E_near[ii,jj]/r * np.exp(1j*k*r) * (1 + Z_far/r)) * ds

    elif mode in ['threaded', 't']:
        print('Using joblib threaded mode...')
        from joblib import Parallel, delayed
        def compute_row(ii):
            row_result = np.zeros_like(X_far, dtype=np.complex128)
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                row_result += (1/(2j*lamb) * E_near[ii,jj]/r * np.exp(1j*k*r) * (1 + Z_far/r)) * ds
            return row_result
        
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) for ii in tqdm(range(len(y_near)), desc="Threaded Integration")
        )
        for row_result in results:
            E_far += row_result

    elif mode in ['vectorized', 'v']:
        print('Using vectorized mode... (Warning: High Memory Usage for large arrays)')
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
        integrand = (1/(2j*lamb)) * (E_n / r) * np.exp(1j*k*r) * (1 + Z_f/r)
        
        # 沿着近场的 Y轴(axis=3) 和 X轴(axis=4) 积分求和
        E_far = np.sum(integrand, axis=(3, 4)) * ds

    elif mode in ['numba', 'n']:
        print('Using numba hybrid mode...')
        import numba as nb
        
        # 展平远场网格，以便在外层套用 tqdm 进度条
        shape_orig = X_far.shape
        X_flat = X_far.ravel()
        Y_flat = Y_far.ravel()
        Z_flat = Z_far.ravel()
        E_flat = np.zeros_like(X_flat, dtype=np.complex128)
        
        # 内部 Numba 函数：计算单个远场观察点接收到的所有近场积分 (启用多线程加速)
        @nb.njit(parallel=True, fastmath=True)
        def compute_single_far_point(xf, yf, zf, x_n, y_n, E_n, lamb, k, ds):
            val = 0j
            y_len, x_len = len(y_n), len(x_n)
            # prange 支持对标量 val 的自动线程归约 (Reduction)
            for ii in nb.prange(y_len):
                for jj in range(x_len):
                    r = np.sqrt((xf - x_n[jj])**2 + (yf - y_n[ii])**2 + zf**2)
                    if r < 1e-12: r = 1e-12
                    val += (1/(2j*lamb) * E_n[ii,jj]/r * np.exp(1j*k*r) * (1 + zf/r)) * ds
            return val
            
        # 外层 Python 循环挂载 tqdm
        for i in tqdm(range(len(X_flat)), desc="Numba Integration"):
            E_flat[i] = compute_single_far_point(
                X_flat[i], Y_flat[i], Z_flat[i], 
                x_near, y_near, E_near, lamb, k, ds
            )
            
        # 还原回 3D 矩阵形状
        E_far = E_flat.reshape(shape_orig)

    else:
        raise ValueError('Invalid mode(请检查输入的mode参数)')
        
    return E_far

def RorySommerfeld_Scalar(lamb, x_near, y_near, E_near, x_far, y_far, z_far, mode='numba'):
    '''
    瑞利-索末菲(Rayleigh-Sommerfeld) 标量衍射积分公式
    
    参数:
        lamb: 波长
        x_near, y_near: 近场位置数据 (允许输入单个数字或一维数组)
        E_near: 近场的电场数据 (二维数组)
        x_far, y_far, z_far: 远场的位置数据 (允许输入单个数字或一维数组)
        mode: 计算模式 ('common', 'threaded', 'vectorized', 'numba')
        
    返回:
        E_far: 远场电场数据，形状为 (len(x_far), len(y_far), len(z_far))
    '''
    from tqdm.auto import tqdm
    
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

    # --- 3. 计算模块 ---
    if mode in ['common', 'c']:
        print('Using common mode...')
        for ii in tqdm(range(len(y_near)), desc="Common Integration"):
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                # 瑞利索末菲公式: 1/(1j*lamb) 且倾斜因子为 Z_far/r
                E_far += (1/(1j*lamb) * E_near[ii,jj]/r * np.exp(1j*k*r) * (Z_far/r)) * ds

    elif mode in ['threaded', 't']:
        print('Using joblib threaded mode...')
        from joblib import Parallel, delayed
        def compute_row(ii):
            row_result = np.zeros_like(X_far, dtype=np.complex128)
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + (Y_far - y_near[ii])**2 + Z_far**2)
                r = np.maximum(r, eps)
                row_result += (1/(1j*lamb) * E_near[ii,jj]/r * np.exp(1j*k*r) * (Z_far/r)) * ds
            return row_result
        
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) for ii in tqdm(range(len(y_near)), desc="Threaded Integration")
        )
        for row_result in results:
            E_far += row_result

    elif mode in ['vectorized', 'v']:
        print('Using vectorized mode... (Warning: Very High Memory Usage for large grids)')
        # 利用 5D 广播：远场占前三个维度，近场占后两个维度
        X_f = X_far[..., np.newaxis, np.newaxis]
        Y_f = Y_far[..., np.newaxis, np.newaxis]
        Z_f = Z_far[..., np.newaxis, np.newaxis]
        
        X_n = x_near.reshape(1, 1, 1, 1, -1)
        Y_n = y_near.reshape(1, 1, 1, -1, 1)
        E_n = E_near.reshape(1, 1, 1, len(y_near), len(x_near))
        
        r = np.sqrt((X_f - X_n)**2 + (Y_f - Y_n)**2 + Z_f**2)
        r = np.maximum(r, eps)
        
        integrand = (1/(1j*lamb)) * (E_n / r) * np.exp(1j*k*r) * (Z_f/r)
        
        # 对近场的 Y轴(axis=3) 和 X轴(axis=4) 积分求和
        E_far = np.sum(integrand, axis=(3, 4)) * ds

    elif mode in ['numba', 'n']:
        print('Using numba hybrid mode...')
        import numba as nb
        
        # 展平远场网格，以便在外层套用 tqdm 进度条
        shape_orig = X_far.shape
        X_flat = X_far.ravel()
        Y_flat = Y_far.ravel()
        Z_flat = Z_far.ravel()
        E_flat = np.zeros_like(X_flat, dtype=np.complex128)
        
        # 内部 Numba 函数：计算单个远场观察点接收到的所有近场积分 (启用多线程加速)
        @nb.njit(parallel=True, fastmath=True)
        def compute_single_far_point(xf, yf, zf, x_n, y_n, E_n, lamb, k, ds):
            val = 0j
            y_len, x_len = len(y_n), len(x_n)
            # prange 支持对标量 val 的自动线程归约 (Reduction)
            for ii in nb.prange(y_len):
                for jj in range(x_len):
                    r = np.sqrt((xf - x_n[jj])**2 + (yf - y_n[ii])**2 + zf**2)
                    if r < 1e-12: r = 1e-12
                    val += (1/(1j*lamb) * E_n[ii,jj]/r * np.exp(1j*k*r) * (zf/r)) * ds
            return val
            
        # 外层 Python 循环挂载 tqdm
        for i in tqdm(range(len(X_flat)), desc="Numba Integration"):
            E_flat[i] = compute_single_far_point(
                X_flat[i], Y_flat[i], Z_flat[i], 
                x_near, y_near, E_near, lamb, k, ds
            )
            
        # 还原回 3D 矩阵形状
        E_far = E_flat.reshape(shape_orig)

    else:
        raise ValueError('Invalid mode (请检查输入的 mode 参数)')
        
    return E_far



def RorySommerfeld_Vector(lamb, x_near, y_near, E_near_x, E_near_y, x_far, y_far, z_far, mode='numba'):
    '''
    lamb: 波长
    x_near, y_near: 近场位置数据，x_near和y_near应当是一维ndarry数组
    E_near_x, E_near_y: 近场的电场数据的xy分量，E_near_x和E_near_y应当是二维ndarry数组
    x_far, y_far, z_far: 远场的位置数据，应当是一维数据或者数值
    mode: 计算模式
        'common'('c')，   : 普通循环计算模式，兼容所有平台，最稳定，但速度最慢
        'threaded'('t')   : 多线程计算模式，能够吃满CPU资源，测试仅windows下可用，需要joblib库
        'vectorized'('v') : 矢量化计算模式，计算小数据非常快，但大数据会容易爆内存(目前还没写好)
        'numba'('n')      : numba计算模式，计算速度非常快，兼容windows和linux，需要numba库，**推荐使用**

    return: 远场电场数据
    '''
    from tqdm import tqdm

    # 确保远场坐标为一维数组
    x_far = np.asarray(x_far)
    y_far = np.asarray(y_far)
    z_far = np.asarray(z_far)
    if x_far.ndim == 0: x_far = x_far[np.newaxis]
    if y_far.ndim == 0: y_far = y_far[np.newaxis]
    if z_far.ndim == 0: z_far = z_far[np.newaxis]

    k = 2 * np.pi / lamb
    # 生成远场网格（使用 'ij' 索引）
    X_far, Y_far, Z_far = np.meshgrid(x_far, y_far, z_far, indexing='ij')
    E_far_x = np.zeros_like(X_far, dtype=np.complex128)
    E_far_y = np.zeros_like(Y_far, dtype=np.complex128)
    E_far_z = np.zeros_like(Z_far, dtype=np.complex128)


    if mode == 'common' or mode == 'c':
        print('Using normal mode...')
        # 直接积分计算
        for ii in tqdm(range(len(y_near))):
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + 
                            (Y_far - y_near[ii])**2 + 
                            Z_far**2)
                exp_term = np.exp(1j*k*r)
                common_factor = (-1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                
                E_far_x += E_near_x[ii,jj] * exp_term * common_factor

                E_far_y += E_near_y[ii,jj] * exp_term * common_factor
                
                z_common_factor = (1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                E_far_z += ((E_near_x[ii,jj] + E_near_y[ii,jj]) * exp_term * z_common_factor)

    elif mode == 'vectorized' or mode == 'v':
        print('Using vectorized mode...')
        # 生成近场网格
        X_near, Y_near = np.meshgrid(x_near, y_near, indexing='ij')

        # 计算距离
        dx = X_far[np.newaxis, :, :, np.newaxis] - X_near[:, :, np.newaxis, np.newaxis]
        dy = Y_far[np.newaxis, :, :, np.newaxis] - Y_near[:, :, np.newaxis, np.newaxis]
        dz = Z_far[np.newaxis, np.newaxis, :, :]  # 形状为 (1,1,len(y_far),len(z_far))
        r = np.sqrt(dx**2 + dy**2 + dz**2)

        # 计算x分量
        factor_x = (-1/(2*np.pi) * E_near_x[:, :, np.newaxis, np.newaxis] * 
                    np.exp(1j*k*r) * dz / (r**2) * (1j*k - 1/r))
        
        # 计算y分量
        factor_y = (-1/(2*np.pi) * E_near_y[:, :, np.newaxis, np.newaxis] * 
                    np.exp(1j*k*r) * dz / (r**2) * (1j*k - 1/r))
        
        # 计算z分量
        factor_z = (1/(2*np.pi) * E_near_x[:, :, np.newaxis, np.newaxis] * 
                    np.exp(1j*k*r) * dz / (r**2) * (1j*k - 1/r)) + \
                (1/(2*np.pi) * E_near_y[:, :, np.newaxis, np.newaxis] * 
                    np.exp(1j*k*r) * dz / (r**2) * (1j*k - 1/r))
        
        # 累加所有近场点贡献
        E_far_x = np.sum(factor_x, axis=(0, 1))
        E_far_y = np.sum(factor_y, axis=(0, 1))
        E_far_z = np.sum(factor_z, axis=(0, 1))

    elif mode == 'threaded' or mode == 't':
        print('Using joblib threaded mode...')
        from joblib import Parallel, delayed
        
        # 使用joblib多线程实现
        def compute_row(ii):
            """计算单行的远场贡献"""
            row_x = np.zeros_like(X_far, dtype=np.complex128)
            row_y = np.zeros_like(Y_far, dtype=np.complex128)
            row_z = np.zeros_like(Z_far, dtype=np.complex128)
            
            for jj in range(len(x_near)):
                r = np.sqrt((X_far - x_near[jj])**2 + 
                            (Y_far - y_near[ii])**2 + 
                            Z_far**2)
                exp_term = np.exp(1j*k*r)
                common_factor = (-1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                
                # 计算x分量
                row_x += E_near_x[ii,jj] * exp_term * common_factor

                # 计算y分量
                row_y += E_near_y[ii,jj] * exp_term * common_factor

                # 计算z分量
                z_common_factor = (1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                row_z += (E_near_x[ii,jj] + E_near_y[ii,jj]) * exp_term * z_common_factor
            
            return row_x, row_y, row_z
        
        # 并行执行计算
        results = Parallel(n_jobs=-1)(
            delayed(compute_row)(ii) 
            for ii in tqdm(range(len(y_near)), desc="Processing rows")
        )
        
        # 合并结果
        for row_x, row_y, row_z in results:
            E_far_x += row_x
            E_far_y += row_y
            E_far_z += row_z

    elif mode == 'numba' or mode == 'n':
        print('Using numba mode...(numba mode has no progress bar)')
        import numba as nb
        
        # Numba 加速的积分内核
        @nb.njit(parallel=True, fastmath=True)
        def compute_row_parallel(y_len, x_len, x_near, y_near, E_near_x, E_near_y, 
                                X_far, Y_far, Z_far, k, E_far_x, E_far_y, E_far_z):
            for ii in nb.prange(y_len):  # prange 启用多线程
                for jj in range(x_len):
                    # 计算距离
                    r = np.sqrt((X_far - x_near[jj])**2 + 
                                (Y_far - y_near[ii])**2 + 
                                Z_far**2)
                    exp_term = np.exp(1j*k*r)
                    common_factor = (-1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                    
                    # 计算x分量
                    E_far_x += (E_near_x[ii,jj] * exp_term * common_factor)
                    
                    # 计算y分量
                    E_far_y += (E_near_y[ii,jj] * exp_term * common_factor)
                    
                    # 计算z分量
                    z_common_factor = (1/(2*np.pi) * Z_far / (r**2) * (1j*k - 1/r))
                    E_far_z += ((E_near_x[ii,jj] + E_near_y[ii,jj]) * exp_term * z_common_factor)
            return E_far_x, E_far_y, E_far_z
        
        # 调用 Numba 并行函数
        E_far_x, E_far_y, E_far_z = compute_row_parallel(
            len(y_near), len(x_near), x_near, y_near, 
            E_near_x, E_near_y, X_far, Y_far, Z_far, k, 
            E_far_x, E_far_y, E_far_z
        )
    # 计算总体电场强度（模值）
    E_far = np.sqrt(np.abs(E_far_x)**2 + np.abs(E_far_y)**2 + np.abs(E_far_z)**2)
    return E_far, E_far_x, E_far_y, E_far_z


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















