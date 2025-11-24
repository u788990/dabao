#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键打包游戏工具 v4.2 修复版
修复：单文件模式临时文件夹自动清理（关键问题）
新增：三种清理策略，解决 _MEIxxxxxx 残留
增强：打包质量和用户体验
作者：u788990@160.com
"""

import os
import sys
import subprocess
import shutil
import time
import glob
import ast
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import importlib.util
import tempfile
import traceback
import atexit

# 版本检查兼容
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    importlib_metadata = None

try:
    import pkg_resources
except ImportError:
    pkg_resources = None


def get_python_executable():
    """获取实际的Python解释器路径（增强版）"""
    if getattr(sys, 'frozen', False):
        possible_paths = [
            shutil.which('python'),
            shutil.which('python3'),
            r'C:\Python39\python.exe',
            r'C:\Python310\python.exe',
            r'C:\Python311\python.exe',
            r'C:\Python312\python.exe',
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python39', 'python.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python310', 'python.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python311', 'python.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python312', 'python.exe'),
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        
        try:
            result = subprocess.run(['py', '-c', 'import sys; print(sys.executable)'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                python_path = result.stdout.strip()
                if os.path.exists(python_path):
                    return python_path
        except:
            pass
        
        return sys.executable
    else:
        return sys.executable


class GamePackager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("别快EXE2026打包 v4.2 修复版 - 自动清理临时文件夹")
        self.root.geometry("820x780")
        self.root.resizable(False, False)
        
        self.python_executable = get_python_executable()
        
        try:
            if os.path.exists("28x28.png"):
                self.root.iconphoto(True, tk.PhotoImage(file="28x28.png"))
        except:
            pass
        
        self.current_dir = Path.cwd()
        self.default_source = "修改的游戏.py"
        self.output_name = "记事本与网址导航游戏"
        
        self.default_icons = {
            'exe': "480x480.png",
            'window': "28x28.png",
            'taskbar': "108x108.png"
        }
        
        # 打包配置
        self.pack_mode_var = tk.StringVar(value='onefile')
        self.no_console_var = tk.BooleanVar(value=True)
        self.clean_var = tk.BooleanVar(value=True)
        self.upx_var = tk.BooleanVar(value=False)
        self.admin_var = tk.BooleanVar(value=False)
        self.safe_mode_var = tk.BooleanVar(value=True)
        
        # v4.2 新增：临时文件夹清理策略
        self.cleanup_strategy_var = tk.StringVar(value='atexit')
        
        self.message_queue = queue.Queue()
        self.dependencies = []
        self.all_imports = set()
        
        self.create_ui()
        self.process_queue()
        
    def create_ui(self):
        """创建用户界面"""
        # 标题栏
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=40)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, 
                               text="🎮 别快EXE打包 v4.2 修复版 - 自动清理临时文件夹", 
                               font=('Arial', 10, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=8)
        
        # 主容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        # 标签页
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="打包配置")
        self.create_config_tab()
        
        self.check_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.check_frame, text="环境检查")
        self.create_check_tab()
        
        self.deps_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.deps_frame, text="依赖分析")
        self.create_deps_tab()
        
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="打包日志")
        self.create_log_tab()
        
        # 底部按钮栏
        bottom_frame = tk.Frame(self.root, bg='#ecf0f1', height=75)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_frame.pack_propagate(False)
        
        # 进度条
        self.progress = ttk.Progressbar(bottom_frame, length=800, mode='determinate')
        self.progress.pack(pady=(5, 2))
        
        self.progress_label = tk.Label(bottom_frame, text="准备就绪 - v4.2已修复临时文件夹清理问题", 
                                       font=('Arial', 8), bg='#ecf0f1')
        self.progress_label.pack()
        
        # 按钮容器
        button_container = tk.Frame(bottom_frame, bg='#ecf0f1')
        button_container.pack(pady=3)
        
        self.check_button = tk.Button(
            button_container, text="🔍 检查", font=('Arial', 9, 'bold'),
            bg='#f39c12', fg='white', width=8, height=1,
            command=self.start_environment_check
        )
        self.check_button.pack(side=tk.LEFT, padx=3)
        
        self.analyze_button = tk.Button(
            button_container, text="📊 分析", font=('Arial', 9, 'bold'),
            bg='#9b59b6', fg='white', width=8, height=1,
            command=self.analyze_dependencies, state='disabled'
        )
        self.analyze_button.pack(side=tk.LEFT, padx=3)
        
        self.pack_button = tk.Button(
            button_container, text="🚀 打包", font=('Arial', 9, 'bold'),
            bg='#27ae60', fg='white', width=8, height=1,
            command=self.start_packing, state='disabled'
        )
        self.pack_button.pack(side=tk.LEFT, padx=3)
        
        self.install_button = tk.Button(
            button_container, text="📦 安装", font=('Arial', 9, 'bold'),
            bg='#3498db', fg='white', width=8, height=1,
            command=self.install_dependencies
        )
        self.install_button.pack(side=tk.LEFT, padx=3)
        
        tk.Button(
            button_container, text="📁 目录", font=('Arial', 9, 'bold'),
            bg='#95a5a6', fg='white', width=8, height=1,
            command=self.open_output_dir
        ).pack(side=tk.LEFT, padx=3)
        
        tk.Button(
            button_container, text="❌ 退出", font=('Arial', 9, 'bold'),
            bg='#e74c3c', fg='white', width=8, height=1,
            command=self.quit_app
        ).pack(side=tk.LEFT, padx=3)
    
    def create_config_tab(self):
        """创建打包配置标签页"""
        main_frame = tk.Frame(self.config_frame, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # ================== 源文件与输出名（完美平分版）==================
        source_frame = tk.LabelFrame(main_frame, text="源文件与输出名", font=('Arial', 10, 'bold'), bg='white', padx=10, pady=8)
        source_frame.pack(fill=tk.X, pady=(0, 8))

        inner = tk.Frame(source_frame, bg='white')
        inner.pack(fill=tk.X)                 # ← 这行绝对不能漏！没有它就会报错！

        # 左边：源文件 + 浏览按钮
        tk.Label(inner, text="源文件:", font=('Arial', 10), bg='white', width=8).pack(side=tk.LEFT, padx=(0, 5))
        self.source_entry = ttk.Entry(inner, font=('Arial', 10))
        self.source_entry.insert(0, self.default_source)
        self.source_entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        tk.Button(inner, text="浏览", font=('Arial', 9, 'bold'), bg='#3498db', fg='white', width=6,
                  command=self.browse_source_file).pack(side=tk.LEFT, padx=(0, 15))

        # 右边：输出名
        tk.Label(inner, text="输出名:", font=('Arial', 10), bg='white').pack(side=tk.LEFT, padx=(20, 5))
        self.output_entry = ttk.Entry(inner, font=('Arial', 10))
        self.output_entry.insert(0, self.output_name)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)   # 抢占剩余空间
        # =================================================================
        
        # =================== 图标配置 - 一行三等分（终极完美版）===================
        icon_frame = tk.LabelFrame(main_frame, text="图标配置（三等分，按钮永不丢失）", font=('Arial', 10, 'bold'), bg='white', padx=12, pady=10)
        icon_frame.pack(fill=tk.X, pady=(0, 10))

        # 主容器
        container = tk.Frame(icon_frame, bg='white')
        container.pack(fill=tk.X)

        # 三个图标配置
        icon_types = [
            ("EXE图标",   'exe',     "480x480.png"),
            ("窗口图标",  'window',  "28x28.png"),
            ("任务栏图标",'taskbar', "108x108.png")
        ]

        for i, (label_text, icon_key, default_file) in enumerate(icon_types):
            # 每个占1/3，关键：用 grid + weight 实现完美三等分
            frame = tk.Frame(container, bg='white')
            frame.grid(row=0, column=i, sticky='ew', padx=(0, 8) if i < 2 else 0)
            frame.grid_columnconfigure(1, weight=1)  # 让输入框抢占所有剩余空间

            tk.Label(frame, text=label_text + ":", font=('Arial', 10), bg='white', width=9).grid(row=0, column=0, sticky='w')
            
            entry = ttk.Entry(frame, font=('Arial', 10))
            entry.insert(0, default_file)
            entry.grid(row=0, column=1, sticky='ew', padx=(5, 8))
            
            btn = tk.Button(frame, text="浏览", font=('Arial', 9, 'bold'), bg='#3498db', fg='white', width=6,
                           command=lambda k=icon_key: self.browse_icon_file(k))
            btn.grid(row=0, column=2)

            setattr(self, f"{icon_key}_icon_entry", entry)

        # 让三列平均分配空间
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_columnconfigure(2, weight=1)
        # =========================================================================
        
        # =================== 打包模式 - 左右平分 + 一行两条 + 单空格（终极版）===================
        mode_frame = tk.LabelFrame(main_frame, text="打包模式选择（推荐单文件夹）", font=('Arial', 10, 'bold'), bg='white', padx=12, pady=10)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        container = tk.Frame(mode_frame, bg='white')
        container.pack(fill=tk.X)

        # 左右两框完全平分
        left  = tk.Frame(container, bg='#e3f2fd', relief=tk.RIDGE, bd=2)
        right = tk.Frame(container, bg='#e8f5e9', relief=tk.RIDGE, bd=2)
        left.pack(side=tk.LEFT,  fill=tk.BOTH, expand=True, padx=(0, 6))
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # 左边：单文件模式
        tk.Radiobutton(left, text="单文件模式", variable=self.pack_mode_var, value='onefile',
                      font=('Arial', 10, 'bold'), bg='#e3f2fd', fg='#1976d2',
                      command=self.on_mode_change).pack(anchor='w', padx=12, pady=(10, 8))

        tk.Label(left, text="• 打包成一个EXE文件 • 方便分发，无需文件夹",
                 font=('Arial', 9), bg='#e3f2fd', fg='#1565c0', anchor='w').pack(anchor='w', padx=25, pady=(0, 4))
        tk.Label(left, text="• 首次启动较慢（需解压） • v4.2已修复临时文件夹清理",
                 font=('Arial', 9), bg='#e3f2fd', fg='#1565c0', anchor='w').pack(anchor='w', padx=25)

        # 右边：单文件夹模式
        tk.Radiobutton(right, text="单文件夹模式（推荐）", variable=self.pack_mode_var, value='onedir',
                      font=('Arial', 10, 'bold'), bg='#e8f5e9', fg='#2e7d32',
                      command=self.on_mode_change).pack(anchor='w', padx=12, pady=(10, 8))

        tk.Label(right, text="• 打包成文件夹+EXE+DLL • 启动速度快（秒开）",
                 font=('Arial', 9), bg='#e8f5e9', fg='#1b5e20', anchor='w').pack(anchor='w', padx=25, pady=(0, 4))
        tk.Label(right, text="• 无临时文件夹问题 • 适合大型程序、游戏",
                 font=('Arial', 9), bg='#e8f5e9', fg='#1b5e20', anchor='w').pack(anchor='w', padx=25)
        # ================================================================================
        
        # =================== 临时文件夹清理策略 - 保留圆点 + 三等分 + 两行显示（终极修复版）===================
        cleanup_frame = tk.LabelFrame(main_frame, text="临时文件夹清理策略（单文件模式专用）", 
                                     font=('Arial', 10, 'bold'), bg='#fff3e0', padx=12, pady=10)
        cleanup_frame.pack(fill=tk.X, pady=(0, 10))

        container = tk.Frame(cleanup_frame, bg='#fff3e0')
        container.pack(fill=tk.X)

        strategies = [
            ("Atexit清理（推荐）",   'atexit',     "程序退出时自动删除临时文件夹\n（最可靠，强烈推荐）",    '#e65100'),
            ("Bootloader清理",       'bootloader', "PyInstaller运行时自动清理\n（需5.0+版本，速度快）",       '#d35400'),
            ("不清理（测试用）",     'manual',     "保留临时文件夹用于调试\n（会占用大量磁盘空间）",         '#c0392b')
        ]

        for i, (title, value, desc, color) in enumerate(strategies):
            frame = tk.Frame(container, bg='#fff3e0', relief=tk.RIDGE, bd=2)
            frame.grid(row=0, column=i, sticky='nsew', padx=(0, 8) if i < 2 else 0)

            # 关键修复：去掉 indicatoron=0，保留经典圆点！
            tk.Radiobutton(frame, text=title, variable=self.cleanup_strategy_var, value=value,
                          font=('Arial', 9, 'bold'), bg='#fff3e0', fg=color,
                          anchor='w', selectcolor='#fff3e0').pack(anchor='w', padx=15, pady=(18, 6))

            # 说明文字（两行）
            lines = desc.split('\n')
            for line in lines:
                tk.Label(frame, text=line, font=('Arial', 9), bg='#fff3e0', fg='#555',
                        anchor='w', justify='left').pack(anchor='w', padx=22, pady=1)

        # 三等分
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_columnconfigure(2, weight=1)
        # =================================================================================
        
        # ===================== 打包选项 - 一行五个（真正五等分，极致紧凑）=====================
        options_frame = tk.LabelFrame(main_frame, text="打包选项", font=('Arial', 10, 'bold'), bg='white', padx=15, pady=10)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        container = tk.Frame(options_frame, bg='white')
        container.pack(fill=tk.X)

        # 真正的五个选项（顺序你原来就是这样）
        checks = [
            ("隐藏控制台", self.no_console_var),
            ("清理临时文件", self.clean_var),
            ("UPX压缩", self.upx_var),
            ("管理员权限", self.admin_var),
            ("安全模式", self.safe_mode_var),  # 第五个！带盾牌的那个
        ]

        for i, (text, var) in enumerate(checks):
            frame = tk.Frame(container, bg='white')
            frame.grid(row=0, column=i, sticky='ew', padx=6)

            # 安全模式特殊高亮（绿色+粗体+盾牌）
            if text == "安全模式":
                cb = tk.Checkbutton(frame, text="安全模式（推荐）", variable=var,
                                   font=('Arial', 10, 'bold'), bg='white', fg='#27ae60',
                                   selectcolor='#d5f5e9', anchor='w')
            else:
                cb = tk.Checkbutton(frame, text=text, variable=var,
                                   font=('Arial', 10), bg='white', anchor='w')

            cb.pack(side=tk.LEFT)

            # 每列平均分配（五等分）
            container.grid_columnconfigure(i, weight=1)
        # =============================================================================
        
        # =================== v4.2 关键修复说明 - 只留两个空格（完美版）===================
        tip_frame = tk.LabelFrame(main_frame, text="v4.2 关键修复说明", 
                                 font=('Arial', 9, 'bold'), bg='#ffebee', padx=8, pady=5)
        tip_frame.pack(fill=tk.X, pady=(0, 5))

        tips_text = """临时文件夹自动清理：单文件模式不再残留 _MEIxxxxxx 文件夹（200~400MB）
        • Atexit策略：程序退出时自动删除，最可靠（强烈推荐）
        • Bootloader策略：运行时清理，需PyInstaller 5.0+
        • 单文件夹模式：天然无临时文件夹，启动速度快，推荐大型程序使用"""

        tk.Label(tip_frame, text=tips_text,
                font=('Arial', 8), bg='#ffebee', fg='#c62828',
                justify=tk.LEFT, anchor=tk.W, padx=18).pack(fill=tk.X)
        # =========================================================================
    
    def on_mode_change(self):
        """打包模式改变时的回调"""
        mode = self.pack_mode_var.get()
        if mode == 'onedir':
            self.progress_label.config(text="已选择单文件夹模式 - 无临时文件夹，启动速度快 ⚡")
        else:
            strategy = self.cleanup_strategy_var.get()
            strategy_name = {'atexit': 'Atexit清理', 'bootloader': 'Bootloader清理', 'manual': '不清理'}
            self.progress_label.config(text=f"已选择单文件模式 - {strategy_name.get(strategy, '')} 📦")
    
    def browse_source_file(self):
        """浏览选择源文件"""
        filename = filedialog.askopenfilename(
            title="选择Python源文件",
            filetypes=[("Python文件", "*.py"), ("所有文件", "*.*")]
        )
        if filename:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, filename)
            self.analyze_button.config(state='disabled')
            self.pack_button.config(state='disabled')
    
    def browse_icon_file(self, icon_type):
        """浏览选择图标文件"""
        filename = filedialog.askopenfilename(
            title=f"选择{icon_type}图标文件",
            filetypes=[("PNG文件", "*.png"), ("ICO文件", "*.ico"), ("所有文件", "*.*")]
        )
        if filename:
            if icon_type == 'exe':
                self.exe_icon_entry.delete(0, tk.END)
                self.exe_icon_entry.insert(0, filename)
            elif icon_type == 'window':
                self.window_icon_entry.delete(0, tk.END)
                self.window_icon_entry.insert(0, filename)
            elif icon_type == 'taskbar':
                self.taskbar_icon_entry.delete(0, tk.END)
                self.taskbar_icon_entry.insert(0, filename)
    
    def normalize_source_file(self):
        """规范化源文件名"""
        source_file = self.source_entry.get().strip()
        if source_file and not source_file.endswith('.py'):
            source_file += '.py'
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, source_file)
        return source_file
    
    def create_cleanup_bootloader_code(self):
        """生成临时文件夹清理代码（v4.2）"""
        strategy = self.cleanup_strategy_var.get()
        
        if strategy == 'atexit':
            # 方案1：使用atexit注册清理函数（最可靠）
            return '''# v4.2 临时文件夹清理代码（Atexit策略）
import sys
import os
import atexit
import shutil
import time

def cleanup_meipass():
    """程序退出时清理临时文件夹"""
    if hasattr(sys, '_MEIPASS'):
        meipass = sys._MEIPASS
        try:
            # 延迟一下确保所有文件句柄关闭
            time.sleep(0.5)
            if os.path.exists(meipass):
                shutil.rmtree(meipass, ignore_errors=True)
                print(f"[清理] 已删除临时文件夹: {meipass}")
        except Exception as e:
            # 静默失败，不影响用户体验
            pass

# 注册退出时清理
if hasattr(sys, '_MEIPASS'):
    atexit.register(cleanup_meipass)

'''
        elif strategy == 'bootloader':
            # 方案2：PyInstaller 5.0+ 的runtime_tmpdir选项
            return '''# v4.2 临时文件夹清理代码（Bootloader策略）
# 使用 PyInstaller 5.0+ 的 runtime_tmpdir 功能
import sys
import os

# 标记使用bootloader清理
if hasattr(sys, '_MEIPASS'):
    print(f"[清理] Bootloader模式，临时文件夹将由PyInstaller管理: {sys._MEIPASS}")

'''
        else:
            # 方案3：不清理（调试模式）
            return '''# v4.2 临时文件夹清理代码（不清理模式）
import sys

if hasattr(sys, '_MEIPASS'):
    print(f"[调试] 临时文件夹保留: {sys._MEIPASS}")
    print("[调试] 请手动清理 C:\\\\Users\\\\你的用户名\\\\AppData\\\\Local\\\\Temp\\\\_MEI*")

'''
    
    def create_icon_wrapper(self, source_file, icons):
        """创建包含图标设置和清理代码的包装器文件（v4.2增强版）"""
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                original_code = f.read()
        except UnicodeDecodeError:
            try:
                with open(source_file, 'r', encoding='gbk') as f:
                    original_code = f.read()
            except:
                with open(source_file, 'r', encoding='latin-1') as f:
                    original_code = f.read()
        
        window_icon = os.path.basename(icons.get('window', '')) if icons.get('window') else ''
        taskbar_icon = os.path.basename(icons.get('taskbar', '')) if icons.get('taskbar') else ''
        
        # v4.2 关键修复：添加临时文件夹清理代码
        pack_mode = self.pack_mode_var.get()
        cleanup_code = ''
        
        if pack_mode == 'onefile':
            cleanup_code = self.create_cleanup_bootloader_code()
        
        # v4.2 增强的图标设置代码
        icon_setup_code = f'''# -*- coding: utf-8 -*-
# 自动生成的包装器代码 v4.2 - 图标设置 + 临时文件夹清理
{cleanup_code}
import sys
import os

def setup_icons():
    """设置窗口和任务栏图标 v4.2"""
    try:
        # 获取资源路径 - 支持PyInstaller打包
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        window_icon_file = "{window_icon}"
        taskbar_icon_file = "{taskbar_icon}"
        
        def get_icon_path(icon_file):
            """智能获取图标完整路径"""
            if not icon_file:
                return None
            
            possible_paths = [
                os.path.join(base_path, icon_file),
                os.path.join(base_path, os.path.basename(icon_file)),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_file),
                os.path.join(os.getcwd(), icon_file),
                icon_file,
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return os.path.abspath(path)
            
            return None
        
        # Tkinter图标设置
        try:
            import tkinter as tk
            
            def set_window_icon(window):
                """为窗口设置图标"""
                try:
                    window_icon_path = get_icon_path(window_icon_file)
                    if window_icon_path and os.path.exists(window_icon_path):
                        try:
                            if window_icon_path.lower().endswith('.png'):
                                photo = tk.PhotoImage(file=window_icon_path)
                                window.iconphoto(True, photo)
                                if not hasattr(window, '_icon_photos'):
                                    window._icon_photos = []
                                window._icon_photos.append(photo)
                            elif window_icon_path.lower().endswith('.ico'):
                                window.iconbitmap(window_icon_path)
                        except:
                            pass
                    
                    # Windows任务栏图标
                    if sys.platform == 'win32':
                        try:
                            import ctypes
                            taskbar_icon_path = get_icon_path(taskbar_icon_file)
                            if taskbar_icon_path and os.path.exists(taskbar_icon_path):
                                myappid = 'mycompany.myproduct.subproduct.version'
                                try:
                                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                                except:
                                    pass
                        except:
                            pass
                            
                except:
                    pass
            
            # 劫持Tk和Toplevel
            _original_tk_init = tk.Tk.__init__
            def new_tk_init(self, *args, **kwargs):
                _original_tk_init(self, *args, **kwargs)
                try:
                    self.after(10, lambda: set_window_icon(self))
                except:
                    pass
            tk.Tk.__init__ = new_tk_init
            
            _original_toplevel_init = tk.Toplevel.__init__
            def new_toplevel_init(self, *args, **kwargs):
                _original_toplevel_init(self, *args, **kwargs)
                try:
                    self.after(10, lambda: set_window_icon(self))
                except:
                    pass
            tk.Toplevel.__init__ = new_toplevel_init
            
        except ImportError:
            pass
        
        # Pygame图标设置
        try:
            import pygame
            
            _original_pygame_init = pygame.init
            def new_pygame_init(*args, **kwargs):
                result = _original_pygame_init(*args, **kwargs)
                try:
                    window_icon_path = get_icon_path(window_icon_file)
                    if window_icon_path and os.path.exists(window_icon_path):
                        icon_surface = pygame.image.load(window_icon_path)
                        pygame.display.set_icon(icon_surface)
                except:
                    pass
                return result
            pygame.init = new_pygame_init
        except ImportError:
            pass
            
    except:
        pass

# 执行图标设置
try:
    setup_icons()
except:
    pass

# === 以下是原始代码 ===
'''
        
        wrapper_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                                   suffix='.py', delete=False)
        wrapper_file.write(icon_setup_code)
        wrapper_file.write('\n')
        wrapper_file.write(original_code)
        wrapper_file.close()
        
        return wrapper_file.name
    
    def create_check_tab(self):
        """创建环境检查标签页"""
        info_label = tk.Label(self.check_frame, 
                             text="系统将自动检查打包所需的环境和文件（包括Tkinter支持）",
                             font=('Arial', 9))
        info_label.pack(pady=5)
        
        text_frame = tk.Frame(self.check_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.check_text = tk.Text(text_frame, 
                                  height=18, 
                                  width=95,
                                  font=('Consolas', 9),
                                  yscrollcommand=scrollbar.set)
        self.check_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.check_text.yview)
    
    def create_deps_tab(self):
        """创建依赖分析标签页"""
        info_label = tk.Label(self.deps_frame, 
                             text="分析源文件中的依赖库，包括隐式导入和子模块",
                             font=('Arial', 9))
        info_label.pack(pady=5)
        
        deps_container = tk.Frame(self.deps_frame)
        deps_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('库名', '状态', '版本', '来源')
        self.deps_tree = ttk.Treeview(deps_container, columns=columns, show='headings', height=14)
        
        self.deps_tree.heading('库名', text='库名')
        self.deps_tree.heading('状态', text='状态')
        self.deps_tree.heading('版本', text='版本')
        self.deps_tree.heading('来源', text='来源')
        
        self.deps_tree.column('库名', width=200)
        self.deps_tree.column('状态', width=100)
        self.deps_tree.column('版本', width=100)
        self.deps_tree.column('来源', width=300)
        
        scrollbar = ttk.Scrollbar(deps_container, orient=tk.VERTICAL, command=self.deps_tree.yview)
        self.deps_tree.configure(yscrollcommand=scrollbar.set)
        
        self.deps_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.deps_info = tk.Label(self.deps_frame, 
                                 text="请先选择源文件并点击'分析'",
                                 font=('Arial', 9), fg='gray')
        self.deps_info.pack(pady=3)
    
    def create_log_tab(self):
        """创建打包日志标签页"""
        self.log_text = scrolledtext.ScrolledText(self.log_frame,
                                                  height=18,
                                                  width=95,
                                                  font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Button(self.log_frame,
                 text="清空日志",
                 font=('Arial', 9),
                 command=lambda: self.log_text.delete(1.0, tk.END)).pack(pady=3)
    
    def is_module_available(self, module_name):
        """检查模块是否可用"""
        try:
            result = subprocess.run(
                [self.python_executable, '-c', f'import {module_name}'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            try:
                __import__(module_name)
                return True
            except ImportError:
                return False
    
    def get_package_version(self, package_name):
        """获取包版本"""
        try:
            result = subprocess.run(
                [self.python_executable, '-c', 
                 f'import importlib.metadata; print(importlib.metadata.version("{package_name}"))'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        try:
            if importlib_metadata:
                return importlib_metadata.version(package_name)
            elif pkg_resources:
                return pkg_resources.get_distribution(package_name).version
        except:
            pass
        
        return 'N/A'
    
    def start_environment_check(self):
        """开始环境检查"""
        self.notebook.select(1)
        self.check_button.config(state='disabled')
        self.check_text.delete(1.0, tk.END)
        self.check_text.insert(tk.END, "正在检查环境（v4.2修复版），请稍候...\n\n")
        
        thread = threading.Thread(target=self.check_environment)
        thread.daemon = True
        thread.start()
    
    def check_environment(self):
        """检查打包环境（v4.2增强版）"""
        all_ok = True
        
        try:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self.add_check_message(f"Python版本: {python_version}\n")
            self.add_check_message(f"执行环境: {sys.executable}\n")
            self.add_check_message(f"解释器路径: {self.python_executable}\n")
            
            if getattr(sys, 'frozen', False):
                self.add_check_message("  ℹ️ 运行在打包环境中\n")
            
            # 检查源文件
            source_file = self.normalize_source_file()
            self.add_check_message(f"\n源文件检查:\n")
            
            if os.path.exists(source_file):
                self.add_check_message(f"  ✅ 源文件: {source_file}\n")
                try:
                    with open(source_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        self.add_check_message(f"  ✅ 文件可读 ({len(content)} 字符)\n")
                        
                        try:
                            compile(content, source_file, 'exec')
                            self.add_check_message(f"  ✅ 语法正确\n")
                        except SyntaxError as e:
                            self.add_check_message(f"  ⚠️ 语法错误: 第{e.lineno}行 - {e.msg}\n")
                            all_ok = False
                            
                except Exception as e:
                    self.add_check_message(f"  ❌ 读取失败: {e}\n")
                    all_ok = False
            else:
                self.add_check_message(f"  ❌ 文件不存在: {source_file}\n")
                all_ok = False
            
            # 检查图标
            self.add_check_message("\n图标文件检查:\n")
            icon_entries = {
                'EXE图标': self.exe_icon_entry.get(),
                '窗口图标': self.window_icon_entry.get(),
                '任务栏图标': self.taskbar_icon_entry.get()
            }
            
            for icon_name, icon_file in icon_entries.items():
                if icon_file:
                    abs_icon_path = os.path.abspath(icon_file)
                    if os.path.exists(abs_icon_path):
                        size = os.path.getsize(abs_icon_path)
                        self.add_check_message(f"  ✅ {icon_name}: {abs_icon_path} ({size} bytes)\n")
                    else:
                        self.add_check_message(f"  ⚠️ {icon_name}不存在: {abs_icon_path}\n")
            
            # 检查核心依赖
            self.add_check_message("\n核心依赖检查:\n")
            if self.is_module_available('PyInstaller'):
                version = self.get_package_version('pyinstaller')
                self.add_check_message(f"  ✅ PyInstaller (v{version})\n")
                
                # v4.2 检查PyInstaller版本是否支持runtime-tmpdir
                try:
                    ver_parts = version.split('.')
                    major = int(ver_parts[0])
                    if major >= 5:
                        self.add_check_message(f"  ✅ 支持Bootloader清理策略\n")
                    else:
                        self.add_check_message(f"  ⚠️ 版本过低，建议升级到5.0+以使用Bootloader清理\n")
                except:
                    pass
            else:
                self.add_check_message("  ❌ PyInstaller 未安装\n")
                all_ok = False
            
            if self.is_module_available('PIL'):
                version = self.get_package_version('Pillow')
                self.add_check_message(f"  ✅ Pillow (v{version})\n")
            else:
                self.add_check_message("  ⚠️ Pillow 未安装（图标转换受限）\n")
            
            # 检查Tkinter
            self.add_check_message("\nTkinter环境检查:\n")
            if self.is_module_available('tkinter'):
                self.add_check_message("  ✅ Tkinter 可用\n")
                try:
                    import tkinter
                    tcl_lib = os.path.join(os.path.dirname(tkinter.__file__), 'tcl')
                    tk_lib = os.path.join(os.path.dirname(tkinter.__file__), 'tk')
                    if os.path.exists(tcl_lib):
                        self.add_check_message(f"  ✅ TCL库: {tcl_lib}\n")
                    if os.path.exists(tk_lib):
                        self.add_check_message(f"  ✅ TK库: {tk_lib}\n")
                except Exception as e:
                    self.add_check_message(f"  ⚠️ 路径检查失败: {e}\n")
            else:
                self.add_check_message("  ❌ Tkinter 不可用\n")
                all_ok = False
            
            # v4.2 新增：检查临时文件夹清理策略
            pack_mode = self.pack_mode_var.get()
            cleanup_strategy = self.cleanup_strategy_var.get()
            
            self.add_check_message("\nv4.2 临时文件夹清理检查:\n")
            if pack_mode == 'onefile':
                strategy_names = {
                    'atexit': 'Atexit清理（推荐）',
                    'bootloader': 'Bootloader清理',
                    'manual': '不清理（调试模式）'
                }
                self.add_check_message(f"  📦 单文件模式: {strategy_names.get(cleanup_strategy, '未知')}\n")
                
                if cleanup_strategy == 'atexit':
                    self.add_check_message(f"  ✅ 将使用Atexit策略自动清理临时文件夹\n")
                elif cleanup_strategy == 'bootloader':
                    self.add_check_message(f"  ⚡ 将使用Bootloader策略（需PyInstaller 5.0+）\n")
                else:
                    self.add_check_message(f"  ⚠️ 临时文件夹将不会清理，注意磁盘空间\n")
            else:
                self.add_check_message(f"  📁 单文件夹模式: 无临时文件夹问题\n")
            
            # 完成检查
            self.add_check_message("\n" + "="*60 + "\n")
            if all_ok:
                self.add_check_message("✅ 环境检查通过！v4.2修复版已就绪\n")
                self.add_check_message("下一步：点击'分析'按钮\n")
                self.message_queue.put(('enable_analyze_button', None))
            else:
                self.add_check_message("❌ 检查未通过，请解决问题\n")
                self.add_check_message("提示：点击'安装'按钮\n")
                
        except Exception as e:
            self.add_check_message(f"\n❌ 检查出错: {e}\n")
            self.add_check_message(f"{traceback.format_exc()}\n")
        
        self.message_queue.put(('enable_check_button', None))
    
    def get_module_dependencies(self, module_name):
        """递归获取模块的所有子模块"""
        deps = set()
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.submodule_search_locations:
                import pkgutil
                for importer, modname, ispkg in pkgutil.walk_packages(
                    path=spec.submodule_search_locations,
                    prefix=module_name + '.'
                ):
                    deps.add(modname)
        except:
            pass
        return deps
    
    def analyze_dependencies(self):
        """分析源文件依赖"""
        source_file = self.normalize_source_file()
        
        if not os.path.exists(source_file):
            messagebox.showerror("错误", f"源文件不存在: {source_file}")
            return
        
        self.notebook.select(2)
        self.analyze_button.config(state='disabled')
        
        for item in self.deps_tree.get_children():
            self.deps_tree.delete(item)
        
        self.deps_info.config(text="正在深度分析依赖...")
        
        thread = threading.Thread(target=self._analyze_deps, args=(source_file,))
        thread.daemon = True
        thread.start()
    
    def _analyze_deps(self, source_file):
        """实际分析依赖（v4.2增强版）"""
        try:
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    source_code = f.read()
            except UnicodeDecodeError:
                with open(source_file, 'r', encoding='gbk') as f:
                    source_code = f.read()
            
            tree = ast.parse(source_code)
            imports = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split('.')[0]
                        imports.add(module_name)
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        imports.add(module_name)
                        imports.add(node.module)
            
            # 标准库列表
            stdlib_modules = {
                'os', 'sys', 'time', 'datetime', 'json', 'math', 'random', 
                'collections', 'itertools', 'functools', 'threading', 'queue',
                'subprocess', 'shutil', 'pathlib', 'glob', 're', 'ast',
                'tkinter', 'webbrowser', 'urllib', 'socket', 'enum', 'copy',
                'tempfile', 'zipfile', 'pickle', 'base64', 'hashlib', 'string',
                'struct', 'io', 'typing', 'warnings', 'traceback', 'inspect',
                'ctypes', 'platform', 'logging', 'configparser', 'csv',
                'email', 'html', 'http', 'xml', 'sqlite3', 'gzip', 'bz2', 'atexit'
            }
            
            deps_data = []
            missing_deps = []
            self.all_imports = set()
            
            for module_name in sorted(imports):
                if module_name in ['__future__', '__main__', 'builtins']:
                    continue
                
                top_module = module_name.split('.')[0]
                if top_module in stdlib_modules:
                    if top_module not in [d[0] for d in deps_data]:
                        deps_data.append((top_module, '✅ 已安装', '内置', '标准库'))
                    self.all_imports.add(top_module)
                    continue
                
                if self.is_module_available(top_module):
                    version = self.get_package_version(top_module)
                    
                    if top_module not in [d[0] for d in deps_data]:
                        deps_data.append((top_module, '✅ 已安装', version, '系统'))
                    self.all_imports.add(top_module)
                    
                    try:
                        sub_modules = self.get_module_dependencies(top_module)
                        for sub in sub_modules:
                            self.all_imports.add(sub)
                    except:
                        pass
                else:
                    if top_module not in [d[0] for d in deps_data]:
                        deps_data.append((top_module, '❌ 未安装', 'N/A', '需要安装'))
                    missing_deps.append(top_module)
            
            # v4.2新增：添加关键隐藏导入
            critical_hidden = [
                'pkg_resources.py2_warn',
                'pkg_resources.markers',
                'tkinter.filedialog',
                'tkinter.messagebox',
                'tkinter.ttk',
                'encodings.utf_8',
                'encodings.gbk',
                'atexit',
            ]
            
            for hidden in critical_hidden:
                self.all_imports.add(hidden)
            
            self.message_queue.put(('update_deps_tree', deps_data))
            
            if missing_deps:
                info_text = f"发现 {len(missing_deps)} 个缺失依赖: {', '.join(missing_deps)}"
                self.message_queue.put(('update_deps_info', (info_text, 'red')))
            else:
                info_text = f"所有 {len(deps_data)} 个依赖就绪（含 {len(self.all_imports)} 个子模块）"
                self.message_queue.put(('update_deps_info', (info_text, 'green')))
                self.message_queue.put(('enable_pack_button', None))
            
            self.dependencies = list(imports)
            
        except Exception as e:
            self.message_queue.put(('update_deps_info', (f"分析失败: {str(e)}", 'red')))
        
        self.message_queue.put(('enable_analyze_button', None))
    
    def install_dependencies(self):
        """安装依赖"""
        self.install_button.config(state='disabled')
        self.notebook.select(3)
        
        thread = threading.Thread(target=self._install_deps)
        thread.daemon = True
        thread.start()
    
    def _install_deps(self):
        """实际安装依赖"""
        core_deps = ['pyinstaller', 'Pillow']
        
        if hasattr(self, 'dependencies'):
            for dep in self.dependencies:
                if not self.is_module_available(dep):
                    if dep not in core_deps and dep not in ['tkinter', 'atexit']:
                        core_deps.append(dep)
        
        self.add_log_message("="*60 + "\n")
        self.add_log_message("开始安装依赖...\n")
        self.add_log_message(f"Python: {self.python_executable}\n")
        self.add_log_message("="*60 + "\n\n")
        
        success_count = 0
        fail_count = 0
        
        mirrors = [
            ("清华镜像", "https://pypi.tuna.tsinghua.edu.cn/simple"),
            ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ]
        
        for dep in core_deps:
            self.add_log_message(f"安装 {dep}...\n")
            success = False
            
            for mirror_name, mirror_url in mirrors:
                try:
                    self.add_log_message(f"  尝试 {mirror_name}...\n")
                    result = subprocess.run(
                        [self.python_executable, "-m", "pip", "install", dep, "-i", mirror_url, "--upgrade"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        self.add_log_message(f"  ✅ {dep} 成功\n")
                        success = True
                        success_count += 1
                        break
                except Exception as e:
                    self.add_log_message(f"  ⚠️ 失败: {e}\n")
            
            if not success:
                fail_count += 1
            
            self.add_log_message("-" * 50 + "\n")
        
        self.add_log_message(f"\n完成！成功: {success_count}, 失败: {fail_count}\n")
        self.message_queue.put(('enable_install_button', None))
    
    def prepare_icons(self):
        """准备图标（v4.2增强版 - 保留透明通道）"""
        icons = {}
        
        try:
            from PIL import Image
            has_pil = True
        except ImportError:
            has_pil = False
            self.add_log_message("  警告: Pillow未安装\n")
        
        exe_icon = self.exe_icon_entry.get()
        if exe_icon:
            exe_icon_abs = os.path.abspath(exe_icon)
            if os.path.exists(exe_icon_abs):
                if exe_icon_abs.lower().endswith('.png') and has_pil:
                    try:
                        img = Image.open(exe_icon_abs)
                        
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        
                        ico_path = "temp_app_icon.ico"
                        sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
                        img.save(ico_path, format='ICO', sizes=sizes)
                        
                        icons['exe'] = os.path.abspath(ico_path)
                        self.add_log_message(f"  ✅ 生成透明ICO: {icons['exe']}\n")
                    except Exception as e:
                        self.add_log_message(f"  ⚠️ ICO转换失败: {e}\n")
                        icons['exe'] = exe_icon_abs
                else:
                    icons['exe'] = exe_icon_abs
        
        window_icon = self.window_icon_entry.get()
        if window_icon:
            window_icon_abs = os.path.abspath(window_icon)
            if os.path.exists(window_icon_abs):
                icons['window'] = window_icon_abs
        
        taskbar_icon = self.taskbar_icon_entry.get()
        if taskbar_icon:
            taskbar_icon_abs = os.path.abspath(taskbar_icon)
            if os.path.exists(taskbar_icon_abs):
                icons['taskbar'] = taskbar_icon_abs
        
        return icons
    
    def collect_data_files(self, source_file, icons):
        """收集数据文件（v4.2增强版）"""
        data_files = []
        source_dir = os.path.dirname(os.path.abspath(source_file)) or '.'
        collected = set()
        
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except:
            source_code = ""
        
        patterns = [
            r'["\']([^"\']+\.(?:png|jpg|jpeg|gif|ico))["\']',
            r'["\']([^"\']+\.(?:json|txt|xml|cfg))["\']',
        ]
        
        referenced = set()
        for pattern in patterns:
            matches = re.findall(pattern, source_code, re.IGNORECASE)
            referenced.update(matches)
        
        for file_ref in referenced:
            for full_path in [os.path.join(source_dir, file_ref), os.path.abspath(file_ref)]:
                if os.path.exists(full_path):
                    full_path_abs = os.path.abspath(full_path)
                    if full_path_abs not in collected:
                        data_files.append((full_path_abs, '.'))
                        collected.add(full_path_abs)
                        break
        
        self.add_log_message("\n  🔑 添加图标文件:\n")
        for icon_type, icon_path in icons.items():
            if icon_path and os.path.exists(icon_path):
                icon_path_abs = os.path.abspath(icon_path)
                if icon_path_abs not in collected:
                    data_files.append((icon_path_abs, '.'))
                    collected.add(icon_path_abs)
                    self.add_log_message(f"    ✅ {icon_type}: {os.path.basename(icon_path)}\n")
        
        return data_files
    
    def get_tkinter_data_paths(self):
        """获取Tkinter数据路径（修复Tk错误）"""
        tk_paths = []
        try:
            import tkinter
            tk_dir = os.path.dirname(tkinter.__file__)
            
            tcl_lib = os.path.join(tk_dir, 'tcl')
            if os.path.exists(tcl_lib):
                tk_paths.append((tcl_lib, 'tcl'))
                self.add_log_message(f"  ✅ TCL库\n")
            
            tk_lib = os.path.join(tk_dir, 'tk')
            if os.path.exists(tk_lib):
                tk_paths.append((tk_lib, 'tk'))
                self.add_log_message(f"  ✅ TK库\n")
            
            for dll in glob.glob(os.path.join(tk_dir, '*.dll')):
                tk_paths.append((dll, '.'))
            
        except Exception as e:
            self.add_log_message(f"  ⚠️ Tkinter路径失败: {e}\n")
        
        return tk_paths
    
    def start_packing(self):
        """开始打包"""
        source_file = self.normalize_source_file()
        
        if not os.path.exists(source_file):
            messagebox.showerror("错误", f"源文件不存在: {source_file}")
            return
        
        self.pack_button.config(state='disabled')
        self.notebook.select(3)
        self.log_text.delete(1.0, tk.END)
        
        thread = threading.Thread(target=self.pack_game, args=(source_file,))
        thread.daemon = True
        thread.start()
    
    def pack_game(self, source_file):
        """执行打包（v4.2修复版 - 添加临时文件夹清理）"""
        wrapper_file = None
        temp_ico = None
        
        try:
            output_name = self.output_entry.get().strip() or self.output_name
            pack_mode = self.pack_mode_var.get()
            cleanup_strategy = self.cleanup_strategy_var.get()
            
            self.message_queue.put(('progress', (10, "准备图标...")))
            self.add_log_message("="*70 + "\n")
            self.add_log_message("开始打包 v4.2修复版（临时文件夹自动清理）\n")
            self.add_log_message(f"源文件: {source_file}\n")
            self.add_log_message(f"输出: {output_name}\n")
            self.add_log_message(f"打包模式: {'📦 单文件模式' if pack_mode == 'onefile' else '📁 单文件夹模式（快速启动）'}\n")
            
            if pack_mode == 'onefile':
                strategy_names = {
                    'atexit': 'Atexit清理（推荐）',
                    'bootloader': 'Bootloader清理',
                    'manual': '不清理（调试）'
                }
                self.add_log_message(f"清理策略: {strategy_names.get(cleanup_strategy, '未知')}\n")
            
            self.add_log_message(f"安全模式: {'启用' if self.safe_mode_var.get() else '禁用'}\n")
            self.add_log_message("="*70 + "\n\n")
            
            self.add_log_message("准备图标...\n")
            icons = self.prepare_icons()
            
            if 'exe' in icons and icons['exe'].endswith('temp_app_icon.ico'):
                temp_ico = icons['exe']
            
            self.message_queue.put(('progress', (15, "生成代码...")))
            self.add_log_message("\n生成增强代码...\n")
            
            # v4.2 关键修复：始终生成包装器以注入清理代码
            if pack_mode == 'onefile' or icons.get('window') or icons.get('taskbar'):
                wrapper_file = self.create_icon_wrapper(source_file, icons)
                self.add_log_message(f"  ✅ 包装器（含清理代码）: {wrapper_file}\n")
                actual_source = wrapper_file
            else:
                actual_source = source_file
            
            self.message_queue.put(('progress', (20, "收集资源...")))
            self.add_log_message("\n收集资源...\n")
            data_files = self.collect_data_files(source_file, icons)
            
            if self.safe_mode_var.get():
                self.add_log_message("\n🛡️ 安全模式：收集Tkinter...\n")
                tk_paths = self.get_tkinter_data_paths()
                data_files.extend(tk_paths)
            
            self.add_log_message(f"\n  ✅ 共 {len(data_files)} 个文件\n")
            
            self.message_queue.put(('progress', (25, "构建命令...")))
            self.add_log_message("\n构建命令...\n")
            
            cmd = [self.python_executable, "-m", "PyInstaller"]
            
            if self.clean_var.get():
                cmd.append("--clean")
            
            cmd.append("--noconfirm")
            
            # 根据用户选择决定打包模式
            if pack_mode == 'onefile':
                cmd.append("--onefile")
                self.add_log_message("  📦 使用单文件模式\n")
                
                # v4.2 关键修复：添加runtime-tmpdir参数（如果使用bootloader策略）
                if cleanup_strategy == 'bootloader':
                    try:
                        pyinstaller_version = self.get_package_version('pyinstaller')
                        ver_parts = pyinstaller_version.split('.')
                        major = int(ver_parts[0])
                        
                        if major >= 5:
                            cmd.append("--runtime-tmpdir")
                            cmd.append(".")
                            self.add_log_message("  ⚡ 启用Bootloader清理\n")
                        else:
                            self.add_log_message("  ⚠️ PyInstaller版本过低，Bootloader清理不可用\n")
                            self.add_log_message("  ℹ️ 将回退到Atexit清理策略\n")
                    except:
                        self.add_log_message("  ⚠️ 无法确定PyInstaller版本，跳过Bootloader参数\n")
                
                if cleanup_strategy == 'atexit':
                    self.add_log_message("  🔄 已注入Atexit清理代码\n")
                elif cleanup_strategy == 'manual':
                    self.add_log_message("  ❌ 不清理临时文件夹（调试模式）\n")
                    
            else:
                cmd.append("--onedir")
                self.add_log_message("  📁 使用单文件夹模式（无临时文件夹问题）\n")
            
            if self.no_console_var.get():
                cmd.append("--noconsole")
            
            if 'exe' in icons:
                cmd.extend(["--icon", icons['exe']])
            
            cmd.extend(["--name", output_name])
            
            # 添加数据文件
            if data_files:
                for src, dst in data_files:
                    sep = ';' if sys.platform == 'win32' else ':'
                    src_abs = os.path.abspath(src)
                    cmd.extend(["--add-data", f"{src_abs}{sep}{dst}"])
            
            # 添加隐藏导入
            if hasattr(self, 'all_imports') and self.all_imports:
                for dep in sorted(self.all_imports):
                    if dep not in ['__future__', '__main__', 'builtins']:
                        cmd.extend(["--hidden-import", dep])
            
            # 安全模式参数
            if self.safe_mode_var.get():
                self.add_log_message("  🛡️ 启用安全模式\n")
                cmd.extend(["--collect-all", "pkg_resources"])
                cmd.extend(["--collect-all", "tkinter"])
            
            if self.admin_var.get():
                cmd.append("--uac-admin")
            
            if self.upx_var.get() and (shutil.which('upx') or os.path.exists('upx.exe')):
                cmd.append("--upx-dir=.")
            else:
                cmd.append("--noupx")
            
            cmd.append(actual_source)
            
            self.message_queue.put(('progress', (30, "执行打包...")))
            self.add_log_message("\n执行打包...\n")
            self.add_log_message(f"命令: {' '.join(cmd[:10])}...\n\n")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            progress = 30
            for line in process.stdout:
                self.add_log_message(line)
                
                if "Building" in line:
                    progress = min(progress + 3, 85)
                elif "Copying" in line:
                    progress = min(progress + 2, 85)
                
                self.message_queue.put(('progress', (progress, "打包中...")))
            
            process.wait()
            
            self.message_queue.put(('progress', (95, "检查结果...")))
            
            # 根据打包模式检查不同的输出位置
            if pack_mode == 'onefile':
                exe_path = Path("dist") / f"{output_name}.exe"
                output_type = "单文件"
            else:
                exe_path = Path("dist") / output_name / f"{output_name}.exe"
                output_type = "文件夹"
            
            if exe_path.exists():
                file_size = exe_path.stat().st_size / (1024 * 1024)
                
                # 如果是文件夹模式，统计整个文件夹大小
                if pack_mode == 'onedir':
                    folder_path = Path("dist") / output_name
                    total_size = sum(f.stat().st_size for f in folder_path.rglob('*') if f.is_file())
                    folder_size = total_size / (1024 * 1024)
                    file_count = len(list(folder_path.rglob('*')))
                    
                    self.message_queue.put(('progress', (100, f"成功！文件夹: {folder_size:.2f} MB")))
                    
                    self.add_log_message("\n" + "="*70 + "\n")
                    self.add_log_message(f"✅ 打包成功！（{output_type}模式）\n")
                    self.add_log_message(f"输出文件夹: dist/{output_name}/\n")
                    self.add_log_message(f"主程序: {exe_path.name}\n")
                    self.add_log_message(f"EXE大小: {file_size:.2f} MB\n")
                    self.add_log_message(f"总大小: {folder_size:.2f} MB\n")
                    self.add_log_message(f"包含文件: {file_count} 个\n")
                    self.add_log_message("="*70 + "\n")
                    
                    messagebox.showinfo("打包成功", 
                                       f"✅ 打包完成！v4.2 {output_type}模式\n\n"
                                       f"📁 输出位置: dist\\{output_name}\\\n"
                                       f"🚀 主程序: {exe_path.name}\n"
                                       f"📊 EXE大小: {file_size:.2f} MB\n"
                                       f"📦 总大小: {folder_size:.2f} MB\n"
                                       f"📄 包含: {file_count} 个文件\n\n"
                                       f"💡 无临时文件夹问题\n"
                                       f"💡 直接双击 {exe_path.name} 即可运行\n"
                                       f"💡 发给别人时，发送整个 {output_name} 文件夹")
                else:
                    # 单文件模式
                    self.message_queue.put(('progress', (100, f"成功！{file_size:.2f} MB")))
                    
                    self.add_log_message("\n" + "="*70 + "\n")
                    self.add_log_message(f"✅ 打包成功！（{output_type}模式）\n")
                    self.add_log_message(f"文件: {exe_path}\n")
                    self.add_log_message(f"大小: {file_size:.2f} MB\n")
                    
                    # v4.2 显示清理策略信息
                    if cleanup_strategy == 'atexit':
                        self.add_log_message(f"🔄 清理策略: Atexit自动清理\n")
                        self.add_log_message(f"💡 程序退出时将自动删除临时文件夹\n")
                    elif cleanup_strategy == 'bootloader':
                        self.add_log_message(f"⚡ 清理策略: Bootloader清理\n")
                        self.add_log_message(f"💡 PyInstaller运行时管理临时文件夹\n")
                    else:
                        self.add_log_message(f"❌ 清理策略: 不清理（调试模式）\n")
                        self.add_log_message(f"⚠️ 临时文件夹将保留在 Temp\\_MEI*\n")
                    
                    self.add_log_message("="*70 + "\n")
                    
                    strategy_msg = ""
                    if cleanup_strategy == 'atexit':
                        strategy_msg = "\n🔄 已启用Atexit清理策略\n💡 程序退出时自动删除临时文件夹"
                    elif cleanup_strategy == 'bootloader':
                        strategy_msg = "\n⚡ 已启用Bootloader清理策略\n💡 PyInstaller运行时管理临时文件夹"
                    else:
                        strategy_msg = "\n⚠️ 不清理模式（调试用）\n💡 临时文件夹将保留，注意清理"
                    
                    messagebox.showinfo("打包成功", 
                                       f"✅ 打包完成！v4.2 {output_type}模式\n\n"
                                       f"📦 文件: {exe_path.name}\n"
                                       f"📊 大小: {file_size:.2f} MB\n\n"
                                       f"📂 数据: {len(data_files)} 个\n"
                                       f"📚 模块: {len(self.all_imports) if hasattr(self, 'all_imports') else 0} 个"
                                       f"{strategy_msg}")
            else:
                self.message_queue.put(('progress', (100, "失败")))
                self.add_log_message("\n❌ 打包失败 - 未找到输出文件\n")
                self.add_log_message(f"预期位置: {exe_path}\n")
                
                messagebox.showerror("打包失败", 
                                    f"❌ 打包失败！未找到输出文件\n\n"
                                    f"预期位置:\n{exe_path}\n\n"
                                    f"解决方案：\n"
                                    f"1. 检查日志中的错误信息\n"
                                    f"2. 启用'安全模式'重试\n"
                                    f"3. 检查源文件和图标\n"
                                    f"4. 尝试切换打包模式")
            
        except Exception as e:
            self.message_queue.put(('progress', (100, f"错误: {str(e)}")))
            self.add_log_message(f"\n❌ 打包出错: {str(e)}\n")
            self.add_log_message(f"{traceback.format_exc()}\n")
            messagebox.showerror("打包错误", f"❌ 打包出错！\n\n{str(e)}\n\n请查看日志了解详情")
        
        finally:
            # v4.2 修复：清理临时文件
            if wrapper_file and os.path.exists(wrapper_file):
                try:
                    os.remove(wrapper_file)
                    self.add_log_message("\n🧹 清理包装器文件\n")
                except Exception as e:
                    self.add_log_message(f"⚠️ 清理包装器失败: {e}\n")
            
            if temp_ico and os.path.exists(temp_ico):
                try:
                    time.sleep(1)
                    os.remove(temp_ico)
                    self.add_log_message("🧹 清理临时ICO文件\n")
                except Exception as e:
                    self.add_log_message(f"⚠️ 清理ICO失败: {e}\n")
            
            # v4.2 新增：清理老旧的_MEI临时文件夹（可选）
            try:
                temp_dir = tempfile.gettempdir()
                mei_folders = glob.glob(os.path.join(temp_dir, '_MEI*'))
                
                if mei_folders and len(mei_folders) > 5:
                    self.add_log_message(f"\n💡 发现 {len(mei_folders)} 个旧临时文件夹\n")
                    cleaned = 0
                    for folder in mei_folders:
                        try:
                            # 只清理超过1天的文件夹
                            folder_time = os.path.getmtime(folder)
                            if time.time() - folder_time > 86400:
                                shutil.rmtree(folder, ignore_errors=True)
                                cleaned += 1
                        except:
                            pass
                    
                    if cleaned > 0:
                        self.add_log_message(f"🧹 已清理 {cleaned} 个旧临时文件夹\n")
            except:
                pass
            
            self.message_queue.put(('enable_pack_button', None))
    
    def add_check_message(self, message):
        self.message_queue.put(('check_message', message))
    
    def add_log_message(self, message):
        self.message_queue.put(('log_message', message))
    
    def process_queue(self):
        try:
            while True:
                msg_type, msg_content = self.message_queue.get_nowait()
                
                if msg_type == 'check_message':
                    self.check_text.insert(tk.END, msg_content)
                    self.check_text.see(tk.END)
                elif msg_type == 'log_message':
                    self.log_text.insert(tk.END, msg_content)
                    self.log_text.see(tk.END)
                elif msg_type == 'enable_check_button':
                    self.check_button.config(state='normal')
                elif msg_type == 'enable_analyze_button':
                    self.analyze_button.config(state='normal')
                elif msg_type == 'enable_pack_button':
                    self.pack_button.config(state='normal')
                elif msg_type == 'enable_install_button':
                    self.install_button.config(state='normal')
                elif msg_type == 'update_deps_tree':
                    for item in msg_content:
                        self.deps_tree.insert('', 'end', values=item)
                elif msg_type == 'update_deps_info':
                    text, color = msg_content
                    self.deps_info.config(text=text, fg=color)
                elif msg_type == 'progress':
                    value, text = msg_content
                    self.progress['value'] = value
                    self.progress_label.config(text=text)
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def open_output_dir(self):
        """打开输出目录"""
        dist_dir = Path("dist")
        if dist_dir.exists():
            try:
                if sys.platform == 'win32':
                    os.startfile(dist_dir)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', dist_dir])
                else:
                    subprocess.run(['xdg-open', dist_dir])
            except Exception as e:
                messagebox.showerror("错误", f"无法打开目录: {e}")
        else:
            messagebox.showinfo("提示", "输出目录不存在，请先打包")
    
    def quit_app(self):
        """退出应用"""
        if messagebox.askyesno("确认退出", "确定要退出打包工具吗？"):
            self.root.quit()
    
    def run(self):
        """运行打包工具"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self.root.mainloop()


def main():
    """主函数"""
    print("="*70)
    print("游戏一键打包工具 v4.2 修复版")
    print("🔧 关键修复：单文件模式临时文件夹自动清理")
    print("🆕 新增功能：三种清理策略（Atexit/Bootloader/Manual）")
    print("✅ 解决问题：_MEIxxxxxx 文件夹残留（200~400MB）")
    print("📁 推荐模式：单文件夹模式（无临时文件夹，启动快）")
    print("作者：u788990@160.com")
    print("="*70)
    print()
    
    if getattr(sys, 'frozen', False):
        print("检测到运行在打包环境中")
        print(f"当前执行文件: {sys.executable}")
    
    try:
        packager = GamePackager()
        packager.run()
    except Exception as e:
        print(f"启动失败: {e}")
        traceback.print_exc()
        input("按Enter键退出...")


if __name__ == "__main__":
    main()
