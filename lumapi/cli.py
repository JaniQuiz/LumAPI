import json
import os
import importlib.util
import re
import platform
import sys

# --- 路径处理逻辑 ---
# 对于安装版，cli.py 位于 lumapi 包内部
LUMAPI_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(LUMAPI_DIR, "config.json")
INIT_PATH = os.path.join(LUMAPI_DIR, "__init__.py")

# 确保 __init__.py 存在
if not os.path.exists(INIT_PATH):
    try:
        with open(INIT_PATH, 'w') as f: f.write("from lumapi.lumapi import *\n")
    except: pass
# ---------------------------

def get_lumapi_path(lumerical_root, version):
    base_path = os.path.join(lumerical_root, version)
    ansys_path = os.path.join(base_path, "Lumerical", "api", "python", "lumapi.py")
    if os.path.exists(ansys_path): return ansys_path
    standalone_path = os.path.join(base_path, "api", "python", "lumapi.py")
    if os.path.exists(standalone_path): return standalone_path
    return standalone_path

def detect_version(lumerical_root):
    try:
        if not os.path.exists(lumerical_root): return None
        for item in os.listdir(lumerical_root):
            item_path = os.path.join(lumerical_root, item)
            if os.path.isdir(item_path) and re.match(r'^v\d{3}$', item):
                if os.path.exists(get_lumapi_path(lumerical_root, item)):
                    return item
        return None
    except: return None

def detect_common_paths():
    print("正在扫描 Lumerical 路径...", end="", flush=True)
    common_paths = []
    if platform.system() == "Windows":
        import string
        from ctypes import windll
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1: drives.append(letter + ":\\")
            bitmask >>= 1
        for drive in drives:
            paths = [
                os.path.join(drive, "Program Files", "Lumerical"),
                os.path.join(drive, "Program Files (x86)", "Lumerical"),
                os.path.join(drive, "Lumerical"),
                os.path.join(drive, "Program Files", "Ansys Inc"),
                os.path.join(drive, "Program Files (x86)", "Ansys Inc")
            ]
            for p in paths:
                if os.path.exists(p):
                    v = detect_version(p)
                    if v: common_paths.append((p, v))
    elif platform.system() == "Linux":
        paths = [
            "/opt/lumerical", "/usr/local/lumerical",
            "/usr/ansys_inc", "/opt/ansys_inc",
            os.path.expanduser("~/Ansys/ansys_inc"), os.path.expanduser("~/ansys_inc")
        ]
        for p in paths:
            if os.path.exists(p):
                v = detect_version(p)
                if v: common_paths.append((p, v))
    print(" 完成。")
    return common_paths

def validate_path(lumerical_root):
    try:
        if not lumerical_root: return "", ""
        lumerical_root = os.path.abspath(lumerical_root)
        version = detect_version(lumerical_root)
        if not version:
            print(f"错误：未找到有效版本 (在 {lumerical_root})")
            return "", ""
        lumapi_path = get_lumapi_path(lumerical_root, version)
        if not os.path.exists(lumapi_path): return "", ""
        
        spec = importlib.util.spec_from_file_location('lumapi', lumapi_path)
        lumapi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lumapi)
        
        if platform.system() == "Windows":
            os.add_dll_directory(lumerical_root)
            bin_path = os.path.join(lumerical_root, version, "bin")
            if not os.path.exists(bin_path):
                bin_path = os.path.join(lumerical_root, version, "Lumerical", "bin")
            if os.path.exists(bin_path):
                os.add_dll_directory(bin_path)
        return lumapi_path, version
    except Exception as e:
        print(f"验证失败: {e}")
        return "", ""

def save_config(lumerical_path, version):
    try:
        dir_name = os.path.dirname(CONFIG_PATH)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        with open(CONFIG_PATH, 'w') as f:
            json.dump({'lumerical_path': os.path.abspath(lumerical_path), 'version': version}, f, indent=4)
        print(f"[成功] 配置已保存到 {CONFIG_PATH}。")
        return True
    except Exception as e:
        print(f"[错误] 保存失败: {e}")
        print("提示：如果安装在系统目录，可能需要管理员权限运行。")
        return False

# ================= 主流程 =================

def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get('lumerical_path'), config.get('version')
    except: pass
    return None, None

def load_lumapi(lumerical_path, version):
    # 直接使用 validate_path 里的逻辑来测试
    # 或者尝试从 lumapi 包导入
    try:
        print(f"正在尝试加载 Lumerical API ({version})...")
        path, ver = validate_path(lumerical_path)
        if path:
            print(f"\n[成功] 成功验证并加载 API: {path}")
        else:
            print(f"\n[失败] 无法加载 API")
    except Exception as e:
        print(f"\n[错误] {e}")

def perform_configuration():
    detected = detect_common_paths()
    if detected:
        print("\n检测到以下路径:")
        for i, (p, v) in enumerate(detected):
            print(f"{i+1}. {p} ({v})")
        print(f"{len(detected)+1}. 手动输入")
        try:
            sel_str = input("选择: ").strip()
            if not sel_str: return
            sel = int(sel_str)
            if 1 <= sel <= len(detected):
                path, ver = detected[sel-1]
                if validate_path(path)[0]:
                    save_config(path, ver)
                return
        except ValueError: pass

    path = input("\n请输入安装根目录: ").strip()
    if not path: return
    p_valid, v_valid = validate_path(path)
    if p_valid: save_config(path, v_valid)

def main():
    print("=== Lumerical Python API 配置工具 (PyPI版) ===")
    
    while True:
        cfg_path, cfg_ver = load_config()
        has_config = (cfg_path is not None)
        
        print("\n-------------------------")
        if has_config:
            print(f"当前配置: {cfg_path} ({cfg_ver})")
            print("1. [测试] 测试加载环境")
            print("2. [配置] 重新配置路径")
            print("3. [退出] 退出")
        else:
            print("当前状态: 未配置")
            print("1. [配置] 开始配置新路径")
            print("2. [退出] 退出")
            
        choice = input("\n选项: ").strip()
        
        if has_config:
            if choice == '1': load_lumapi(cfg_path, cfg_ver)
            elif choice == '2': perform_configuration()
            elif choice == '3': sys.exit()
        else:
            if choice == '1': perform_configuration()
            elif choice == '2': sys.exit()

if __name__ == "__main__":
    main()
