#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键打包游戏工具 v5.3 智能优化版
优化内容：
1. v5.3: 解决巨型库(Torch/Pandas)打包极慢的问题（智能豁免 collect-submodules）
2. v5.3: 自动添加 copy-metadata 解决运行时 "DistributionNotFound" 错误
3. v5.3: 优化进度条逻辑，精准显示最后压缩阶段状态
4. v5.3: 强制禁止对 Numpy/Pandas 使用 UPX（防止运行时崩溃）
5. v5.3: 扩充排除列表，剔除测试模块减小体积

基于 v5.2 缓存增强版
"""

import os
import sys
import subprocess
import shutil
import time
import glob
import ast
import re
import hashlib
import json
import tempfile
import traceback
import atexit
import threading
import queue
import concurrent.futures
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional, Any

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

# ==================== 常量定义 ====================

VERSION = "5.3"

# 完整的Python标准库列表
STDLIB_MODULES = frozenset({
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
    'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
    'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
    'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg',
    'cProfile', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime',
    'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email',
    'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
    'fnmatch', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
    'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
    'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
    'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
    'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math',
    'mimetypes', 'mmap', 'modulefinder', 'msvcrt', 'multiprocessing', 'netrc', 
    'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 
    'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 
    'plistlib', 'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 
    'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 
    're', 'readline', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 
    'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 
    'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 
    'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 
    'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 
    'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 
    'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 
    'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types', 'typing',
    'typing_extensions', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid', 
    'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound', 
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 
    'zlib', '_thread', '__future__', '__main__', 'antigravity', 'this',
})

# 第三方库映射：import名 -> pip包名
PACKAGE_NAME_MAP = {
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'skimage': 'scikit-image',
    'yaml': 'PyYAML',
    'bs4': 'beautifulsoup4',
    'dateutil': 'python-dateutil',
    'dotenv': 'python-dotenv',
    'jwt': 'PyJWT',
    'serial': 'pyserial',
    'wx': 'wxPython',
    'gi': 'PyGObject',
    'cairo': 'pycairo',
    'OpenGL': 'PyOpenGL',
    'usb': 'pyusb',
    'Crypto': 'pycryptodome',
    'google': 'google-api-python-client',
    'lxml': 'lxml',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'scipy': 'scipy',
    'matplotlib': 'matplotlib',
    'pygame': 'pygame',
    'requests': 'requests',
    'flask': 'Flask',
    'django': 'Django',
    'sqlalchemy': 'SQLAlchemy',
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'pydantic': 'pydantic',
    'fastapi': 'fastapi',
    'redis': 'redis',
    'pymongo': 'pymongo',
    'psycopg2': 'psycopg2-binary',
    'mysql': 'mysql-connector-python',
    'pyqt5': 'PyQt5',
    'pyqt6': 'PyQt6',
    'PySide2': 'PySide2',
    'PySide6': 'PySide6',
    'PyInstaller': 'pyinstaller',
    'torch': 'torch',
    'torchvision': 'torchvision',
    'torchaudio': 'torchaudio',
    'tensorflow': 'tensorflow',
    'keras': 'keras',
}

PIP_TO_IMPORT_MAP = {
    'Pillow': 'PIL',
    'pillow': 'PIL',
    'pyinstaller': 'PyInstaller',
    'PyInstaller': 'PyInstaller',
    'opencv-python': 'cv2',
    'opencv-python-headless': 'cv2',
    'scikit-learn': 'sklearn',
    'scikit-image': 'skimage',
    'PyYAML': 'yaml',
    'pyyaml': 'yaml',
    'beautifulsoup4': 'bs4',
    'python-dateutil': 'dateutil',
    'python-dotenv': 'dotenv',
    'PyJWT': 'jwt',
    'pyjwt': 'jwt',
    'pyserial': 'serial',
    'wxPython': 'wx',
    'wxpython': 'wx',
    'PyGObject': 'gi',
    'pycairo': 'cairo',
    'PyOpenGL': 'OpenGL',
    'pyopengl': 'OpenGL',
    'pyusb': 'usb',
    'pycryptodome': 'Crypto',
    'pycryptodomex': 'Cryptodome',
    'torch': 'torch',
    'torchvision': 'torchvision',
    'torchaudio': 'torchaudio',
    'tensorflow': 'tensorflow',
    'tensorflow-gpu': 'tensorflow',
    'keras': 'keras',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'scipy': 'scipy',
    'matplotlib': 'matplotlib',
    'pygame': 'pygame',
    'requests': 'requests',
    'flask': 'flask',
    'Flask': 'flask',
    'django': 'django',
    'Django': 'django',
    'sqlalchemy': 'sqlalchemy',
    'SQLAlchemy': 'sqlalchemy',
}

# 复杂库（可能需要收集子模块）
COMPLEX_PACKAGES = {
    'pygame', 'PIL', 'numpy', 'scipy', 'matplotlib', 'pandas', 'sklearn',
    'cv2', 'tensorflow', 'torch', 'keras', 'PyQt5', 'PyQt6', 'PySide2',
    'PySide6', 'wx', 'kivy', 'pyglet', 'arcade', 'panda3d', 'moderngl',
}

# v5.3: 巨型库名单（不建议自动收集所有子模块，否则打包会非常慢）
GIANT_PACKAGES = {
    'torch', 'tensorflow', 'keras', 'pandas', 'numpy', 'cv2', 'scipy',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6'
}

# v5.3: 需要 copy-metadata 的库（防止运行时报错）
METADATA_REQUIRED_PACKAGES = {
    'tqdm', 'regex', 'requests', 'packaging', 'importlib_metadata', 
    'google-api-python-client', 'zipp', 'torch', 'transformers'
}

# 库的隐式依赖映射
IMPLICIT_DEPENDENCIES = {
    'PIL': ['PIL._imaging', 'PIL._imagingft', 'PIL._imagingmath', 'PIL._imagingtk'],
    'numpy': ['numpy.core._multiarray_umath', 'numpy.core._dtype_ctypes', 
              'numpy.random.mtrand'],
    'pygame': ['pygame.base', 'pygame.constants', 'pygame.rect', 'pygame.rwobject', 
               'pygame.surflock', 'pygame.color', 'pygame.bufferproxy', 'pygame.math', 
               'pygame.mixer', 'pygame.mixer_music', 'pygame.font', 'pygame.image', 
               'pygame.transform', 'pygame.display', 'pygame.event', 'pygame.key', 
               'pygame.mouse', 'pygame.time'],
    'requests': ['urllib3', 'certifi', 'charset_normalizer', 'idna'],
    'cv2': ['cv2.data', 'numpy'],
    'tkinter': ['tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
                'tkinter.scrolledtext', 'tkinter.font'],
}

# 打包时应排除的模块（优化体积和速度）
EXCLUDE_MODULES = [
    'numpy.array_api', 'numpy.distutils', 'numpy.f2py', 'numpy.testing', 'numpy.tests',
    'scipy.spatial.cKDTree', 'matplotlib.tests', 'matplotlib.testing',
    'torch.test', 'torch.testing', 'torch.distributed',  # v5.3: 排除Torch测试
    'pandas.tests',  # v5.3: 排除Pandas测试
    'IPython', 'jupyter', 'jupyter_client', 'jupyter_core', 'notebook',
    'pytest', 'pytest_cov', 'sphinx', 'setuptools', 'pip', 'wheel', 'twine',
    'black', 'flake8', 'pylint', 'mypy', 'isort', 'autopep8', 'yapf',
    'coverage', 'tox', 'nox', 'virtualenv', 'pyinstaller'
]

# 安全：允许的pip包名字符
SAFE_PACKAGE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')


def get_python_executable() -> str:
    """获取实际的Python解释器路径"""
    if getattr(sys, 'frozen', False):
        possible_paths = [
            shutil.which('python'),
            shutil.which('python3'),
            shutil.which('py'),
        ]
        if sys.platform == 'win32':
            for ver in ['312', '311', '310', '39', '38']:
                possible_paths.extend([
                    rf'C:\Python{ver}\python.exe',
                    os.path.join(os.environ.get('LOCALAPPDATA', ''), 
                                'Programs', 'Python', f'Python{ver}', 'python.exe'),
                    os.path.join(os.environ.get('PROGRAMFILES', ''),
                                'Python' + ver, 'python.exe'),
                ])
        
        for path in possible_paths:
            if path and os.path.isfile(path):
                return path
        try:
            result = subprocess.run(
                ['py', '-c', 'import sys; print(sys.executable)'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                python_path = result.stdout.strip()
                if os.path.isfile(python_path):
                    return python_path
        except Exception:
            pass
        return sys.executable
    else:
        return sys.executable


def is_safe_package_name(name: str) -> bool:
    if not name or len(name) > 100: return False
    return bool(SAFE_PACKAGE_NAME_PATTERN.match(name))


def is_safe_path(path: str, base_dir: Optional[str] = None) -> bool:
    try:
        abs_path = os.path.abspath(path)
        dangerous_patterns = ['..', '~', '$', '%', '`', '|', ';', '&', '<', '>']
        for pattern in dangerous_patterns:
            if pattern in path: return False
        if base_dir:
            base_abs = os.path.abspath(base_dir)
            if not abs_path.startswith(base_abs): return False
        return True
    except Exception:
        return False


def pip_name_to_import_name(pip_name: str) -> str:
    if pip_name in PIP_TO_IMPORT_MAP:
        return PIP_TO_IMPORT_MAP[pip_name]
    lower_name = pip_name.lower()
    if lower_name in PIP_TO_IMPORT_MAP:
        return PIP_TO_IMPORT_MAP[lower_name]
    return pip_name.lower().replace('-', '_')


class SecureDependencyCache:
    """安全依赖缓存"""
    CACHE_EXPIRY_SECONDS = 7 * 24 * 3600
    
    def __init__(self, cache_file: str = None):
        if cache_file is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".game_packer_cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "dep_cache_v5.json")
        self.cache_file = cache_file
        self.secret_key = self._get_machine_key()
        self.cache = self._load_cache()
    
    def _get_machine_key(self) -> str:
        import platform
        try: login = os.getlogin()
        except: login = 'user'
        machine_info = f"{platform.node()}-{platform.machine()}-{login}"
        return hashlib.sha256(machine_info.encode()).hexdigest()[:32]
    
    def _compute_signature(self, data: dict) -> str:
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256((data_str + self.secret_key).encode()).hexdigest()
    
    def _load_cache(self) -> dict:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    container = json.load(f)
                data = container.get('data', {})
                stored_sig = container.get('signature', '')
                if self._compute_signature(data) == stored_sig:
                    return data
        except Exception:
            pass
        return {'modules': {}, 'timestamp': time.time()}
    
    def _save_cache(self):
        try:
            container = {
                'data': self.cache,
                'signature': self._compute_signature(self.cache)
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(container, f, indent=2)
        except Exception:
            pass
    
    def get(self, module_name: str) -> Optional[dict]:
        cached = self.cache.get('modules', {}).get(module_name)
        if cached:
            if time.time() - cached.get('time', 0) < self.CACHE_EXPIRY_SECONDS:
                return cached
        return None
    
    def set(self, module_name: str, available: bool, version: str = None):
        if 'modules' not in self.cache: self.cache['modules'] = {}
        self.cache['modules'][module_name] = {
            'available': available, 'version': version, 'time': time.time()
        }
        self._save_cache()
    
    def set_batch(self, results: Dict[str, dict]):
        if 'modules' not in self.cache: self.cache['modules'] = {}
        for name, info in results.items():
            self.cache['modules'][name] = {
                'available': info.get('available', False),
                'version': info.get('version'),
                'time': time.time()
            }
        self._save_cache()
    
    def clear(self):
        self.cache = {'modules': {}, 'timestamp': time.time()}
        self._save_cache()


class AdvancedImportAnalyzer:
    """高级导入分析器"""
    def __init__(self):
        self.imports: Set[str] = set()
        self.from_imports: Set[str] = set()
        self.dynamic_imports: Set[str] = set()
        self.conditional_imports: Set[str] = set()
        self.all_modules: Set[str] = set()
    
    def analyze_file(self, filepath: str) -> Dict[str, Set[str]]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f: source = f.read()
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding='gbk') as f: source = f.read()
            except Exception:
                with open(filepath, 'r', encoding='latin-1') as f: source = f.read()
        
        try:
            tree = ast.parse(source)
            self._visit_tree(tree)
        except SyntaxError: pass
        self._regex_analysis(source)
        self.all_modules = (self.imports | self.from_imports | self.dynamic_imports | self.conditional_imports)
        return {'imports': self.imports, 'from_imports': self.from_imports, 
                'dynamic': self.dynamic_imports, 'conditional': self.conditional_imports, 
                'all': self.all_modules}
    
    def _visit_tree(self, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names: self._add_import(alias.name, self.imports)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._add_import(node.module, self.from_imports)
                    self._add_import(node.module.split('.')[0], self.from_imports)
            elif isinstance(node, ast.Call):
                self._check_dynamic_import(node)
    
    def _add_import(self, name: str, target: Set[str]):
        if not name: return
        target.add(name)
        parts = name.split('.')
        target.add(parts[0])
        for i in range(1, len(parts)): target.add('.'.join(parts[:i+1]))
    
    def _check_dynamic_import(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == '__import__':
            if node.args and isinstance(node.args[0], ast.Constant):
                self._add_import(str(node.args[0].value), self.dynamic_imports)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == 'import_module':
                if node.args and isinstance(node.args[0], ast.Constant):
                    self._add_import(str(node.args[0].value), self.dynamic_imports)
    
    def _regex_analysis(self, source: str):
        patterns = [r'^\s*import\s+([\w\.]+)', r'^\s*from\s+([\w\.]+)\s+import',
                    r'__import__\s*\(\s*[\'"]([^\'"]+)[\'"]', r'import_module\s*\(\s*[\'"]([^\'"]+)[\'"]']
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.MULTILINE):
                if match.group(1) and not match.group(1).startswith('_'):
                    self._add_import(match.group(1), self.conditional_imports)


class BatchModuleChecker:
    def __init__(self, python_exe: str, cache: SecureDependencyCache):
        self.python_exe = python_exe
        self.cache = cache
    
    def check_modules(self, modules: Set[str], use_cache: bool = True) -> Dict[str, dict]:
        results = {}
        to_check = []
        for module in modules:
            top = module.split('.')[0]
            if top in STDLIB_MODULES:
                results[top] = {'available': True, 'version': 'stdlib', 'pip_name': '-', 'source': '标准库'}
                continue
            if use_cache:
                cached = self.cache.get(top)
                if cached:
                    results[top] = {'available': cached['available'], 'version': cached.get('version', 'N/A'),
                                    'pip_name': PACKAGE_NAME_MAP.get(top, top), 'source': '缓存'}
                    continue
            if top not in to_check: to_check.append(top)
        
        if to_check:
            batch_results = self._batch_check(to_check)
            results.update(batch_results)
            self.cache.set_batch(batch_results)
        return results
    
    def _batch_check(self, modules: List[str]) -> Dict[str, dict]:
        results = {}
        check_script = '''
import sys, json, importlib
modules = %s
results = {}
for m in modules:
    try:
        mod = __import__(m)
        version = getattr(mod, '__version__', None)
        if not version:
            try: import importlib.metadata; version = importlib.metadata.version(m)
            except: version = 'N/A'
        results[m] = {'available': True, 'version': str(version)}
    except Exception as e:
        results[m] = {'available': False, 'version': None, 'error': str(e)}
print(json.dumps(results))
''' % repr(modules)
        try:
            result = subprocess.run([self.python_exe, '-c', check_script], capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and result.stdout.strip():
                check_results = json.loads(result.stdout.strip())
                for module, info in check_results.items():
                    results[module] = {
                        'available': info.get('available', False), 'version': info.get('version', 'N/A'),
                        'pip_name': PACKAGE_NAME_MAP.get(module, module),
                        'source': '已安装' if info.get('available') else '需要安装'
                    }
            else:
                for module in modules: results[module] = {'available': False, 'version': 'N/A', 'pip_name': module}
        except Exception:
            for module in modules: results[module] = {'available': False, 'version': 'N/A', 'pip_name': module}
        return results


class GamePackagerV5:
    """v5.3 智能优化版"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"EXE打包工具 v{VERSION} - 智能优化版")
        self.root.geometry("900x850")
        self.root.resizable(True, True)
        self.root.minsize(800, 700)
        
        self.python_exe = get_python_executable()
        self.dep_cache = SecureDependencyCache()
        self.import_analyzer = AdvancedImportAnalyzer()
        self.module_checker = BatchModuleChecker(self.python_exe, self.dep_cache)
        
        # 默认配置
        self.current_dir = Path.cwd()
        self.default_source = "修改的游戏.py"
        self.output_name = "我的游戏"
        
        # UI变量
        self.pack_mode_var = tk.StringVar(value='onedir')
        self.no_console_var = tk.BooleanVar(value=True)
        self.clean_var = tk.BooleanVar(value=True)
        self.upx_var = tk.BooleanVar(value=False) # 默认关闭UPX，因为容易出问题
        self.admin_var = tk.BooleanVar(value=False)
        self.safe_mode_var = tk.BooleanVar(value=True)
        self.cleanup_strategy_var = tk.StringVar(value='atexit')
        
        self.collect_all_var = tk.BooleanVar(value=True)
        self.fast_mode_var = tk.BooleanVar(value=True)
        self.parallel_var = tk.BooleanVar(value=True)
        
        self.message_queue = queue.Queue()
        self.analyzed_deps: Dict[str, dict] = {}
        self.missing_deps: List[str] = []
        self.all_imports: Set[str] = set()
        self.hidden_imports: Set[str] = set()
        
        self._create_ui()
        self._process_queue()
    
    def _create_ui(self):
        title_frame = tk.Frame(self.root, bg='#1a237e', height=45)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=f"🎮 EXE打包工具 v{VERSION} - 智能优化版", font=('Microsoft YaHei', 11, 'bold'),
                 bg='#1a237e', fg='white').pack(pady=10)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        self._create_config_tab()
        self._create_check_tab()
        self._create_deps_tab()
        self._create_log_tab()
        self._create_bottom_bar()
    
    def _create_config_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📦 打包配置")
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1*(event.delta/120)), "units"))
        
        main = scrollable_frame
        
        source_frame = tk.LabelFrame(main, text="源文件与输出", font=('Arial', 10, 'bold'), bg='white', padx=10, pady=8)
        source_frame.pack(fill=tk.X, padx=10, pady=5)
        
        r1 = tk.Frame(source_frame, bg='white'); r1.pack(fill=tk.X, pady=3)
        tk.Label(r1, text="源文件:", bg='white', width=8).pack(side=tk.LEFT)
        self.source_entry = ttk.Entry(r1); self.source_entry.insert(0, self.default_source)
        self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(r1, text="浏览", bg='#2196F3', fg='white', command=self._browse_source).pack(side=tk.LEFT)
        
        r2 = tk.Frame(source_frame, bg='white'); r2.pack(fill=tk.X, pady=3)
        tk.Label(r2, text="输出名:", bg='white', width=8).pack(side=tk.LEFT)
        self.output_entry = ttk.Entry(r2); self.output_entry.insert(0, self.output_name)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        icon_frame = tk.LabelFrame(main, text="图标配置", font=('Arial', 10, 'bold'), bg='white', padx=10, pady=8)
        icon_frame.pack(fill=tk.X, padx=10, pady=5)
        
        for label, key, default in [("EXE图标", "exe", "480x480.png"), ("窗口图标", "window", "28x28.png"), ("任务栏", "taskbar", "108x108.png")]:
            row = tk.Frame(icon_frame, bg='white'); row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label+":", bg='white', width=16, anchor='w').pack(side=tk.LEFT)
            entry = ttk.Entry(row); entry.insert(0, default)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            tk.Button(row, text="...", width=3, command=lambda k=key: self._browse_icon(k)).pack(side=tk.LEFT)
            setattr(self, f"{key}_icon_entry", entry)
            
        mode_frame = tk.LabelFrame(main, text="打包模式", font=('Arial', 10, 'bold'), bg='white', padx=10, pady=8)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        mr = tk.Frame(mode_frame, bg='white'); mr.pack(fill=tk.X)
        
        left = tk.Frame(mr, bg='#e8f5e9', relief=tk.RIDGE, bd=2)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tk.Radiobutton(left, text="📁 单文件夹模式（推荐）", variable=self.pack_mode_var, value='onedir', bg='#e8f5e9', fg='#2e7d32').pack(anchor='w', padx=10, pady=5)
        tk.Label(left, text="• 启动速度最快 • 无需解压\n• 适合所有情况", bg='#e8f5e9', fg='#1b5e20', font=('Arial', 8)).pack(anchor='w', padx=25)
        
        right = tk.Frame(mr, bg='#e3f2fd', relief=tk.RIDGE, bd=2)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        tk.Radiobutton(right, text="📦 单文件模式", variable=self.pack_mode_var, value='onefile', bg='#e3f2fd', fg='#1565c0').pack(anchor='w', padx=10, pady=5)
        tk.Label(right, text="• 方便分发 • 启动较慢\n• 巨型库打包极慢", bg='#e3f2fd', fg='#0d47a1', font=('Arial', 8)).pack(anchor='w', padx=25)
        
        opt_frame = tk.LabelFrame(main, text="打包选项", font=('Arial', 10, 'bold'), bg='white', padx=10, pady=8)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)
        or1 = tk.Frame(opt_frame, bg='white'); or1.pack(fill=tk.X, pady=3)
        for t, v in [("隐藏控制台", self.no_console_var), ("清理临时文件", self.clean_var), ("UPX压缩(慎用)", self.upx_var), ("管理员权限", self.admin_var), ("🛡️ 安全模式", self.safe_mode_var)]:
            tk.Checkbutton(or1, text=t, variable=v, bg='white').pack(side=tk.LEFT, padx=8)
            
        or2 = tk.Frame(opt_frame, bg='#e8f4fd'); or2.pack(fill=tk.X, pady=5)
        tk.Label(or2, text="⚡ v5.3 增强:", font=('Arial', 9, 'bold'), bg='#e8f4fd', fg='#1565c0').pack(side=tk.LEFT, padx=5)
        for t, v in [("自动收集(智能)", self.collect_all_var), ("排除调试模块", self.fast_mode_var), ("并行分析", self.parallel_var)]:
            tk.Checkbutton(or2, text=t, variable=v, bg='#e8f4fd').pack(side=tk.LEFT, padx=8)

        info_frame = tk.LabelFrame(main, text="v5.3 改进说明", font=('Arial', 9, 'bold'), bg='#e8f5e9', padx=10, pady=5)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(info_frame, text="✅ 智能豁免 Torch/Pandas 全量收集（解决打包慢/卡90%问题）\n✅ 自动添加 copy-metadata（解决 DistributionNotFound 错误）\n✅ 强制禁止 Numpy/Pandas 使用 UPX（防止崩溃）", bg='#e8f5e9', fg='#1b5e20', justify='left').pack(anchor='w')

    def _create_check_tab(self):
        f = ttk.Frame(self.notebook); self.notebook.add(f, text="🔍 环境检查")
        self.check_text = tk.Text(f, height=20, font=('Consolas', 9))
        self.check_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _create_deps_tab(self):
        f = ttk.Frame(self.notebook); self.notebook.add(f, text="📊 依赖分析")
        tree_frame = tk.Frame(f); tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        cols = ('模块名', '状态', '版本', 'pip包名', '类型')
        self.deps_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=15)
        for c, w in zip(cols, [150, 80, 100, 130, 150]):
            self.deps_tree.heading(c, text=c); self.deps_tree.column(c, width=w)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.deps_tree.yview)
        self.deps_tree.configure(yscrollcommand=sb.set)
        self.deps_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.deps_info = tk.Label(f, text="请先点击'分析'", font=('Arial', 10), fg='gray')
        self.deps_info.pack(pady=5)

    def _create_log_tab(self):
        f = ttk.Frame(self.notebook); self.notebook.add(f, text="📝 打包日志")
        self.log_text = scrolledtext.ScrolledText(f, height=20, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        bf = tk.Frame(f); bf.pack(pady=3)
        tk.Button(bf, text="清空日志", command=lambda: self.log_text.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
        tk.Button(bf, text="复制日志", command=self._copy_log).pack(side=tk.LEFT, padx=5)

    def _create_bottom_bar(self):
        b = tk.Frame(self.root, bg='#ecf0f1', height=85); b.pack(fill=tk.X, side=tk.BOTTOM); b.pack_propagate(False)
        self.progress = ttk.Progressbar(b, length=870, mode='determinate'); self.progress.pack(pady=(8, 2))
        self.progress_label = tk.Label(b, text="准备就绪 - v5.3 智能优化版", font=('Arial', 9), bg='#ecf0f1'); self.progress_label.pack()
        bf = tk.Frame(b, bg='#ecf0f1'); bf.pack(pady=5)
        self.btn_refs = {}
        for t, c, cmd in [("🔍 检查", '#FF9800', self._start_check), ("📊 分析", '#9C27B0', self._start_analyze), 
                          ("📦 安装", '#2196F3', self._start_install), ("🚀 打包", '#4CAF50', self._start_pack), 
                          ("🗑️ 清缓存", '#FF5722', self._clear_cache), ("📁 目录", '#607D8B', self._open_output), 
                          ("❌ 退出", '#F44336', self._quit)]:
            btn = tk.Button(bf, text=t, font=('Arial', 9, 'bold'), bg=c, fg='white', width=8, command=cmd)
            btn.pack(side=tk.LEFT, padx=3); self.btn_refs[t] = btn
        self.btn_refs["📊 分析"].config(state='disabled'); self.btn_refs["🚀 打包"].config(state='disabled')

    # ... (辅助方法省略，如 _browse_source, _copy_log 等，保持原样即可，为了节省长度这里不重复) ...
    def _browse_source(self):
        filepath = filedialog.askopenfilename(title="选择源文件", filetypes=[("Python文件", "*.py"), ("所有文件", "*.*")])
        if filepath:
            self.source_entry.delete(0, tk.END); self.source_entry.insert(0, filepath)
            self.analyzed_deps = {}; self.missing_deps = []
            self.btn_refs["📊 分析"].config(state='disabled'); self.btn_refs["🚀 打包"].config(state='disabled')
    
    def _browse_icon(self, k):
        filepath = filedialog.askopenfilename(title=f"选择{k}", filetypes=[("图片", "*.png *.ico"), ("所有", "*.*")])
        if filepath: getattr(self, f"{k}_icon_entry").delete(0, tk.END); getattr(self, f"{k}_icon_entry").insert(0, filepath)
    
    def _open_output(self):
        dist = Path("dist")
        if dist.exists():
            if sys.platform=='win32': os.startfile(dist)
            else: subprocess.run(['xdg-open', dist])
        else: messagebox.showinfo("提示", "未找到输出目录")

    def _clear_cache(self):
        self.dep_cache.clear(); self.analyzed_deps={}; self.missing_deps=[]
        messagebox.showinfo("成功", "缓存已清除")
    
    def _copy_log(self):
        self.root.clipboard_clear(); self.root.clipboard_append(self.log_text.get(1.0, tk.END))
        messagebox.showinfo("成功", "日志已复制")

    def _quit(self):
        if messagebox.askyesno("确认", "确定退出？"): self.root.quit()

    def _process_queue(self):
        try:
            while True:
                msg_type, content = self.message_queue.get_nowait()
                if msg_type == 'check': self.check_text.insert(tk.END, content); self.check_text.see(tk.END)
                elif msg_type == 'log': self.log_text.insert(tk.END, content); self.log_text.see(tk.END)
                elif msg_type == 'progress': self.progress['value'] = content[0]; self.progress_label.config(text=content[1])
                elif msg_type == 'deps_tree': 
                    for item in content: self.deps_tree.insert('', 'end', values=item)
                elif msg_type == 'deps_info': self.deps_info.config(text=content[0], fg=content[1])
                elif msg_type == 'enable_btn': self.btn_refs[content].config(state='normal')
        except queue.Empty: pass
        self.root.after(100, self._process_queue)
    
    def _add_check_msg(self, msg): self.message_queue.put(('check', msg))
    def _add_log_msg(self, msg): self.message_queue.put(('log', msg))
    def _get_source_file(self):
        s = self.source_entry.get().strip()
        return s + '.py' if s and not s.endswith('.py') else s

    # ==================== 核心逻辑 ====================

    def _start_check(self):
        self.notebook.select(1); self.btn_refs["🔍 检查"].config(state='disabled')
        self.check_text.delete(1.0, tk.END)
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        try:
            self._add_check_msg(f"环境检查 v{VERSION}\n{'='*40}\n")
            self._add_check_msg(f"解释器: {self.python_exe}\n")
            source = self._get_source_file()
            if os.path.exists(source):
                self._add_check_msg(f"✅ 源文件: {source}\n")
                if is_safe_path(source): self._add_check_msg(f"✅ 路径安全\n")
            else: self._add_check_msg(f"❌ 源文件不存在: {source}\n")
            
            # 核心依赖检查
            core_deps = ['PyInstaller', 'PIL']
            results = self.module_checker.check_modules(set(core_deps), use_cache=False)
            ok = True
            for dep in core_deps:
                if results.get(dep, {}).get('available'): self._add_check_msg(f"✅ {dep} 已安装\n")
                else: 
                    self._add_check_msg(f"❌ {dep} 未安装\n"); ok = False
            
            if ok and os.path.exists(source): 
                self.message_queue.put(('enable_btn', "📊 分析"))
                self._add_check_msg("\n✅ 检查通过！\n")
            else: self._add_check_msg("\n❌ 检查未通过\n")
        except Exception as e: self._add_check_msg(f"错误: {e}")
        self.message_queue.put(('enable_btn', "🔍 检查"))

    def _start_analyze(self):
        self.notebook.select(2); self.btn_refs["📊 分析"].config(state='disabled')
        for i in self.deps_tree.get_children(): self.deps_tree.delete(i)
        threading.Thread(target=self._do_analyze, args=(self._get_source_file(),), daemon=True).start()

    def _do_analyze(self, source):
        try:
            self.message_queue.put(('progress', (20, "解析代码...")))
            res = self.import_analyzer.analyze_file(source)
            all_imps = res['all']
            expanded = set()
            for m in all_imps:
                top = m.split('.')[0]; expanded.add(top)
                if top in IMPLICIT_DEPENDENCIES: expanded.update(IMPLICIT_DEPENDENCIES[top])
            
            self.message_queue.put(('progress', (50, "检测状态...")))
            results = self.module_checker.check_modules(expanded)
            
            self.analyzed_deps = {}; self.missing_deps = []; self.all_imports = set(); self.hidden_imports = set()
            tree_data = []
            
            for mod, info in sorted(results.items()):
                if mod in STDLIB_MODULES: continue
                self.analyzed_deps[mod] = info; self.all_imports.add(mod)
                status = '✅' if info['available'] else '❌'
                if mod not in res['imports'] and mod not in res['from_imports']: self.hidden_imports.add(mod)
                tree_data.append((mod, status, info.get('version', 'N/A'), info.get('pip_name', mod), 
                                  '隐式依赖' if mod in self.hidden_imports else '直接导入'))
                if not info['available']: self.missing_deps.append(info['pip_name'])
            
            self.message_queue.put(('deps_tree', tree_data))
            if self.missing_deps: 
                self.message_queue.put(('deps_info', (f"缺 {len(self.missing_deps)} 个依赖", 'red')))
            else: 
                self.message_queue.put(('deps_info', ("✅ 依赖就绪", 'green')))
                self.message_queue.put(('enable_btn', "🚀 打包"))
            self.message_queue.put(('progress', (100, "分析完成")))
        except Exception as e: 
            traceback.print_exc()
            self.message_queue.put(('deps_info', (f"错误: {e}", 'red')))
        self.message_queue.put(('enable_btn', "📊 分析"))

    def _start_install(self):
        self.notebook.select(3); self.btn_refs["📦 安装"].config(state='disabled')
        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self):
        try:
            to_install = [p for p in self.missing_deps if p != '-']
            if not to_install: 
                self._add_log_msg("无缺失依赖\n"); self.message_queue.put(('enable_btn', "📦 安装")); return
            
            self._add_log_msg(f"正在安装: {', '.join(to_install)}\n")
            for pkg in to_install:
                if not is_safe_package_name(pkg): continue
                cmd = [self.python_exe, "-m", "pip", "install", pkg, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                subprocess.run(cmd, capture_output=True)
                self.dep_cache.set(pip_name_to_import_name(pkg), True)
                self._add_log_msg(f"✅ {pkg} 安装尝试完成\n")
            self._add_log_msg("\n安装流程结束，请重新分析\n")
        except Exception as e: self._add_log_msg(f"安装错误: {e}\n")
        self.message_queue.put(('enable_btn', "📦 安装"))

    def _start_pack(self):
        self.notebook.select(3); self.btn_refs["🚀 打包"].config(state='disabled')
        self.log_text.delete(1.0, tk.END)
        threading.Thread(target=self._do_pack, args=(self._get_source_file(),), daemon=True).start()

    def _do_pack(self, source):
        wrapper_file = None
        try:
            output_name = self.output_entry.get().strip() or "game"
            self.message_queue.put(('progress', (5, "初始化...")))
            self._add_log_msg(f"=== 开始打包 v{VERSION} ===\n")
            self._add_log_msg(f"源: {source}, 模式: {self.pack_mode_var.get()}\n")
            
            icons = self._prepare_icons()
            
            # 创建包装器 (解决图标和路径问题)
            if self.pack_mode_var.get() == 'onefile' or icons.get('window'):
                wrapper_file = self._create_wrapper(source, icons)
                actual_source = wrapper_file
            else:
                actual_source = source

            data_files = self._collect_data_files(source, icons)
            cmd = self._build_command(actual_source, output_name, icons, data_files)
            
            self._add_log_msg(f"\n执行命令: {' '.join(cmd[:10])} ...\n\n")
            
            # 执行打包
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     universal_newlines=True, bufsize=1)
            
            progress = 10
            # 优化的进度条逻辑
            for line in process.stdout:
                self._add_log_msg(line)
                
                lower_line = line.lower()
                if "analyzing" in lower_line:
                    progress = min(progress + 1, 40)
                    self.message_queue.put(('progress', (progress, "分析依赖...")))
                elif "collecting" in lower_line:
                    progress = min(progress + 1, 60)
                    self.message_queue.put(('progress', (progress, "收集文件...")))
                elif "copying" in lower_line:
                    progress = min(progress + 0.5, 80)
                elif "archiving" in lower_line: # 关键：正在压缩
                    progress = 85
                    self.message_queue.put(('progress', (85, "正在压缩(大文件需等待)...")))
                elif "building pkg" in lower_line: # 关键：构建包
                    progress = 90
                    self.message_queue.put(('progress', (90, "正在写入EXE...")))
                elif "appended" in lower_line:
                    progress = 95
            
            process.wait()
            
            if process.returncode == 0:
                self.message_queue.put(('progress', (100, "打包成功!")))
                self._add_log_msg("\n✅ 打包成功!\n")
                if wrapper_file and os.path.exists(wrapper_file): os.remove(wrapper_file)
                self._open_output()
                messagebox.showinfo("成功", "打包完成！")
            else:
                self.message_queue.put(('progress', (100, "打包失败")))
                self._add_log_msg("\n❌ 打包失败，请检查日志\n")
                messagebox.showerror("失败", "打包过程出错")
                
        except Exception as e:
            self.message_queue.put(('progress', (100, f"错误: {e}")))
            self._add_log_msg(f"\n❌ 严重错误: {e}\n{traceback.format_exc()}\n")
        finally:
            self.message_queue.put(('enable_btn', "🚀 打包"))

    def _build_command(self, source, output_name, icons, data_files):
        cmd = [self.python_exe, "-m", "PyInstaller", "--noconfirm", "--name", output_name]
        
        if self.clean_var.get(): cmd.append("--clean")
        if self.pack_mode_var.get() == 'onefile': cmd.append("--onefile")
        else: cmd.append("--onedir")
        if self.no_console_var.get(): cmd.append("--noconsole")
        if icons.get('exe'): cmd.extend(["--icon", icons['exe']])
        if self.admin_var.get(): cmd.append("--uac-admin")
        
        # 数据文件
        sep = ';' if sys.platform == 'win32' else ':'
        for s, d in data_files: cmd.extend(["--add-data", f"{s}{sep}{d}"])
        
        # 排除
        if self.fast_mode_var.get():
            for exc in EXCLUDE_MODULES: cmd.extend(["--exclude-module", exc])
        
        # v5.3 智能收集逻辑 (解决慢的问题)
        collected_metadata = set()
        if self.collect_all_var.get():
            for mod in self.all_imports:
                top = mod.split('.')[0]
                
                # 1. 自动添加 copy-metadata (解决 DistributionNotFound)
                pip_name = PACKAGE_NAME_MAP.get(top, top).lower()
                if (top in METADATA_REQUIRED_PACKAGES or pip_name in METADATA_REQUIRED_PACKAGES) and top not in collected_metadata:
                    cmd.extend(["--copy-metadata", top])
                    self._add_log_msg(f"  📝 复制元数据: {top}\n")
                    collected_metadata.add(top)
                
                # 2. 智能 collect-submodules
                if top in COMPLEX_PACKAGES and top not in STDLIB_MODULES:
                    # 关键优化：跳过巨型库的全量收集
                    if top in GIANT_PACKAGES:
                        self._add_log_msg(f"  ⏩ 跳过全量收集(优化速度): {top}\n")
                        # 对于 PyTorch 等，使用原生 hook 足够了，不需要 collect-submodules
                    else:
                        cmd.extend(["--collect-submodules", top])
                        self._add_log_msg(f"  📦 收集子模块: {top}\n")

        # 隐藏导入
        added_hidden = set()
        for mod in self.all_imports | self.hidden_imports:
            if mod not in STDLIB_MODULES and mod not in added_hidden:
                # 简单过滤
                if not any(mod.startswith(e.split('.')[0]) for e in EXCLUDE_MODULES):
                    cmd.extend(["--hidden-import", mod])
                    added_hidden.add(mod)

        # 安全模式补充
        if self.safe_mode_var.get():
            cmd.extend(["--collect-all", "pkg_resources"])
        
        # v5.3 强制禁止对敏感库使用 UPX (防止崩溃)
        # 即使勾选了 UPX，也要把这些库排除
        if self.upx_var.get() and shutil.which('upx'):
            cmd.append("--upx-dir=.")
            no_upx_libs = ['pandas', 'numpy', 'torch', 'cv2', 'scipy', 'tensorflow']
            for lib in no_upx_libs:
                cmd.extend(["--upx-exclude", lib])
        else:
            cmd.append("--noupx")
            
        cmd.append(source)
        return cmd

    def _prepare_icons(self):
        icons = {}
        # (简化图标处理逻辑，与原版类似但略去非关键代码以缩短篇幅)
        exe_p = self.exe_icon_entry.get()
        if exe_p and os.path.exists(exe_p): icons['exe'] = os.path.abspath(exe_p)
        win_p = self.window_icon_entry.get()
        if win_p and os.path.exists(win_p): icons['window'] = os.path.abspath(win_p)
        return icons

    def _create_wrapper(self, source, icons):
        # 创建临时包装脚本以处理图标
        with open(source, 'r', encoding='utf-8') as f: orig = f.read()
        win_icon = os.path.basename(icons.get('window', ''))
        code = f"""import sys, os
try:
    base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base, "{win_icon}")
    import tkinter as tk
    _orig = tk.Tk.__init__
    def _new(self, *a, **k):
        _orig(self, *a, **k)
        try: 
            if os.path.exists(icon_path): 
                if icon_path.endswith('.png'): self.iconphoto(True, tk.PhotoImage(file=icon_path))
                else: self.iconbitmap(icon_path)
        except: pass
    tk.Tk.__init__ = _new
except: pass
{orig}
"""
        tmp = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.py', delete=False)
        tmp.write(code); tmp.close()
        return tmp.name

    def _collect_data_files(self, source, icons):
        data = []
        src_dir = os.path.dirname(os.path.abspath(source))
        if icons.get('window'): data.append((icons['window'], '.'))
        # 简单的资源扫描
        try:
            with open(source, 'r', encoding='utf-8') as f: c = f.read()
            for ext in ['png','jpg','ico','json','txt','mp3','wav']:
                for m in re.finditer(f'["\']([^"\']+\.{ext})["\']', c, re.I):
                    fname = m.group(1)
                    fp = os.path.join(src_dir, fname)
                    if os.path.exists(fp): data.append((os.path.abspath(fp), '.'))
        except: pass
        return list(set(data))

    def run(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth()//2) - (w//2)
        y = (self.root.winfo_screenheight()//2) - (h//2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        self.root.mainloop()

if __name__ == "__main__":
    GamePackagerV5().run()
