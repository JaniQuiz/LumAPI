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

class LumericalGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lumerical 接口配置工具 (PyPI版)")
        
        # --- 路径处理核心逻辑 ---
        # 对于安装版，gui.py 位于 LumAPI 包内部
        self.lumapi_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.lumapi_dir, "config.json")
        self.init_file_path = os.path.join(self.lumapi_dir, "__init__.py")
        
        # 确保 __init__.py 存在 (虽然通常安装包里会有)
        if not os.path.exists(self.init_file_path):
            try:
                with open(self.init_file_path, 'w') as f:
                    f.write("from LumAPI.lumapi import *\n")
            except: pass

        self.create_widgets()
        self.check_config()      # 检查 Lumerical 配置

    def create_widgets(self):
        # 配置列权重
        self.root.columnconfigure(1, weight=1)

        # ==================== Lumerical 部分 ====================
        
        # --- Row 0: Lumerical 路径配置 ---
        tk.Label(self.root, text="Lumerical路径:").grid(row=0, column=0, padx=10, pady=(15, 2), sticky="e")
        
        self.path_var = tk.StringVar()
        self.path_combo = ttk.Combobox(self.root, textvariable=self.path_var, width=50)
        self.path_combo.grid(row=0, column=1, padx=5, pady=(15, 2), sticky="ew")
        self.path_combo.bind('<KeyRelease>', lambda e: self.validate_path(self.path_var.get()))
        self.path_combo.bind("<<ComboboxSelected>>", self.on_path_selected)
        
        tk.Button(self.root, text="浏览...", command=self.browse_path).grid(row=0, column=2, padx=10, pady=(15, 2))

        # --- Row 1: Lumerical 配置状态 ---
        self.status_label = tk.Label(self.root, text="等待配置...", fg="gray", font=("TkDefaultFont", 9))
        self.status_label.grid(row=1, column=0, columnspan=3, pady=0, sticky="n")

        # --- Row 2: 按钮组 ---
        btn_frame = tk.Frame(self.root)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=(15, 25))
        
        self.verify_btn = tk.Button(btn_frame, text="保存配置", command=self.confirm_path, state=tk.DISABLED, width=15)
        self.verify_btn.pack(side=tk.LEFT, padx=10)
        
        self.test_btn = tk.Button(btn_frame, text="测试加载", command=self.test_load, state=tk.DISABLED, width=15)
        self.test_btn.pack(side=tk.LEFT, padx=10)

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
            self.test_btn.config(state=tk.NORMAL)
        else:
            self.test_btn.config(state=tk.DISABLED)

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
            self.test_btn.config(state=tk.DISABLED)
            return
        ver = self.detect_version(path)
        if ver:
            self.status_label.config(text=f"状态: 有效 ({ver})", fg="green")
            self.verify_btn.config(state=tk.NORMAL)
            # 是否启用测试按钮取决于是否已经保存，这里简化逻辑，只要有效即可尝试保存
        else:
            self.status_label.config(text="状态: 无效路径", fg="red")
            self.verify_btn.config(state=tk.DISABLED)
            self.test_btn.config(state=tk.DISABLED)

    def confirm_path(self):
        path = self.path_var.get()
        version = self.detect_version(path)
        try:
            with open(self.config_path, 'w') as f:
                json.dump({'lumerical_path': os.path.abspath(path), 'version': version}, f, indent=4)
            
            self.status_label.config(text=f"状态: 配置已保存 ({version})", fg="blue")
            self.verify_btn.config(state=tk.DISABLED) # 提示已保存
            self.test_btn.config(state=tk.NORMAL)
            
            messagebox.showinfo("成功", "配置已保存。")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}\n可能需要管理员权限。")

    def test_load(self):
        try:
            # 重新加载模块以应用新配置 (如果lumapi本身有缓存)
            # 这里简单尝试验证路径
            from LumAPI.lumapi import validate_path
            path = self.path_var.get()
            version = self.detect_version(path)
            
            lumapi = validate_path(path, version)
            if lumapi:
                messagebox.showinfo("测试成功", f"成功加载 Lumerical API\n版本: {version}")
            else:
                messagebox.showerror("测试失败", "无法加载 Lumerical API")
        except Exception as e:
             messagebox.showerror("错误", f"测试过程出错: {str(e)}")

def main():
    root = tk.Tk()
    app = LumericalGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
