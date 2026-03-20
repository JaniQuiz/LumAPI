import numpy as np
import matplotlib.pyplot as plt
import os
from LumAPI import RayleighSommerfeld_Vector

def plot_diff(diff_data, title, xlabel, ylabel, extent, filename, is_xy=True, vmax=1e-10):
    """通用的差值绘制与保存函数"""
    plt.figure(figsize=(5, 4) if is_xy else (10, 2.5))
    
    im = plt.imshow(diff_data.T if is_xy else diff_data, 
                    extent=extent, cmap='viridis', origin='lower', aspect='auto',
                    vmin=0, vmax=vmax)
    
    max_err = np.max(diff_data)
    plt.title(f"{title}\nMax Diff: {max_err:.2e}")
    plt.xlabel(xlabel); plt.ylabel(ylabel)
    plt.colorbar(im)
    plt.tight_layout()
    plt.savefig(filename, dpi=150 if is_xy else 200)
    plt.close()

def run_rs_vector_validation():
    os.makedirs('pics', exist_ok=True)
    
    # === 物理参数设置 ===
    lamb = 1.55e-6         
    k = 2 * np.pi / lamb
    D = 60e-6              
    dx = 0.5e-6            
    f_design = 50e-6       
    
    x_n = np.arange(-D/2, D/2, dx)
    y_n = np.arange(-D/2, D/2, dx)
    X_n, Y_n = np.meshgrid(x_n, y_n, indexing='xy')
    aperture = (X_n**2 + Y_n**2) <= (D/2)**2
    
    tests = [
        ('+', 'numba'), ('+', 'vectorized'), ('+', 'threaded'), ('+', 'common'),
        ('-', 'numba')
    ]
    
    # 统一的高分辨率坐标轴设置（无降采样）
    z_scan = np.linspace(1e-6, 100e-6, 200) 
    x_f_scan = np.linspace(-10e-6, 10e-6, 100)
    x_xz_scan = np.linspace(-30e-6, 30e-6, 150)
    
    # 用于缓存各模式结果的字典
    field_results = {}
    
    # === 第一阶段：计算并绘制各模式光强场 ===
    for software, mode in tests:
        print(f"\n========== 开始计算并生成图片: 约定={software}, 模式={mode} ==========")
        fn_sg = 'plus' if software == '+' else 'minus'
        
        # 相位翻转
        sg = 1.0 if software == '+' else -1.0
        phase = -sg * k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
        
        # 矢量近场初始化：这里采用 X线偏振 光入射
        E_near_x = aperture * np.exp(1j * phase)
        E_near_y = np.zeros_like(E_near_x)
        
        # 1. Z 轴扫描 (找到真实焦平面 actual_f)
        E_tot_z, _, _, _ = RayleighSommerfeld_Vector(lamb, x_n, y_n, E_near_x, E_near_y, 0.0, 0.0, z_scan, mode=mode, software=software)
        # E_total 返回的是场强的模（sqrt(|Ex|^2 + |Ey|^2 + |Ez|^2)），光强直接用平方即可
        I_z_axis = E_tot_z[0, 0, :]**2
        actual_f = z_scan[np.argmax(I_z_axis)]
        
        plt.figure(figsize=(5, 4))
        plt.plot(z_scan*1e6, I_z_axis, 'b-', linewidth=2)
        plt.axvline(f_design*1e6, color='r', linestyle='--', label=f'Design ({f_design*1e6} μm)')
        plt.axvline(actual_f*1e6, color='g', linestyle=':', label=f'Actual ({actual_f*1e6:.1f} μm)')
        plt.title(f"Z-axis Vector Intensity ({software} | {mode})")
        plt.xlabel("Z (μm)"); plt.ylabel("Intensity")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f'pics/RS_vector_{fn_sg}_{mode}_Z.jpg', dpi=150)
        plt.close()
        
        # 2. XY 焦平面扫描
        E_tot_xy, _, _, _ = RayleighSommerfeld_Vector(lamb, x_n, y_n, E_near_x, E_near_y, x_f_scan, x_f_scan, actual_f, mode=mode, software=software)
        I_xy_plane = E_tot_xy[:, :, 0]**2
        
        plt.figure(figsize=(5, 4))
        im = plt.imshow(I_xy_plane.T, extent=[-10, 10, -10, 10], cmap='hot', origin='lower')
        plt.title(f"Focal Plane XY ({software} | {mode})")
        plt.xlabel("X (μm)"); plt.ylabel("Y (μm)")
        plt.colorbar(im)
        plt.tight_layout()
        plt.savefig(f'pics/RS_vector_{fn_sg}_{mode}_XY.jpg', dpi=150)
        plt.close()

        # 3. XZ 全景扫描 (10x2.5 横向沙漏图)
        E_tot_xz, _, _, _ = RayleighSommerfeld_Vector(lamb, x_n, y_n, E_near_x, E_near_y, x_xz_scan, 0.0, z_scan, mode=mode, software=software)
        I_xz_plane = E_tot_xz[:, 0, :]**2
        
        plt.figure(figsize=(10, 2.5))
        im = plt.imshow(I_xz_plane, extent=[z_scan[0]*1e6, z_scan[-1]*1e6, x_xz_scan[0]*1e6, x_xz_scan[-1]*1e6], cmap='jet', aspect='auto', origin='lower')
        plt.axvline(f_design*1e6, color='w', linestyle='--', alpha=0.5)
        plt.title(f"XZ Propagation Plane ({software} | {mode})")
        plt.xlabel("Z (μm)"); plt.ylabel("X (μm)")
        plt.colorbar(im)
        plt.tight_layout()
        plt.savefig(f'pics/RS_vector_{fn_sg}_{mode}_XZ.jpg', dpi=200)
        plt.close()

        # 缓存结果用于后续差值比对
        field_results[(software, mode)] = {
            'I_xy': I_xy_plane,
            'I_xz': I_xz_plane
        }

    # === 第二阶段：生成一致性验证的差值比对图 ===
    print("\n========== 开始计算并生成误差对比图 ==========")
    
    # 以正约定下的 common 模式作为基准
    base_xy = field_results[('+', 'common')]['I_xy']
    base_xz = field_results[('+', 'common')]['I_xz']
    
    xy_extent = [-10, 10, -10, 10]
    xz_extent = [z_scan[0]*1e6, z_scan[-1]*1e6, x_xz_scan[0]*1e6, x_xz_scan[-1]*1e6]

    # 固定统一的绘图上限
    diff_vmax = 1e-10

    # 1. 对比不同计算模式 (Numba, Vectorized, Threaded) 与基准 Common 的差值
    for mode in ['numba', 'vectorized', 'threaded']:
        diff_xy = np.abs(field_results[('+', mode)]['I_xy'] - base_xy)
        diff_xz = np.abs(field_results[('+', mode)]['I_xz'] - base_xz)
        
        # 计算并打印最大值和平均值，方便复制进 md 文档
        max_xy, mean_xy = np.max(diff_xy), np.mean(diff_xy)
        max_xz, mean_xz = np.max(diff_xz), np.mean(diff_xz)
        
        print(f"\n[{mode.capitalize()} - Common] 误差统计:")
        print(f"  -> XY 平面: 最大差值 = {max_xy:.4e}, 平均差值 = {mean_xy:.4e}")
        print(f"  -> XZ 平面: 最大差值 = {max_xz:.4e}, 平均差值 = {mean_xz:.4e}")
        
        plot_diff(diff_xy, f"Diff: {mode.capitalize()} - Common (XY)", 
                  "X (μm)", "Y (μm)", xy_extent, f'pics/RS_vector_diff_{mode}_c_XY.jpg', 
                  is_xy=True, vmax=diff_vmax)
                  
        plot_diff(diff_xz, f"Diff: {mode.capitalize()} - Common (XZ)", 
                  "Z (μm)", "X (μm)", xz_extent, f'pics/RS_vector_diff_{mode}_c_XZ.jpg', 
                  is_xy=False, vmax=diff_vmax)

    # 2. 对比不同相位约定 (Minus vs Plus，同在 Numba 模式下比较)
    diff_xy_conv = np.abs(field_results[('-', 'numba')]['I_xy'] - field_results[('+', 'numba')]['I_xy'])
    diff_xz_conv = np.abs(field_results[('-', 'numba')]['I_xz'] - field_results[('+', 'numba')]['I_xz'])
    
    # 打印不同约定的误差统计
    print(f"\n[Minus - Plus 相位约定] 误差统计:")
    print(f"  -> XY 平面: 最大差值 = {np.max(diff_xy_conv):.4e}, 平均差值 = {np.mean(diff_xy_conv):.4e}")
    print(f"  -> XZ 平面: 最大差值 = {np.max(diff_xz_conv):.4e}, 平均差值 = {np.mean(diff_xz_conv):.4e}")

    plot_diff(diff_xy_conv, "Diff: Minus - Plus Phase Conv (XY)", 
              "X (μm)", "Y (μm)", xy_extent, 'pics/RS_vector_diff_minus_plus_XY.jpg', 
              is_xy=True, vmax=diff_vmax)
              
    plot_diff(diff_xz_conv, "Diff: Minus - Plus Phase Conv (XZ)", 
              "Z (μm)", "X (μm)", xz_extent, 'pics/RS_vector_diff_minus_plus_XZ.jpg', 
              is_xy=False, vmax=diff_vmax)
    
