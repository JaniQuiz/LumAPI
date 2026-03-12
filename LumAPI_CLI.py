import json
import os
import importlib.util
import re
import platform
import sys
import shutil
import subprocess

# --- 路径处理逻辑 ---
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS 
    OUTPUT_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = BASE_DIR

LUMAPI_DIR = os.path.join(BASE_DIR, "lumapi")
CONFIG_PATH = os.path.join(LUMAPI_DIR, "config.json")
INIT_PATH = os.path.join(LUMAPI_DIR, "__init__.py")

if not getattr(sys, 'frozen', False) and not os.path.exists(LUMAPI_DIR):
    os.makedirs(LUMAPI_DIR, exist_ok=True)

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
        if not getattr(sys, 'frozen', False) and not os.path.exists(LUMAPI_DIR):
            os.makedirs(LUMAPI_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({'lumerical_path': os.path.abspath(lumerical_path), 'version': version}, f, indent=4)
        print(f"[成功] 配置已保存。")
        return True
    except Exception as e:
        print(f"[错误] 保存失败: {e}")
        return False

# ================= Python 环境相关函数 =================

def detect_python_interpreters():
    """扫描本地 Python 环境"""
    print("正在扫描 Python 环境...", end="", flush=True)
    interpreters = set()
    
    # 扫描 PATH
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for p in paths:
        exe = "python.exe" if platform.system() == "Windows" else "python3"
        full = os.path.join(p, exe)
        if os.path.exists(full) and os.access(full, os.X_OK):
            interpreters.add(full)
            
    # 常见目录
    if platform.system() == "Windows":
        user_profile = os.environ.get("USERPROFILE", "")
        roots = [os.path.join(user_profile, "anaconda3"), "C:\\ProgramData\\Anaconda3"]
        for r in roots:
            if os.path.exists(os.path.join(r, "python.exe")):
                interpreters.add(os.path.join(r, "python.exe"))
    
    interpreters.add(sys.executable)
    print(" 完成。")
    return sorted(list(interpreters))

def get_site_packages(python_exe):
    try:
        cmd = [python_exe, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]
        if platform.system() == "Windows":
             startupinfo = subprocess.STARTUPINFO()
             startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
             result = subprocess.check_output(cmd, startupinfo=startupinfo, encoding='utf-8')
        else:
             result = subprocess.check_output(cmd, encoding='utf-8')
        return result.strip()
    except: return None

def install_to_python_env():
    # 1. 检查配置是否就绪
    if not os.path.exists(CONFIG_PATH):
        print("[错误] 必须先配置 Lumerical 路径才能执行此操作。")
        return

    # 2. 选择 Python 环境
    interpreters = detect_python_interpreters()
    print("\n请选择目标 Python 环境:")
    for i, path in enumerate(interpreters):
        print(f"{i+1}. {path}")
    print(f"{len(interpreters)+1}. 手动输入路径")
    print(f"{len(interpreters)+2}. 返回")
    
    try:
        sel = int(input("选择: "))
        if 1 <= sel <= len(interpreters):
            python_exe = interpreters[sel-1]
        elif sel == len(interpreters) + 1:
            python_exe = input("请输入 python 可执行文件完整路径: ").strip()
        else:
            return
    except: return

    if not os.path.exists(python_exe):
        print("[错误] 路径不存在")
        return

    # 3. 获取库路径并安装
    print(f"正在获取库路径 ({python_exe})...")
    lib_path = get_site_packages(python_exe)
    if not lib_path:
        print("[错误] 无法获取 site-packages 路径")
        return

    target_dir = os.path.join(lib_path, "lumapi")
    print(f"目标安装路径: {target_dir}")
    
    if os.path.exists(target_dir):
        choice = input("检测到目录已存在，是否覆盖? (y/n): ").lower()
        if choice != 'y':
            print("操作已取消")
            return

    try:
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        files = ["__init__.py", "lumapi.py", "config.json"]
        for f in files:
            src = os.path.join(LUMAPI_DIR, f)
            dst = os.path.join(target_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            elif f == "__init__.py":
                 with open(dst, 'w') as f_obj: f_obj.write("from lumapi.lumapi import *\n")
        
        print(f"\n[成功] 已安装到 {target_dir}")
        print("您现在可以在该 Python 环境中使用 'import lumapi'")
    except Exception as e:
        print(f"[错误] 安装失败: {e}")

# ================= 主流程 =================

def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get('lumerical_path'), config.get('version')
    except: pass
    return None, None

def export_files_local():
    if not os.path.exists(CONFIG_PATH):
        print("[错误] 无有效配置")
        return
    try:
        shutil.copy2(os.path.join(LUMAPI_DIR, "lumapi.py"), os.path.join(OUTPUT_DIR, "lumapi.py"))
        shutil.copy2(CONFIG_PATH, os.path.join(OUTPUT_DIR, "config.json"))
        print(f"[成功] 文件已导出到: {OUTPUT_DIR}")
    except Exception as e: print(f"[错误] {e}")

def load_lumapi(lumerical_path, version):
    lumapi_path = get_lumapi_path(lumerical_path, version)
    spec = importlib.util.spec_from_file_location('lumapi', lumapi_path)
    lumapi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lumapi)
    print(f"\n成功加载 API: {lumapi_path}")
    return lumapi

def perform_configuration():
    detected = detect_common_paths()
    if detected:
        print("\n检测到以下路径:")
        for i, (p, v) in enumerate(detected):
            print(f"{i+1}. {p} ({v})")
        print(f"{len(detected)+1}. 手动输入")
        try:
            sel = int(input("选择: "))
            if 1 <= sel <= len(detected):
                path, ver = detected[sel-1]
                if validate_path(path)[0]:
                    save_config(path, ver)
                return
        except: pass

    path = input("\n请输入安装根目录: ").strip()
    p_valid, v_valid = validate_path(path)
    if p_valid: save_config(path, v_valid)

def main():
    print("=== Lumerical Python API 配置工具 (CLI) ===")
    
    while True:
        cfg_path, cfg_ver = load_config()
        has_config = (cfg_path is not None)
        
        print("\n-------------------------")
        if has_config:
            print(f"当前配置: {cfg_path} ({cfg_ver})")
            print("1. [启动] 测试加载环境")
            print("2. [导出] 导出到当前目录")
            print("3. [安装] 安装到 Python 环境 (site-packages)")
            print("4. [重置] 重新配置路径")
            print("5. [退出] 退出")
        else:
            print("当前状态: 未配置")
            print("1. [配置] 开始配置新路径")
            print("2. [退出] 退出")
            
        choice = input("\n选项: ").strip()
        
        if has_config:
            if choice == '1': validate_path(cfg_path); load_lumapi(cfg_path, cfg_ver)
            elif choice == '2': export_files_local()
            elif choice == '3': install_to_python_env()
            elif choice == '4': perform_configuration()
            elif choice == '5': sys.exit()
        else:
            if choice == '1': perform_configuration()
            elif choice == '2': sys.exit()

if __name__ == "__main__":
    main()