import keyword
import os
# 从你的 LumAPI 包中导入实例化对象
from LumAPI import lumapi

def generate_ultimate_stubs():
    products = ['FDTD', 'MODE', 'DEVICE', 'INTERCONNECT']
    product_commands = {}
    
    # 官方 Python API 层面自带的基类公共方法
    python_base_methods = {
        'close', 'eval', 'getv', 'putv', 
        'getObjectById', 'getObjectBySelection', 'getAllSelectedObjects'
    }

    # Lumerical 特有的控制流保留字，也需要屏蔽
    lumerical_excludes = {'catch', 'end', 'true', 'false', 'isnull', 'exit'}

    print("正在启动并连接 Lumerical 核心提取纯净 API...")
    
    for prod in products:
        try:
            print(f"尝试启动 {prod} 核心进程...")
            # 动态调用 lumapi.FDTD(), lumapi.MODE() 等
            constructor = getattr(lumapi, prod)
            handle = constructor(hide=True)
            
            handle.eval("api_list_temp = getcommands;")
            raw_cmds = handle.getv("api_list_temp")
            
            cmds = set()
            for cmd in raw_cmds.split("\n"):
                cmd = cmd.strip()
                # 核心过滤机制：必须是合法标识符，且不是Python关键字，且不是Lumerical控制字
                if cmd.isidentifier() and not keyword.iskeyword(cmd) and cmd not in lumerical_excludes:
                    cmds.add(cmd)
                    
            product_commands[prod] = cmds
            handle.close()
            print(f" -> {prod} 提取成功，包含 {len(cmds)} 个有效指令。")
        except Exception as e:
            print(f" -> 无法启动 {prod} (可能是缺少许可证或未安装)，将跳过。原因: {e}")
            
    if not product_commands:
        print("所有模块均无法启动，提取失败！请检查 Lumerical 环境。")
        return

    # 计算共同方法 (交集)
    shared_cmds = set.intersection(*product_commands.values())
    base_methods = shared_cmds.union(python_base_methods)
    print(f"\n分类完成！找到 {len(base_methods)} 个共有基础方法。")

    # ================= 构建 .pyi 文件内容 =================
    # 1. 导入模块和自定义函数的类型提示
    stub_content = """from typing import Any, Tuple, Dict, List, Union, Optional
import numpy as np

# ================= mat保存读取函数 =================
def savemat(filename: str, data_dict: Dict[str, Any], version: str = 'v7.3', auto_transpose: bool = True) -> bool: ...
def loadmat(filename: str, auto_transpose: bool = True, squeeze_me: bool = True) -> Dict[str, Any]: ...

# ==================== 绘图函数 ====================
def create_cmap(color_list: list, cmap_name: str = "custom_cmap") -> Any: ...
def set_colorbar_range(mappable: Any, vmin: float, vmax: float) -> None: ...

# ================== 衍射积分函数 ==================
def Estimate_focal(lamb: float, r: float, focal_theory: float) -> Tuple[float, float]: ...

def Kirchhoff(lamb: float, x_near: Any, y_near: Any, E_near: Any, x_far: Any, y_far: Any, z_far: Any, mode: str = 'numba', software: str = '+') -> Any: ...
def RayleighSommerfeld_Scalar(lamb: float, x_near: Any, y_near: Any, E_near: Any, x_far: Any, y_far: Any, z_far: Any, mode: str = 'numba', software: str = '+') -> Any: ...
def RayleighSommerfeld_Vector(lamb: float, x_near: Any, y_near: Any, E_near_x: Any, E_near_y: Any, x_far: Any, y_far: Any, z_far: Any, mode: str = 'numba', software: str = '+') -> Tuple[Any, Any, Any, Any]: ...
def AngularSpectrum_Vector(lamb: float, x_near: Any, y_near: Any, E_near_x: Any, E_near_y: Any, x_far: Any, y_far: Any, z_far: Any, mode: str = 'numba', software: str = '+') -> Tuple[Any, Any, Any, Any]: ...
# =================================================

class LumFuncBase:
"""
    
    # 2. 写入基类公共方法
    if base_methods:
        for m in sorted(base_methods):
            stub_content += f"    def {m}(self, *args, **kwargs) -> Any: ...\n"
    else:
        stub_content += "    pass\n"
    stub_content += "\n"

    # 3. 写入各个专属子类方法
    for prod in products:
        stub_content += f"class {prod}(LumFuncBase):\n"
        if prod in product_commands:
            specific_methods = product_commands[prod] - base_methods
            if specific_methods:
                for m in sorted(specific_methods):
                    stub_content += f"    def {m}(self, *args, **kwargs) -> Any: ...\n"
            else:
                stub_content += "    pass\n"
        else:
            stub_content += "    pass\n"
        stub_content += "\n"

    # 4. 写入主类和实例映射
    stub_content += """class lumerical:
    def FDTD(self, filename: Optional[str] = None, key: Optional[str] = None, hide: bool = False, serverArgs: Dict = {}, remoteArgs: Dict = {}, **kwargs) -> FDTD: ...
    def MODE(self, filename: Optional[str] = None, key: Optional[str] = None, hide: bool = False, serverArgs: Dict = {}, remoteArgs: Dict = {}, **kwargs) -> MODE: ...
    def DEVICE(self, filename: Optional[str] = None, key: Optional[str] = None, hide: bool = False, serverArgs: Dict = {}, remoteArgs: Dict = {}, **kwargs) -> DEVICE: ...
    def INTERCONNECT(self, filename: Optional[str] = None, key: Optional[str] = None, hide: bool = False, serverArgs: Dict = {}, remoteArgs: Dict = {}, **kwargs) -> INTERCONNECT: ...

lumapi: lumerical
"""

    # 5. 保存到 LumAPI 文件夹内
    pyi_path = os.path.join("LumAPI", "lumapi.pyi")
    with open(pyi_path, 'w', encoding='utf-8') as f:
        f.write(stub_content)

    print(f"完美！已将最终版存根文件生成至: {pyi_path}")

if __name__ == "__main__":
    generate_ultimate_stubs()