def run_vector_feature_analysis():
    """
    单独运行的矢量衍射特性分析函数，用于展示高 NA 聚焦下的 Ex, Ey, Ez 分量
    """
    print("\n========== 开始矢量衍射特性分析 (偏振耦合展示) ==========")
    os.makedirs('pics', exist_ok=True)
    
    # === 物理参数设置 ===
    lamb = 1.55e-6         
    k = 2 * np.pi / lamb
    D = 60e-6              
    dx = 0.5e-6            
    f_design = 50e-6       
    
    x_n = np.arange(-D/2, D/2, dx)
    y_n = np.arange(-D/2, D/2, dx)
    X_n, Y_n = np.meshgrid(x_n, y_n, indexing='xy')
    aperture = (X_n**2 + Y_n**2) <= (D/2)**2
    
    # 采用正向约定，计算近场相控阵 (X 线偏振)
    phase = -k * np.sqrt(X_n**2 + Y_n**2 + f_design**2)
    E_near_x = aperture * np.exp(1j * phase)
    E_near_y = np.zeros_like(E_near_x)
    
    # 1. 快速使用 Numba 模式扫描一次 Z 轴找到准确焦距
    z_scan_fast = np.linspace(40e-6, 60e-6, 100)
    E_tot_z, _, _, _ = RayleighSommerfeld_Vector(lamb, x_n, y_n, E_near_x, E_near_y, 0.0, 0.0, z_scan_fast, mode='n', software='+')
    actual_f = z_scan_fast[np.argmax(E_tot_z[0, 0, :]**2)]
    print(f"检测到实际焦距: {actual_f*1e6:.2f} μm")

    # 2. 在焦平面上进行局部高分辨率扫描 (放大查看光斑细节)
    # 缩小范围到 ±4 μm 以便清晰看清波瓣形状
    x_f_zoom = np.linspace(-4e-6, 4e-6, 120)
    
    # 提取四个返回值
    E_tot, Ex, Ey, Ez = RayleighSommerfeld_Vector(
        lamb, x_n, y_n, E_near_x, E_near_y, 
        x_f_zoom, x_f_zoom, actual_f, 
        mode='n', software='+'
    )
    
    # 计算各分量光强
    Ix = np.abs(Ex[:, :, 0])**2
    Iy = np.abs(Ey[:, :, 0])**2
    Iz = np.abs(Ez[:, :, 0])**2
    Itot = E_tot[:, :, 0]**2

    # --- 定义绘图辅组函数 ---
    def plot_component(data, title, filename, cmap='hot'):
        plt.figure(figsize=(5, 4))
        # 注意转置以匹配 XY 物理坐标系
        im = plt.imshow(data.T, extent=[-4, 4, -4, 4], cmap=cmap, origin='lower')
        plt.title(f"{title}\nMax: {np.max(data):.2e}")
        plt.xlabel("X (μm)"); plt.ylabel("Y (μm)")
        plt.colorbar(im)
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close()

    # 3. 独立绘制各个分量
    plot_component(Ix, "$|E_x|^2$ (Main Component)", 'pics/RS_vector_feature_Ex.jpg')
    # Ey 分量非常弱，四叶草形状
    plot_component(Iy, "$|E_y|^2$ (Cross Polarization)", 'pics/RS_vector_feature_Ey.jpg', cmap='magma')
    # Ez 分量呈现双叶片形状
    plot_component(Iz, "$|E_z|^2$ (Longitudinal)", 'pics/RS_vector_feature_Ez.jpg', cmap='plasma')
    # 总光强
    plot_component(Itot, "$|E_{total}|^2$ (Total Intensity)", 'pics/RS_vector_feature_Total.jpg')
    
    print("矢量分量特征图已生成！请查看 pics/ 文件夹。")

if __name__ == "__main__":
    run_rs_vector_validation()
    run_vector_feature_analysis()
    print("\n所有 RS_vector 验证图片与差值分析图已生成完毕！")