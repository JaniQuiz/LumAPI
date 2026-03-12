import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
import json
import os
import platform
import importlib.util
import re
import sys
import shutil
import subprocess

class LumericalGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lumerical 接口配置工具")
        
        # --- 路径处理核心逻辑 ---
        if getattr(sys, 'frozen', False):
            self.base_dir = sys._MEIPASS 
            self.output_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.output_dir = self.base_dir

        self.lumapi_dir = os.path.join(self.base_dir, "lumapi")
        self.config_path = os.path.join(self.lumapi_dir, "config.json")
        self.init_file_path = os.path.join(self.lumapi_dir, "__init__.py")
        
        # 确保目录存在
        if not getattr(sys, 'frozen', False) and not os.path.exists(self.lumapi_dir):
            os.makedirs(self.lumapi_dir, exist_ok=True)
            
        # 确保 __init__.py 存在
        if not os.path.exists(self.init_file_path):
            try:
                with open(self.init_file_path, 'w') as f:
                    f.write("from lumapi.lumapi import *\n")
            except: pass

        self.create_widgets()
        self.check_config()      # 检查 Lumerical 配置
        self.check_python_envs() # 检查 Python 环境

    def create_widgets(self):
        # 配置列权重
        self.root.columnconfigure(1, weight=1)

        # ==================== Lumerical 部分 ====================
        
        # --- Row 0: Lumerical 路径配置 ---
        # pady=(15, 2): 上边距15(留空)，下边距2(紧贴状态行)
        tk.Label(self.root, text="Lumerical路径:").grid(row=0, column=0, padx=10, pady=(15, 2), sticky="e")
        
        self.path_var = tk.StringVar()
        self.path_combo = ttk.Combobox(self.root, textvariable=self.path_var, width=50)
        self.path_combo.grid(row=0, column=1, padx=5, pady=(15, 2), sticky="ew")
        self.path_combo.bind('<KeyRelease>', lambda e: self.validate_path(self.path_var.get()))
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        
        tk.Button(self.root, text="浏览...", command=self.browse_path).grid(row=0, column=2, padx=10, pady=(15, 2))

        # --- Row 1: Lumerical 配置状态 ---
        # pady=0: 极度紧凑
        self.status_label = tk.Label(self.root, text="等待配置...", fg="gray", font=("TkDefaultFont", 9))
        self.status_label.grid(row=1, column=0, columnspan=3, pady=0, sticky="n")

        # --- Row 2: 按钮组 ---
        # pady=(5, 25): 上边距5(紧贴状态行)，下边距25(作为两部分之间的自然分隔，替代分隔线)
        btn_frame = tk.Frame(self.root)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=(5, 25))
        
        self.verify_btn = tk.Button(btn_frame, text="保存配置", command=self.confirm_path, state=tk.DISABLED, width=15)
        self.verify_btn.pack(side=tk.LEFT, padx=20)
        
        self.export_local_btn = tk.Button(btn_frame, text="导出到本地目录", command=self.export_files_local, state=tk.DISABLED, width=15)
        self.export_local_btn.pack(side=tk.LEFT, padx=20)


        # ==================== Python 部分 ====================

        # --- Row 4: Python 解释器选择 ---
        # pady=(0, 2): 紧贴下方的状态行
        tk.Label(self.root, text="Python解释器:").grid(row=4, column=0, padx=10, pady=(0, 2), sticky="e")
        
        self.py_path_var = tk.StringVar()
        self.py_combo = ttk.Combobox(self.root, textvariable=self.py_path_var, width=50)
        self.py_combo.grid(row=4, column=1, padx=5, pady=(0, 2), sticky="ew")
        self.py_combo.bind("<<ComboboxSelected>>", lambda e: self.check_python_status())
        self.py_combo.bind('<KeyRelease>', lambda e: self.check_python_status())
        
        tk.Button(self.root, text="浏览...", command=self.browse_python).grid(row=4, column=2, padx=10, pady=(0, 2))

        # --- Row 5: Python 解释器状态 ---
        self.py_status_label = tk.Label(self.root, text="请选择 Python 环境", fg="gray", font=("TkDefaultFont", 9))
        self.py_status_label.grid(row=5, column=0, columnspan=3, pady=0, sticky="n")

        # --- Row 6: 导出按钮 ---
        # pady=(5, 20): 上边距5(紧贴状态行)，下边距20(底部留白)
        self.install_btn = tk.Button(self.root, text="导出库文件到该 Python 环境", command=self.install_to_python, state=tk.DISABLED, bg="#dddddd")
        self.install_btn.grid(row=6, column=0, columnspan=3, pady=(5, 20))


    # ================= Lumerical 路径逻辑 =================
    def detect_common_paths(self):
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
                potential_paths = [
                    os.path.join(drive, "Program Files", "Lumerical"),
                    os.path.join(drive, "Program Files (x86)", "Lumerical"),
                    os.path.join(drive, "Lumerical"),
                    os.path.join(drive, "Program Files", "Ansys Inc"),
                    os.path.join(drive, "Program Files (x86)", "Ansys Inc")
                ]
                for path in potential_paths:
                    if os.path.exists(path):
                        version = self.detect_version(path)
                        if version: common_paths.append((path, version))
        elif platform.system() == "Linux":
            potential_paths = [
                "/opt/lumerical", "/usr/local/lumerical",
                "/usr/ansys_inc", "/opt/ansys_inc",
                os.path.expanduser("~/Ansys/ansys_inc"), os.path.expanduser("~/ansys_inc")
            ]
            for path in potential_paths:
                if os.path.exists(path):
                    version = self.detect_version(path)
                    if version: common_paths.append((path, version))
        return common_paths

    def detect_version(self, root):
        try:
            if not os.path.exists(root): return None
            for item in os.listdir(root):
                item_path = os.path.join(root, item)
                if os.path.isdir(item_path) and re.match(r'^v\d{3}$', item):
                    if self.get_lumapi_path_check(root, item):
                        return item
            return None
        except: return None

    def get_lumapi_path_check(self, lumerical_root, version):
        base = os.path.join(lumerical_root, version)
        p1 = os.path.join(base, "Lumerical", "api", "python", "lumapi.py")
        if os.path.exists(p1): return True
        p2 = os.path.join(base, "api", "python", "lumapi.py")
        if os.path.exists(p2): return True
        return False

    def check_config(self):
        common = self.detect_common_paths()
        valid_config = False
        config_path_val = None
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                lumerical_path = config.get('lumerical_path')
                version = config.get('version')
                if lumerical_path and version:
                    if self.get_lumapi_path_check(lumerical_path, version):
                        config_path_val = lumerical_path
                        valid_config = True
            except: pass
        
        values = [f"{p} ({v})" for p, v in common]
        if config_path_val and not any(config_path_val in v for v in values):
            values.insert(0, f"{config_path_val} (Config)")
            
        self.path_combo['values'] = values
        if values: 
            self.path_combo.current(0)
            self.on_path_selected(None)

        if valid_config:
            self.path_var.set(config_path_val)
            self.validate_path(config_path_val)
            self.export_local_btn.config(state=tk.NORMAL)
        else:
            self.export_local_btn.config(state=tk.DISABLED)
            self.install_btn.config(state=tk.DISABLED)

    def on_path_selected(self, event):
        val = self.path_combo.get()
        if " (" in val:
            self.path_var.set(val.split(" (")[0])
            self.validate_path(self.path_var.get())

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)
            self.validate_path(path)

    def validate_path(self, path):
        if not path:
            self.status_label.config(text="请输入路径", fg="red")
            self.verify_btn.config(state=tk.DISABLED)
            self.export_local_btn.config(state=tk.DISABLED)
            self.install_btn.config(state=tk.DISABLED)
            return
        ver = self.detect_version(path)
        if ver:
            self.status_label.config(text=f"状态: 有效 ({ver})", fg="green")
            self.verify_btn.config(state=tk.NORMAL)
            # 注意：保存按钮启用不代表可以导出，必须先保存（check_config会处理已保存的状态）
        else:
            self.status_label.config(text="状态: 无效路径", fg="red")
            self.verify_btn.config(state=tk.DISABLED)
            self.export_local_btn.config(state=tk.DISABLED)
            self.install_btn.config(state=tk.DISABLED)

    def confirm_path(self):
        path = self.path_var.get()
        version = self.detect_version(path)
        try:
            if not getattr(sys, 'frozen', False):
                 os.makedirs(self.lumapi_dir, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump({'lumerical_path': os.path.abspath(path), 'version': version}, f, indent=4)
            
            self.status_label.config(text=f"状态: 配置已保存 ({version})", fg="blue")
            self.verify_btn.config(state=tk.DISABLED) # 提示已保存
            
            # 启用导出功能
            self.export_local_btn.config(state=tk.NORMAL)
            self.check_python_status() # 刷新 Python 按钮状态
            
            messagebox.showinfo("成功", "配置已保存。")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def export_files_local(self):
        try:
            src_files = ["lumapi.py", "config.json"]
            for f_name in src_files:
                src = os.path.join(self.lumapi_dir, f_name)
                dst = os.path.join(self.output_dir, f_name)
                if not os.path.exists(src): raise FileNotFoundError(f"Missing {f_name}")
                shutil.copy2(src, dst)
            messagebox.showinfo("成功", f"文件已导出到: {self.output_dir}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ================= Python 环境逻辑 =================
    def check_python_envs(self):
        """自动检测 Python 环境"""
        interpreters = set()
        
        # 1. 扫描 PATH
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for p in paths:
            exe = "python.exe" if platform.system() == "Windows" else "python3"
            full_path = os.path.join(p, exe)
            if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                interpreters.add(full_path)

        # 2. 常见目录扫描
        if platform.system() == "Windows":
            user_profile = os.environ.get("USERPROFILE", "")
            common_roots = [
                os.path.join(user_profile, "anaconda3"),
                os.path.join(user_profile, "miniconda3"),
                "C:\\ProgramData\\Anaconda3",
                "C:\\Python39", "C:\\Python310", "C:\\Python311", "C:\\Python312"
            ]
            for root in common_roots:
                if os.path.exists(os.path.join(root, "python.exe")):
                    interpreters.add(os.path.join(root, "python.exe"))
        else:
            if os.path.exists("/usr/bin/python3"): interpreters.add("/usr/bin/python3")
            if os.path.exists("/usr/local/bin/python3"): interpreters.add("/usr/local/bin/python3")

        # 当前运行的 Python
        interpreters.add(sys.executable)
        
        sorted_interpreters = sorted(list(interpreters))
        self.py_combo['values'] = sorted_interpreters
        if sorted_interpreters:
            self.py_combo.current(0)
            self.check_python_status()

    def browse_python(self):
        file_types = [("Python Executable", "python.exe")] if platform.system() == "Windows" else [("Python Executable", "python*")]
        path = filedialog.askopenfilename(title="选择 Python 解释器", filetypes=file_types)
        if path:
            self.py_path_var.set(path)
            self.check_python_status()

    def check_python_status(self):
        """Row 5: 更新 Python 状态标签并检查按钮启用状态"""
        py_path = self.py_path_var.get()
        
        # 1. 检查 Python 路径有效性
        if not py_path or not os.path.exists(py_path):
            self.py_status_label.config(text="状态: 请选择有效的 Python 解释器", fg="gray")
            self.install_btn.config(state=tk.DISABLED, text="导出库文件到该 Python 环境")
            return

        # 2. 检查 Lumerical 配置是否已保存 (本地导出按钮是否可用作为判断依据)
        if str(self.export_local_btn['state']) == 'disabled':
            self.py_status_label.config(text="状态: 等待 Lumerical 配置保存...", fg="orange")
            self.install_btn.config(state=tk.DISABLED, text="请先保存配置")
            return

        # 3. 一切就绪
        self.py_status_label.config(text="状态: 就绪", fg="green")
        self.install_btn.config(state=tk.NORMAL, text="导出库文件到该 Python 环境")

    def get_site_packages(self, python_exe):
        try:
            cmd = [python_exe, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.check_output(cmd, startupinfo=startupinfo, encoding='utf-8')
            else:
                result = subprocess.check_output(cmd, encoding='utf-8')
            return result.strip()
        except Exception as e:
            print(e)
            return None

    def install_to_python(self):
        python_exe = self.py_path_var.get()
        
        # 获取库路径
        target_lib_path = self.get_site_packages(python_exe)
        if not target_lib_path or not os.path.exists(target_lib_path):
            messagebox.showerror("错误", f"无法获取库路径或路径不存在:\n{target_lib_path}")
            return

        target_lumapi_dir = os.path.join(target_lib_path, "lumapi")
        
        # 覆盖检查
        if os.path.exists(target_lumapi_dir):
            if not messagebox.askyesno("覆盖警告", f"目录已存在:\n{target_lumapi_dir}\n\n是否覆盖其中的 lumapi 库文件？"):
                return
        else:
            os.makedirs(target_lumapi_dir, exist_ok=True)

        # 复制文件
        try:
            files_to_copy = ["__init__.py", "lumapi.py", "config.json"]
            for f_name in files_to_copy:
                src = os.path.join(self.lumapi_dir, f_name)
                dst = os.path.join(target_lumapi_dir, f_name)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                else:
                    if f_name == "config.json":
                        raise FileNotFoundError("config.json 未找到，请先生成配置")
                    if f_name == "__init__.py":
                        with open(dst, 'w') as f: f.write("from lumapi.lumapi import *\n")

            messagebox.showinfo("安装成功", f"lumapi 库已成功安装到:\n{target_lumapi_dir}\n\n在该 Python 环境中可直接使用: import lumapi")
        except Exception as e:
            messagebox.showerror("安装失败", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = LumericalGUI(root)
    root.mainloop()