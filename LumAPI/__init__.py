# LumAPI/__init__.py

# 显式导入所有需要对外暴露的类和函数
from .lumapi import (
    lumapi, lumerical, LumFuncBase,
    FDTD, MODE, DEVICE, INTERCONNECT,
    savemat, loadmat, save_h5, load_h5, 
    create_cmap, set_colorbar_range,
    Estimate_focal, Kirchhoff, 
    RayleighSommerfeld_Scalar, RayleighSommerfeld_Vector, AngularSpectrum_Vector
)

# 定义 import * 时对外暴露的接口白名单（这是静态检查器识别 import * 的关键）
__all__ = [
    'lumapi', 'lumerical', 'LumFuncBase',
    'FDTD', 'MODE', 'DEVICE', 'INTERCONNECT',
    'savemat', 'loadmat', 'save_h5', 'load_h5',
    'create_cmap', 'set_colorbar_range',
    'Estimate_focal', 'Kirchhoff', 
    'RayleighSommerfeld_Scalar', 'RayleighSommerfeld_Vector', 'AngularSpectrum_Vector'
]