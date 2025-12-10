#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键打包游戏工具 v5.2 缓存增强版
修复内容：
1. v5.1: 修复 pyinstaller 检测失败问题（导入名大小写）
2. v5.1: 修复安装后缓存更新逻辑
3. v5.1: 添加 pip包名 -> 导入名 的反向映射
4. v5.2: 缓存有效期延长至 7 天（解决重复检测问题）
5. v5.2: 缓存文件固定在用户目录（换目录不丢失）
6. v5.2: 添加 torch 等更多库的映射

基于 v5.0 完全重构版
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

VERSION = "5.2"

# 完整的Python标准库列表（Python 3.8-3.12）
STDLIB_MODULES = frozenset({
    # 内置模块
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
    # 私有模块
    '_abc', '_asyncio', '_bisect', '_blake2', '_bootlocale', '_bz2', '_codecs',
    '_collections', '_collections_abc', '_compat_pickle', '_compression',
    '_contextvars', '_crypt', '_csv', '_ctypes', '_curses', '_datetime',
    '_decimal', '_elementtree', '_functools', '_hashlib', '_heapq', '_imp',
    '_io', '_json', '_locale', '_lsprof', '_lzma', '_markupbase', '_md5',
    '_multibytecodec', '_multiprocessing', '_opcode', '_operator', '_osx_support',
    '_pickle', '_posixshmem', '_posixsubprocess', '_py_abc', '_pydecimal',
    '_pyio', '_queue', '_random', '_sha1', '_sha256', '_sha3', '_sha512',
    '_signal', '_sitebuiltins', '_socket', '_sqlite3', '_sre', '_ssl', '_stat',
    '_statistics', '_string', '_strptime', '_struct', '_symtable', '_thread',
    '_threading_local', '_tkinter', '_tracemalloc', '_uuid', '_warnings',
    '_weakref', '_weakrefset', '_winapi', '_xxsubinterpreters', '_xxtestfuzz',
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
    # v5.1 修复：添加 PyInstaller
    'PyInstaller': 'pyinstaller',
    # v5.2: 添加更多
    'torch': 'torch',
    'torchvision': 'torchvision',
    'torchaudio': 'torchaudio',
    'tensorflow': 'tensorflow',
    'keras': 'keras',
}

# v5.1 新增：pip包名 -> 导入名 的反向映射
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
    # v5.2: 添加更多常见库
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

# 需要 collect-submodules 的复杂库
COMPLEX_PACKAGES = {
    'pygame', 'PIL', 'numpy', 'scipy', 'matplotlib', 'pandas', 'sklearn',
    'cv2', 'tensorflow', 'torch', 'keras', 'PyQt5', 'PyQt6', 'PySide2',
    'PySide6', 'wx', 'kivy', 'pyglet', 'arcade', 'panda3d', 'moderngl',
}

# 库的隐式依赖映射
IMPLICIT_DEPENDENCIES = {
    'PIL': ['PIL._imaging', 'PIL._imagingft', 'PIL._imagingmath', 'PIL._imagingtk'],
    'numpy': ['numpy.core._multiarray_umath', 'numpy.core._dtype_ctypes', 
              'numpy.random._common', 'numpy.random._bounded_integers',
              'numpy.random._mt19937', 'numpy.random._philox', 'numpy.random._pcg64',
              'numpy.random._sfc64', 'numpy.random._generator', 'numpy.random.mtrand'],
    'pygame': ['pygame._sdl2', 'pygame.base', 'pygame.constants', 'pygame.rect',
               'pygame.rwobject', 'pygame.surflock', 'pygame.color', 'pygame.bufferproxy',
               'pygame.math', 'pygame.pkgdata', 'pygame.mixer', 'pygame.mixer_music',
               'pygame.font', 'pygame.freetype', 'pygame.image', 'pygame.transform',
               'pygame.display', 'pygame.event', 'pygame.key', 'pygame.mouse'],
    'matplotlib': ['matplotlib.backends.backend_tkagg', 'matplotlib.backends.backend_agg',
                   'matplotlib._path', 'matplotlib._image', 'matplotlib.ft2font',
                   'matplotlib._contour', 'matplotlib._qhull', 'matplotlib._tri',
                   'matplotlib._c_internal_utils'],
    'scipy': ['scipy.special._ufuncs', 'scipy.special._comb', 'scipy.linalg._fblas',
              'scipy.linalg._flapack', 'scipy.sparse._sparsetools', 
              'scipy.spatial._ckdtree', 'scipy.spatial._qhull'],
    'pandas': ['pandas._libs.tslibs.base', 'pandas._libs.tslibs.np_datetime',
               'pandas._libs.tslibs.nattype', 'pandas._libs.tslibs.timedeltas',
               'pandas._libs.tslibs.timestamps', 'pandas._libs.hashtable',
               'pandas._libs.lib', 'pandas._libs.missing', 'pandas._libs.parsers'],
    'sklearn': ['sklearn.utils._cython_blas', 'sklearn.neighbors._typedefs',
                'sklearn.neighbors._quad_tree', 'sklearn.tree._utils',
                'sklearn.utils._weight_vector'],
    'requests': ['urllib3', 'certifi', 'charset_normalizer', 'idna'],
    'aiohttp': ['aiohttp._http_parser', 'aiohttp._http_writer', 'aiohttp._websocket',
                'multidict', 'yarl', 'async_timeout', 'frozenlist', 'aiosignal'],
    'cv2': ['cv2.data', 'numpy'],
    'tkinter': ['tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
                'tkinter.scrolledtext', 'tkinter.font', 'tkinter.colorchooser',
                'tkinter.simpledialog', 'tkinter.dnd'],
}

# 打包时应排除的模块
EXCLUDE_MODULES = [
    'numpy.array_api',
    'numpy.distutils', 
    'numpy.f2py',
    'numpy.testing',
    'numpy.tests',
    'scipy.spatial.cKDTree',
    'matplotlib.tests',
    'matplotlib.testing',
    'IPython',
    'jupyter',
    'jupyter_client',
    'jupyter_core',
    'notebook',
    'pytest',
    'pytest_cov',
    'sphinx',
    'setuptools',
    'pip',
    'wheel',
    'twine',
    'black',
    'flake8',
    'pylint',
    'mypy',
    'isort',
    'autopep8',
    'yapf',
    'coverage',
    'tox',
    'nox',
    'virtualenv',
    'pyinstaller',  # 不要把打包工具自己打进去
]

# 安全：允许的pip包名字符
SAFE_PACKAGE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')


def get_python_executable() -> str:
    """获取实际的Python解释器路径（增强版）"""
    if getattr(sys, 'frozen', False):
        possible_paths = [
            shutil.which('python'),
            shutil.which('python3'),
            shutil.which('py'),
        ]
        
        # Windows 常见路径
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
        
        # 尝试 py launcher
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
    """验证包名是否安全（防止命令注入）"""
    if not name or len(name) > 100:
        return False
    return bool(SAFE_PACKAGE_NAME_PATTERN.match(name))


def is_safe_path(path: str, base_dir: Optional[str] = None) -> bool:
    """验证路径是否安全（防止路径遍历）"""
    try:
        # 规范化路径
        abs_path = os.path.abspath(path)
        
        # 检查是否包含危险模式
        dangerous_patterns = ['..', '~', '$', '%', '`', '|', ';', '&', '<', '>']
        for pattern in dangerous_patterns:
            if pattern in path:
                return False
        
        # 如果指定了基础目录，确保路径在其内
        if base_dir:
            base_abs = os.path.abspath(base_dir)
            if not abs_path.startswith(base_abs):
                return False
        
        return True
    except Exception:
        return False


def pip_name_to_import_name(pip_name: str) -> str:
    """v5.1: 将 pip 包名转换为 Python 导入名"""
    # 先查找映射表
    if pip_name in PIP_TO_IMPORT_MAP:
        return PIP_TO_IMPORT_MAP[pip_name]
    
    # 尝试小写查找
    lower_name = pip_name.lower()
    if lower_name in PIP_TO_IMPORT_MAP:
        return PIP_TO_IMPORT_MAP[lower_name]
    
    # 默认转换规则：小写，将 - 替换为 _
    return pip_name.lower().replace('-', '_')


def import_name_to_pip_name(import_name: str) -> str:
    """将 Python 导入名转换为 pip 包名"""
    if import_name in PACKAGE_NAME_MAP:
        return PACKAGE_NAME_MAP[import_name]
    return import_name


class SecureDependencyCache:
    """v5.2：带签名验证的安全缓存（修复版）"""
    
    # v5.2: 缓存有效期延长到 7 天
    CACHE_EXPIRY_SECONDS = 7 * 24 * 3600  # 7天
    
    def __init__(self, cache_file: str = None):
        # v5.2: 缓存文件放到用户目录，避免换目录丢失
        if cache_file is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".game_packer_cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "dep_cache_v5.json")
        self.cache_file = cache_file
        self.secret_key = self._get_machine_key()
        self.cache = self._load_cache()
    
    def _get_machine_key(self) -> str:
        """生成机器相关的密钥"""
        import platform
        try:
            login = os.getlogin()
        except:
            login = 'user'
        machine_info = f"{platform.node()}-{platform.machine()}-{login}"
        return hashlib.sha256(machine_info.encode()).hexdigest()[:32]
    
    def _compute_signature(self, data: dict) -> str:
        """计算数据签名"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256((data_str + self.secret_key).encode()).hexdigest()
    
    def _load_cache(self) -> dict:
        """加载并验证缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    container = json.load(f)
                
                data = container.get('data', {})
                stored_sig = container.get('signature', '')
                
                # 验证签名
                if self._compute_signature(data) == stored_sig:
                    return data
                else:
                    print("[警告] 缓存签名验证失败，已重置")
        except Exception as e:
            print(f"[警告] 加载缓存失败: {e}")
        
        return {'modules': {}, 'timestamp': time.time()}
    
    def _save_cache(self):
        """保存带签名的缓存"""
        try:
            container = {
                'data': self.cache,
                'signature': self._compute_signature(self.cache)
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(container, f, indent=2)
        except Exception as e:
            print(f"[警告] 保存缓存失败: {e}")
    
    def get(self, module_name: str) -> Optional[dict]:
        """获取缓存的模块状态"""
        cached = self.cache.get('modules', {}).get(module_name)
        if cached:
            # v5.2: 使用类常量定义的过期时间（7天）
            if time.time() - cached.get('time', 0) < self.CACHE_EXPIRY_SECONDS:
                return cached
        return None
    
    def set(self, module_name: str, available: bool, version: str = None):
        """设置模块缓存"""
        if 'modules' not in self.cache:
            self.cache['modules'] = {}
        self.cache['modules'][module_name] = {
            'available': available,
            'version': version,
            'time': time.time()
        }
        self._save_cache()
    
    def set_batch(self, results: Dict[str, dict]):
        """批量设置缓存"""
        if 'modules' not in self.cache:
            self.cache['modules'] = {}
        for name, info in results.items():
            self.cache['modules'][name] = {
                'available': info.get('available', False),
                'version': info.get('version'),
                'time': time.time()
            }
        self._save_cache()
    
    def clear(self):
        """清除缓存"""
        self.cache = {'modules': {}, 'timestamp': time.time()}
        self._save_cache()


class AdvancedImportAnalyzer:
    """v5.0：高级导入分析器"""
    
    def __init__(self):
        self.imports: Set[str] = set()
        self.from_imports: Set[str] = set()
        self.dynamic_imports: Set[str] = set()
        self.conditional_imports: Set[str] = set()
        self.all_modules: Set[str] = set()
    
    def analyze_file(self, filepath: str) -> Dict[str, Set[str]]:
        """分析文件中的所有导入"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding='gbk') as f:
                    source = f.read()
            except Exception:
                with open(filepath, 'r', encoding='latin-1') as f:
                    source = f.read()
        
        # AST 解析
        try:
            tree = ast.parse(source)
            self._visit_tree(tree)
        except SyntaxError as e:
            print(f"[警告] 语法错误: {e}")
        
        # 正则表达式补充检测
        self._regex_analysis(source)
        
        # 合并所有导入
        self.all_modules = (
            self.imports | self.from_imports | 
            self.dynamic_imports | self.conditional_imports
        )
        
        return {
            'imports': self.imports.copy(),
            'from_imports': self.from_imports.copy(),
            'dynamic': self.dynamic_imports.copy(),
            'conditional': self.conditional_imports.copy(),
            'all': self.all_modules.copy()
        }
    
    def _visit_tree(self, tree: ast.AST):
        """遍历AST树"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._add_import(alias.name, self.imports)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._add_import(node.module, self.from_imports)
                    # 也添加顶层模块
                    top = node.module.split('.')[0]
                    self._add_import(top, self.from_imports)
            
            elif isinstance(node, ast.Call):
                self._check_dynamic_import(node)
    
    def _add_import(self, name: str, target: Set[str]):
        """添加导入（处理子模块）"""
        if not name:
            return
        
        # 添加完整模块名
        target.add(name)
        
        # 添加顶层模块
        parts = name.split('.')
        target.add(parts[0])
        
        # 添加所有中间层级
        for i in range(1, len(parts)):
            target.add('.'.join(parts[:i+1]))
    
    def _check_dynamic_import(self, node: ast.Call):
        """检测动态导入"""
        # __import__('xxx')
        if isinstance(node.func, ast.Name) and node.func.id == '__import__':
            if node.args and isinstance(node.args[0], ast.Constant):
                self._add_import(str(node.args[0].value), self.dynamic_imports)
        
        # importlib.import_module('xxx')
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == 'import_module':
                if node.args and isinstance(node.args[0], ast.Constant):
                    self._add_import(str(node.args[0].value), self.dynamic_imports)
    
    def _regex_analysis(self, source: str):
        """正则表达式补充分析"""
        patterns = [
            # import xxx
            r'^\s*import\s+([\w\.]+)',
            # from xxx import
            r'^\s*from\s+([\w\.]+)\s+import',
            # __import__('xxx')
            r'__import__\s*\(\s*[\'"]([^\'"]+)[\'"]',
            # importlib.import_module('xxx')
            r'import_module\s*\(\s*[\'"]([^\'"]+)[\'"]',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.MULTILINE):
                module = match.group(1)
                if module and not module.startswith('_'):
                    self._add_import(module, self.conditional_imports)


class BatchModuleChecker:
    """v5.1：批量模块检测器（修复版）"""
    
    def __init__(self, python_exe: str, cache: SecureDependencyCache):
        self.python_exe = python_exe
        self.cache = cache
    
    def check_modules(self, modules: Set[str], use_cache: bool = True) -> Dict[str, dict]:
        """批量检测模块可用性"""
        results = {}
        to_check = []
        
        # 先检查缓存
        for module in modules:
            top = module.split('.')[0]
            
            # 标准库直接标记
            if top in STDLIB_MODULES:
                results[top] = {
                    'available': True,
                    'version': 'stdlib',
                    'pip_name': '-',
                    'source': '标准库'
                }
                continue
            
            # 检查缓存
            if use_cache:
                cached = self.cache.get(top)
                if cached:
                    results[top] = {
                        'available': cached['available'],
                        'version': cached.get('version', 'N/A'),
                        'pip_name': PACKAGE_NAME_MAP.get(top, top),
                        'source': '缓存'
                    }
                    continue
            
            # 需要实际检测
            if top not in to_check:
                to_check.append(top)
        
        # 批量检测
        if to_check:
            batch_results = self._batch_check(to_check)
            results.update(batch_results)
            
            # 更新缓存
            self.cache.set_batch(batch_results)
        
        return results
    
    def _batch_check(self, modules: List[str]) -> Dict[str, dict]:
        """实际批量检测（一次子进程调用检测所有模块）"""
        results = {}
        
        # 构建批量检测脚本
        check_script = '''
import sys
import json

modules = %s
results = {}

for m in modules:
    try:
        mod = __import__(m)
        version = getattr(mod, '__version__', None)
        if not version:
            try:
                import importlib.metadata
                version = importlib.metadata.version(m)
            except:
                version = 'N/A'
        results[m] = {'available': True, 'version': str(version)}
    except Exception as e:
        results[m] = {'available': False, 'version': None, 'error': str(e)}

print(json.dumps(results))
''' % repr(modules)
        
        try:
            result = subprocess.run(
                [self.python_exe, '-c', check_script],
                capture_output=True,
                text=True,
                timeout=60  # 整体超时60秒
            )
            
            if result.returncode == 0 and result.stdout.strip():
                check_results = json.loads(result.stdout.strip())
                
                for module, info in check_results.items():
                    pip_name = PACKAGE_NAME_MAP.get(module, module)
                    results[module] = {
                        'available': info.get('available', False),
                        'version': info.get('version', 'N/A'),
                        'pip_name': pip_name,
                        'source': '已安装' if info.get('available') else '需要安装'
                    }
            else:
                # 失败时标记所有模块为未知
                for module in modules:
                    pip_name = PACKAGE_NAME_MAP.get(module, module)
                    results[module] = {
                        'available': False,
                        'version': 'N/A',
                        'pip_name': pip_name,
                        'source': '检测失败'
                    }
        
        except subprocess.TimeoutExpired:
            for module in modules:
                results[module] = {
                    'available': False,
                    'version': 'N/A',
                    'pip_name': PACKAGE_NAME_MAP.get(module, module),
                    'source': '检测超时'
                }
        except Exception as e:
            for module in modules:
                results[module] = {
                    'available': False,
                    'version': 'N/A',
                    'pip_name': PACKAGE_NAME_MAP.get(module, module),
                    'source': f'错误: {str(e)[:30]}'
                }
        
        return results


class GamePackagerV5:
    """v5.1 修复版打包工具"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"别快EXE打包工具 v{VERSION} - 缓存增强版")
        self.root.geometry("900x850")
        self.root.resizable(True, True)
        self.root.minsize(800, 700)
        
        # 核心组件
        self.python_exe = get_python_executable()
        self.dep_cache = SecureDependencyCache()
        self.import_analyzer = AdvancedImportAnalyzer()
        self.module_checker = BatchModuleChecker(self.python_exe, self.dep_cache)
        
        # 设置图标
        try:
            if os.path.exists("28x28.png"):
                self.root.iconphoto(True, tk.PhotoImage(file="28x28.png"))
        except Exception:
            pass
        
        # 默认配置
        self.current_dir = Path.cwd()
        self.default_source = "修改的游戏.py"
        self.output_name = "记事本与网址导航游戏"
        
        # UI变量
        self.pack_mode_var = tk.StringVar(value='onedir')  # 默认文件夹模式
        self.no_console_var = tk.BooleanVar(value=True)
        self.clean_var = tk.BooleanVar(value=True)
        self.upx_var = tk.BooleanVar(value=False)
        self.admin_var = tk.BooleanVar(value=False)
        self.safe_mode_var = tk.BooleanVar(value=True)
        self.cleanup_strategy_var = tk.StringVar(value='atexit')
        
        # v5.0 新选项
        self.collect_all_var = tk.BooleanVar(value=True)  # 使用 collect-submodules
        self.fast_mode_var = tk.BooleanVar(value=True)
        self.parallel_var = tk.BooleanVar(value=True)
        self.runtime_trace_var = tk.BooleanVar(value=False)  # 运行时追踪
        
        # 消息队列
        self.message_queue = queue.Queue()
        
        # 分析结果
        self.analyzed_deps: Dict[str, dict] = {}
        self.missing_deps: List[str] = []
        self.all_imports: Set[str] = set()
        self.hidden_imports: Set[str] = set()
        
        # 构建UI
        self._create_ui()
        self._process_queue()
    
    def _create_ui(self):
        """创建用户界面"""
        # 标题栏
        title_frame = tk.Frame(self.root, bg='#1a237e', height=45)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text=f"🎮 别快EXE打包工具 v{VERSION} - 缓存增强版",
            font=('Microsoft YaHei', 11, 'bold'),
            bg='#1a237e', fg='white'
        ).pack(pady=10)
        
        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)
        
        # 各标签页
        self._create_config_tab()
        self._create_check_tab()
        self._create_deps_tab()
        self._create_log_tab()
        
        # 底部控制栏
        self._create_bottom_bar()
    
    def _create_config_tab(self):
        """配置标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📦 打包配置")
        
        # 使用Canvas实现滚动
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        main = scrollable_frame
        
        # ============ 源文件配置 ============
        source_frame = tk.LabelFrame(main, text="源文件与输出", font=('Arial', 10, 'bold'),
                                     bg='white', padx=10, pady=8)
        source_frame.pack(fill=tk.X, padx=10, pady=5)
        
        row1 = tk.Frame(source_frame, bg='white')
        row1.pack(fill=tk.X, pady=3)
        
        tk.Label(row1, text="源文件:", font=('Arial', 10), bg='white', width=8).pack(side=tk.LEFT)
        self.source_entry = ttk.Entry(row1, font=('Arial', 10))
        self.source_entry.insert(0, self.default_source)
        self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(row1, text="浏览", font=('Arial', 9), bg='#2196F3', fg='white',
                  command=self._browse_source).pack(side=tk.LEFT)
        
        row2 = tk.Frame(source_frame, bg='white')
        row2.pack(fill=tk.X, pady=3)
        
        tk.Label(row2, text="输出名:", font=('Arial', 10), bg='white', width=8).pack(side=tk.LEFT)
        self.output_entry = ttk.Entry(row2, font=('Arial', 10))
        self.output_entry.insert(0, self.output_name)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # ============ 图标配置 ============
        icon_frame = tk.LabelFrame(main, text="图标配置", font=('Arial', 10, 'bold'),
                                   bg='white', padx=10, pady=8)
        icon_frame.pack(fill=tk.X, padx=10, pady=5)
        
        icons = [
            ("EXE图标 (480x480)", "exe", "480x480.png"),
            ("窗口图标 (28x28)", "window", "28x28.png"),
            ("任务栏 (108x108)", "taskbar", "108x108.png"),
        ]
        
        for label, key, default in icons:
            row = tk.Frame(icon_frame, bg='white')
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label + ":", font=('Arial', 9), bg='white', width=16, anchor='w').pack(side=tk.LEFT)
            entry = ttk.Entry(row, font=('Arial', 9))
            entry.insert(0, default)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            tk.Button(row, text="...", font=('Arial', 9), width=3,
                      command=lambda k=key: self._browse_icon(k)).pack(side=tk.LEFT)
            setattr(self, f"{key}_icon_entry", entry)
        
        # ============ 打包模式 ============
        mode_frame = tk.LabelFrame(main, text="打包模式", font=('Arial', 10, 'bold'),
                                   bg='white', padx=10, pady=8)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        
        mode_row = tk.Frame(mode_frame, bg='white')
        mode_row.pack(fill=tk.X)
        
        # 单文件夹（推荐）
        left = tk.Frame(mode_row, bg='#e8f5e9', relief=tk.RIDGE, bd=2)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Radiobutton(left, text="📁 单文件夹模式（推荐）", variable=self.pack_mode_var,
                       value='onedir', font=('Arial', 10, 'bold'), bg='#e8f5e9',
                       fg='#2e7d32').pack(anchor='w', padx=10, pady=5)
        tk.Label(left, text="• 启动速度快 • 无临时文件问题\n• 适合大型游戏和复杂程序",
                 font=('Arial', 9), bg='#e8f5e9', fg='#1b5e20',
                 justify='left').pack(anchor='w', padx=25, pady=(0, 8))
        
        # 单文件
        right = tk.Frame(mode_row, bg='#e3f2fd', relief=tk.RIDGE, bd=2)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Radiobutton(right, text="📦 单文件模式", variable=self.pack_mode_var,
                       value='onefile', font=('Arial', 10, 'bold'), bg='#e3f2fd',
                       fg='#1565c0').pack(anchor='w', padx=10, pady=5)
        tk.Label(right, text="• 方便分发 • 首次启动较慢\n• 需要配置清理策略",
                 font=('Arial', 9), bg='#e3f2fd', fg='#0d47a1',
                 justify='left').pack(anchor='w', padx=25, pady=(0, 8))
        
        # 清理策略
        cleanup_frame = tk.LabelFrame(main, text="临时文件清理（单文件模式）",
                                      font=('Arial', 10, 'bold'), bg='#fff3e0', padx=10, pady=8)
        cleanup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        cleanup_row = tk.Frame(cleanup_frame, bg='#fff3e0')
        cleanup_row.pack(fill=tk.X)
        
        strategies = [
            ("Atexit（推荐）", 'atexit', "程序退出时清理"),
            ("Bootloader", 'bootloader', "需PyInstaller 5.0+"),
            ("不清理", 'manual', "调试用"),
        ]
        
        for text, value, desc in strategies:
            f = tk.Frame(cleanup_row, bg='#fff3e0')
            f.pack(side=tk.LEFT, expand=True)
            tk.Radiobutton(f, text=text, variable=self.cleanup_strategy_var, value=value,
                           font=('Arial', 9), bg='#fff3e0').pack()
            tk.Label(f, text=desc, font=('Arial', 8), bg='#fff3e0', fg='gray').pack()
        
        # ============ 打包选项 ============
        opt_frame = tk.LabelFrame(main, text="打包选项", font=('Arial', 10, 'bold'),
                                  bg='white', padx=10, pady=8)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)
        
        opt_row1 = tk.Frame(opt_frame, bg='white')
        opt_row1.pack(fill=tk.X, pady=3)
        
        checks = [
            ("隐藏控制台", self.no_console_var),
            ("清理临时文件", self.clean_var),
            ("UPX压缩", self.upx_var),
            ("管理员权限", self.admin_var),
            ("🛡️ 安全模式", self.safe_mode_var),
        ]
        
        for text, var in checks:
            tk.Checkbutton(opt_row1, text=text, variable=var, font=('Arial', 9),
                           bg='white').pack(side=tk.LEFT, padx=8)
        
        # v5.0 新选项
        opt_row2 = tk.Frame(opt_frame, bg='#e8f4fd')
        opt_row2.pack(fill=tk.X, pady=5)
        
        tk.Label(opt_row2, text="⚡ v5.2 增强:", font=('Arial', 9, 'bold'),
                 bg='#e8f4fd', fg='#1565c0').pack(side=tk.LEFT, padx=5)
        
        v5_opts = [
            ("自动收集子模块", self.collect_all_var),
            ("排除调试模块", self.fast_mode_var),
            ("并行分析", self.parallel_var),
        ]
        
        for text, var in v5_opts:
            tk.Checkbutton(opt_row2, text=text, variable=var, font=('Arial', 9),
                           bg='#e8f4fd').pack(side=tk.LEFT, padx=8)
        
        # ============ v5.2 说明 ============
        info_frame = tk.LabelFrame(main, text="v5.2 改进说明", font=('Arial', 9, 'bold'),
                                   bg='#e8f5e9', padx=10, pady=5)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_text = """✅ 缓存有效期延长至 7 天（解决重复检测问题）
✅ 缓存文件固定在用户目录（换目录不丢失）
✅ 修复 pyinstaller/torch 等检测问题
✅ 自动 collect-submodules 处理复杂库"""
        
        tk.Label(info_frame, text=info_text, font=('Arial', 9), bg='#e8f5e9',
                 fg='#1b5e20', justify='left').pack(anchor='w')
    
    def _create_check_tab(self):
        """环境检查标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🔍 环境检查")
        
        tk.Label(frame, text="检查Python环境、依赖和图标文件",
                 font=('Arial', 10)).pack(pady=5)
        
        text_frame = tk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.check_text = tk.Text(text_frame, height=20, font=('Consolas', 9),
                                  yscrollcommand=scrollbar.set)
        self.check_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.check_text.yview)
    
    def _create_deps_tab(self):
        """依赖分析标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📊 依赖分析")
        
        tk.Label(frame, text="深度分析源文件依赖（AST + 动态导入 + 隐式依赖）",
                 font=('Arial', 10)).pack(pady=5)
        
        # Treeview
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('模块名', '状态', '版本', 'pip包名', '类型')
        self.deps_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        widths = [150, 80, 100, 130, 150]
        for col, width in zip(columns, widths):
            self.deps_tree.heading(col, text=col)
            self.deps_tree.column(col, width=width)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.deps_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.deps_tree.xview)
        self.deps_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.deps_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # 统计标签
        self.deps_info = tk.Label(frame, text="请先选择源文件并点击'分析'",
                                  font=('Arial', 10), fg='gray')
        self.deps_info.pack(pady=5)
    
    def _create_log_tab(self):
        """打包日志标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📝 打包日志")
        
        self.log_text = scrolledtext.ScrolledText(frame, height=20, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=3)
        
        tk.Button(btn_frame, text="清空日志", font=('Arial', 9),
                  command=lambda: self.log_text.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="复制日志", font=('Arial', 9),
                  command=self._copy_log).pack(side=tk.LEFT, padx=5)
    
    def _create_bottom_bar(self):
        """底部控制栏"""
        bottom = tk.Frame(self.root, bg='#ecf0f1', height=85)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)
        
        # 进度条
        self.progress = ttk.Progressbar(bottom, length=870, mode='determinate')
        self.progress.pack(pady=(8, 2))
        
        self.progress_label = tk.Label(bottom, text="准备就绪 - v5.2 缓存增强版",
                                       font=('Arial', 9), bg='#ecf0f1')
        self.progress_label.pack()
        
        # 按钮
        btn_frame = tk.Frame(bottom, bg='#ecf0f1')
        btn_frame.pack(pady=5)
        
        buttons = [
            ("🔍 检查", '#FF9800', self._start_check),
            ("📊 分析", '#9C27B0', self._start_analyze),
            ("📦 安装", '#2196F3', self._start_install),
            ("🚀 打包", '#4CAF50', self._start_pack),
            ("🗑️ 清缓存", '#FF5722', self._clear_cache),
            ("📁 目录", '#607D8B', self._open_output),
            ("❌ 退出", '#F44336', self._quit),
        ]
        
        self.btn_refs = {}
        for text, color, cmd in buttons:
            btn = tk.Button(btn_frame, text=text, font=('Arial', 9, 'bold'),
                           bg=color, fg='white', width=8, command=cmd)
            btn.pack(side=tk.LEFT, padx=3)
            self.btn_refs[text] = btn
        
        # 初始状态
        self.btn_refs["📊 分析"].config(state='disabled')
        self.btn_refs["🚀 打包"].config(state='disabled')
    
    # ==================== 工具方法 ====================
    
    def _browse_source(self):
        """浏览源文件"""
        filepath = filedialog.askopenfilename(
            title="选择Python源文件",
            filetypes=[("Python文件", "*.py"), ("所有文件", "*.*")]
        )
        if filepath:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, filepath)
            # 重置状态
            self.analyzed_deps = {}
            self.missing_deps = []
            self.btn_refs["📊 分析"].config(state='disabled')
            self.btn_refs["🚀 打包"].config(state='disabled')
    
    def _browse_icon(self, icon_type: str):
        """浏览图标文件"""
        filepath = filedialog.askopenfilename(
            title=f"选择{icon_type}图标",
            filetypes=[("图片文件", "*.png *.ico"), ("所有文件", "*.*")]
        )
        if filepath:
            entry = getattr(self, f"{icon_type}_icon_entry")
            entry.delete(0, tk.END)
            entry.insert(0, filepath)
    
    def _get_source_file(self) -> str:
        """获取并验证源文件路径"""
        source = self.source_entry.get().strip()
        if source and not source.endswith('.py'):
            source += '.py'
        return source
    
    def _copy_log(self):
        """复制日志到剪贴板"""
        content = self.log_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("成功", "日志已复制到剪贴板")
    
    def _clear_cache(self):
        """清除缓存"""
        self.dep_cache.clear()
        self.analyzed_deps = {}
        self.missing_deps = []
        messagebox.showinfo("成功", "缓存已清除，下次分析将重新检测所有模块")
    
    def _open_output(self):
        """打开输出目录"""
        dist_dir = Path("dist")
        if dist_dir.exists():
            if sys.platform == 'win32':
                os.startfile(dist_dir)
            elif sys.platform == 'darwin':
                subprocess.run(['open', dist_dir])
            else:
                subprocess.run(['xdg-open', dist_dir])
        else:
            messagebox.showinfo("提示", "输出目录不存在，请先完成打包")
    
    def _quit(self):
        """退出程序"""
        if messagebox.askyesno("确认", "确定要退出吗？"):
            self.root.quit()
    
    def _add_check_msg(self, msg: str):
        """添加检查消息"""
        self.message_queue.put(('check', msg))
    
    def _add_log_msg(self, msg: str):
        """添加日志消息"""
        self.message_queue.put(('log', msg))
    
    def _process_queue(self):
        """处理消息队列"""
        try:
            while True:
                msg_type, content = self.message_queue.get_nowait()
                
                if msg_type == 'check':
                    self.check_text.insert(tk.END, content)
                    self.check_text.see(tk.END)
                elif msg_type == 'log':
                    self.log_text.insert(tk.END, content)
                    self.log_text.see(tk.END)
                elif msg_type == 'progress':
                    value, text = content
                    self.progress['value'] = value
                    self.progress_label.config(text=text)
                elif msg_type == 'deps_tree':
                    for item in content:
                        self.deps_tree.insert('', 'end', values=item)
                elif msg_type == 'deps_info':
                    text, color = content
                    self.deps_info.config(text=text, fg=color)
                elif msg_type == 'enable_btn':
                    btn_text = content
                    if btn_text in self.btn_refs:
                        self.btn_refs[btn_text].config(state='normal')
                elif msg_type == 'disable_btn':
                    btn_text = content
                    if btn_text in self.btn_refs:
                        self.btn_refs[btn_text].config(state='disabled')
        except queue.Empty:
            pass
        
        self.root.after(100, self._process_queue)
    
    # ==================== 环境检查 ====================
    
    def _start_check(self):
        """开始环境检查"""
        self.notebook.select(1)
        self.btn_refs["🔍 检查"].config(state='disabled')
        self.check_text.delete(1.0, tk.END)
        
        thread = threading.Thread(target=self._do_check, daemon=True)
        thread.start()
    
    def _do_check(self):
        """执行环境检查"""
        all_ok = True
        
        try:
            self._add_check_msg(f"{'='*60}\n")
            self._add_check_msg(f"环境检查 v{VERSION}\n")
            self._add_check_msg(f"{'='*60}\n\n")
            
            # Python信息
            py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self._add_check_msg(f"Python版本: {py_ver}\n")
            self._add_check_msg(f"解释器: {self.python_exe}\n")
            
            if getattr(sys, 'frozen', False):
                self._add_check_msg("  ⚠️ 运行在打包环境中\n")
            
            # 源文件检查
            self._add_check_msg(f"\n{'='*40}\n")
            self._add_check_msg("源文件检查\n")
            self._add_check_msg(f"{'='*40}\n")
            
            source = self._get_source_file()
            if os.path.exists(source):
                self._add_check_msg(f"✅ 源文件存在: {source}\n")
                
                # 安全性检查
                if is_safe_path(source):
                    self._add_check_msg(f"✅ 路径安全验证通过\n")
                else:
                    self._add_check_msg(f"⚠️ 路径包含可疑字符\n")
                
                # 语法检查
                try:
                    with open(source, 'r', encoding='utf-8') as f:
                        content = f.read()
                    compile(content, source, 'exec')
                    self._add_check_msg(f"✅ 语法正确 ({len(content):,} 字符)\n")
                except SyntaxError as e:
                    self._add_check_msg(f"❌ 语法错误: 第{e.lineno}行 - {e.msg}\n")
                    all_ok = False
                except Exception as e:
                    self._add_check_msg(f"❌ 读取失败: {e}\n")
                    all_ok = False
            else:
                self._add_check_msg(f"❌ 源文件不存在: {source}\n")
                all_ok = False
            
            # 图标检查
            self._add_check_msg(f"\n{'='*40}\n")
            self._add_check_msg("图标文件检查\n")
            self._add_check_msg(f"{'='*40}\n")
            
            icons = {
                'EXE图标': self.exe_icon_entry.get(),
                '窗口图标': self.window_icon_entry.get(),
                '任务栏图标': self.taskbar_icon_entry.get(),
            }
            
            for name, path in icons.items():
                if path:
                    abs_path = os.path.abspath(path)
                    if os.path.exists(abs_path):
                        size = os.path.getsize(abs_path)
                        self._add_check_msg(f"✅ {name}: {os.path.basename(path)} ({size:,} bytes)\n")
                    else:
                        self._add_check_msg(f"⚠️ {name}不存在: {path}\n")
            
            # ============ v5.1 修复：核心依赖检查 ============
            self._add_check_msg(f"\n{'='*40}\n")
            self._add_check_msg("核心依赖检查\n")
            self._add_check_msg(f"{'='*40}\n")
            
            # v5.1 修复：使用正确的导入名（大小写敏感）
            # PyInstaller 的导入名是 PyInstaller，不是 pyinstaller
            core_deps = ['PyInstaller', 'PIL']  # 使用正确的导入名！
            
            results = self.module_checker.check_modules(set(core_deps), use_cache=False)
            
            for dep in core_deps:
                info = results.get(dep, {})
                # 显示时使用友好名称
                display_name = dep.lower() if dep == 'PyInstaller' else dep
                pip_name = PACKAGE_NAME_MAP.get(dep, dep.lower())
                
                if info.get('available'):
                    ver = info.get('version', 'N/A')
                    self._add_check_msg(f"✅ {display_name}: v{ver}\n")
                else:
                    self._add_check_msg(f"❌ {display_name}: 未安装 (pip install {pip_name})\n")
                    if dep == 'PyInstaller':
                        all_ok = False
            
            # Tkinter检查
            self._add_check_msg(f"\n{'='*40}\n")
            self._add_check_msg("Tkinter环境\n")
            self._add_check_msg(f"{'='*40}\n")
            
            if 'tkinter' in STDLIB_MODULES:
                self._add_check_msg("✅ Tkinter 可用（标准库）\n")
            
            # 结果
            self._add_check_msg(f"\n{'='*60}\n")
            if all_ok:
                self._add_check_msg("✅ 环境检查通过！请点击'分析'按钮\n")
                self.message_queue.put(('enable_btn', "📊 分析"))
            else:
                self._add_check_msg("❌ 检查未通过，请先解决上述问题\n")
            
        except Exception as e:
            self._add_check_msg(f"\n❌ 检查出错: {e}\n")
            self._add_check_msg(traceback.format_exc())
        
        self.message_queue.put(('enable_btn', "🔍 检查"))
    
    # ==================== 依赖分析 ====================
    
    def _start_analyze(self):
        """开始依赖分析"""
        source = self._get_source_file()
        if not os.path.exists(source):
            messagebox.showerror("错误", f"源文件不存在: {source}")
            return
        
        self.notebook.select(2)
        self.btn_refs["📊 分析"].config(state='disabled')
        
        # 清空树
        for item in self.deps_tree.get_children():
            self.deps_tree.delete(item)
        
        self.deps_info.config(text="正在深度分析依赖...", fg='blue')
        
        thread = threading.Thread(target=self._do_analyze, args=(source,), daemon=True)
        thread.start()
    
    def _do_analyze(self, source: str):
        """执行依赖分析"""
        try:
            self.message_queue.put(('progress', (10, "解析源代码...")))
            
            # AST分析
            analyzer = AdvancedImportAnalyzer()
            import_result = analyzer.analyze_file(source)
            
            all_imports = import_result['all']
            
            self.message_queue.put(('progress', (30, f"检测 {len(all_imports)} 个模块...")))
            
            # 添加隐式依赖
            expanded = set()
            for mod in all_imports:
                top = mod.split('.')[0]
                expanded.add(top)
                
                # 添加该库的隐式依赖
                if top in IMPLICIT_DEPENDENCIES:
                    for implicit in IMPLICIT_DEPENDENCIES[top]:
                        expanded.add(implicit)
                        expanded.add(implicit.split('.')[0])
            
            # 批量检测
            self.message_queue.put(('progress', (50, "批量检测模块状态...")))
            results = self.module_checker.check_modules(expanded)
            
            # 整理结果
            self.analyzed_deps = {}
            self.missing_deps = []
            self.all_imports = set()
            self.hidden_imports = set()
            
            tree_data = []
            
            for mod, info in sorted(results.items()):
                if mod in STDLIB_MODULES:
                    continue  # 跳过标准库在树中显示
                
                self.analyzed_deps[mod] = info
                self.all_imports.add(mod)
                
                status = '✅ 已安装' if info['available'] else '❌ 未安装'
                
                # 判断类型
                if mod in import_result['imports'] or mod in import_result['from_imports']:
                    source_type = '直接导入'
                elif mod in import_result['dynamic']:
                    source_type = '动态导入'
                elif mod in import_result['conditional']:
                    source_type = '条件导入'
                else:
                    source_type = '隐式依赖'
                    self.hidden_imports.add(mod)
                
                tree_data.append((mod, status, info.get('version', 'N/A'),
                                  info.get('pip_name', mod), source_type))
                
                if not info['available'] and info.get('pip_name', '-') != '-':
                    self.missing_deps.append(info['pip_name'])
            
            # 去重
            self.missing_deps = list(set(self.missing_deps))
            
            # 更新UI
            self.message_queue.put(('progress', (90, "更新界面...")))
            self.message_queue.put(('deps_tree', tree_data))
            
            # 统计信息
            total = len(tree_data)
            missing = len(self.missing_deps)
            implicit = len(self.hidden_imports)
            
            if missing > 0:
                info_text = f"发现 {missing} 个缺失依赖: {', '.join(self.missing_deps[:5])}"
                if len(self.missing_deps) > 5:
                    info_text += f" ... 等 {len(self.missing_deps)} 个"
                self.message_queue.put(('deps_info', (info_text, 'red')))
            else:
                info_text = f"✅ 所有 {total} 个第三方依赖就绪 (含 {implicit} 个隐式依赖)"
                self.message_queue.put(('deps_info', (info_text, 'green')))
                self.message_queue.put(('enable_btn', "🚀 打包"))
            
            self.message_queue.put(('progress', (100, "分析完成")))
            
        except Exception as e:
            self.message_queue.put(('deps_info', (f"分析失败: {e}", 'red')))
            traceback.print_exc()
        
        self.message_queue.put(('enable_btn', "📊 分析"))
    
    # ==================== 依赖安装 ====================
    
    def _start_install(self):
        """开始安装依赖"""
        self.btn_refs["📦 安装"].config(state='disabled')
        self.notebook.select(3)
        
        thread = threading.Thread(target=self._do_install, daemon=True)
        thread.start()
    
    def _do_install(self):
        """执行依赖安装"""
        try:
            # 收集需要安装的包
            to_install = []
            
            # ============ v5.1 修复：核心依赖检查 ============
            # 使用正确的导入名检查，但安装时用 pip 包名
            core_check = {
                'PyInstaller': 'pyinstaller',  # 导入名 -> pip包名
                'PIL': 'Pillow',
            }
            
            # 检查时使用导入名
            core_results = self.module_checker.check_modules(set(core_check.keys()), use_cache=False)
            
            for import_name, pip_name in core_check.items():
                if not core_results.get(import_name, {}).get('available'):
                    to_install.append(pip_name)
            
            # 分析出的缺失依赖
            for dep in self.missing_deps:
                if dep not in to_install and dep != '-':
                    # 安全检查
                    if is_safe_package_name(dep):
                        to_install.append(dep)
                    else:
                        self._add_log_msg(f"⚠️ 跳过不安全的包名: {dep}\n")
            
            to_install = list(set(to_install))
            
            self._add_log_msg(f"{'='*60}\n")
            self._add_log_msg(f"v{VERSION} 安全安装模式\n")
            self._add_log_msg(f"{'='*60}\n\n")
            
            if not to_install:
                self._add_log_msg("✅ 所有依赖已安装，无需操作\n")
                self.message_queue.put(('enable_btn', "📦 安装"))
                return
            
            self._add_log_msg(f"需要安装: {', '.join(to_install)}\n\n")
            
            # 镜像源
            mirrors = [
                ("清华镜像", "https://pypi.tuna.tsinghua.edu.cn/simple"),
                ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
                ("官方源", "https://pypi.org/simple"),
            ]
            
            success = 0
            failed = 0
            
            for pkg in to_install:
                self._add_log_msg(f"安装 {pkg}...\n")
                installed = False
                
                for mirror_name, mirror_url in mirrors:
                    try:
                        self._add_log_msg(f"  尝试 {mirror_name}...\n")
                        
                        # 安全构建命令
                        cmd = [
                            self.python_exe, "-m", "pip", "install",
                            pkg,  # 已验证安全
                            "-i", mirror_url,
                            "--upgrade",
                            "--no-warn-script-location"
                        ]
                        
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=180
                        )
                        
                        if result.returncode == 0:
                            self._add_log_msg(f"  ✅ 安装成功\n")
                            installed = True
                            success += 1
                            
                            # ============ v5.1 修复：正确更新缓存 ============
                            # 使用 pip包名 -> 导入名 的映射来更新缓存
                            import_name = pip_name_to_import_name(pkg)
                            self.dep_cache.set(import_name, True)
                            self._add_log_msg(f"  📝 缓存更新: {import_name}\n")
                            break
                        else:
                            err = result.stderr[:100] if result.stderr else "未知错误"
                            self._add_log_msg(f"  ⚠️ 失败: {err}\n")
                    
                    except subprocess.TimeoutExpired:
                        self._add_log_msg(f"  ⚠️ 安装超时\n")
                    except Exception as e:
                        self._add_log_msg(f"  ⚠️ 错误: {e}\n")
                
                if not installed:
                    failed += 1
                
                self._add_log_msg("-" * 40 + "\n")
            
            self._add_log_msg(f"\n完成！成功: {success}, 失败: {failed}\n")
            
            if failed == 0:
                self._add_log_msg("\n✅ 所有依赖安装成功！请重新点击'检查'\n")
                self.missing_deps = []
            
        except Exception as e:
            self._add_log_msg(f"\n❌ 安装出错: {e}\n")
            traceback.print_exc()
        
        self.message_queue.put(('enable_btn', "📦 安装"))
    
    # ==================== 打包执行 ====================
    
    def _start_pack(self):
        """开始打包"""
        source = self._get_source_file()
        if not os.path.exists(source):
            messagebox.showerror("错误", f"源文件不存在: {source}")
            return
        
        self.btn_refs["🚀 打包"].config(state='disabled')
        self.notebook.select(3)
        self.log_text.delete(1.0, tk.END)
        
        thread = threading.Thread(target=self._do_pack, args=(source,), daemon=True)
        thread.start()
    
    def _do_pack(self, source: str):
        """执行打包"""
        wrapper_file = None
        temp_ico = None
        
        try:
            output_name = self.output_entry.get().strip() or "output"
            pack_mode = self.pack_mode_var.get()
            
            self.message_queue.put(('progress', (5, "初始化...")))
            
            self._add_log_msg(f"{'='*70}\n")
            self._add_log_msg(f"开始打包 v{VERSION}\n")
            self._add_log_msg(f"{'='*70}\n")
            self._add_log_msg(f"源文件: {source}\n")
            self._add_log_msg(f"输出名: {output_name}\n")
            self._add_log_msg(f"模式: {'单文件' if pack_mode == 'onefile' else '文件夹'}\n")
            self._add_log_msg(f"{'='*70}\n\n")
            
            # 准备图标
            self.message_queue.put(('progress', (10, "准备图标...")))
            icons = self._prepare_icons()
            
            if 'exe' in icons and icons['exe'].endswith('temp_app_icon.ico'):
                temp_ico = icons['exe']
            
            # 创建包装器
            self.message_queue.put(('progress', (15, "生成包装器...")))
            
            if pack_mode == 'onefile' or icons.get('window') or icons.get('taskbar'):
                wrapper_file = self._create_wrapper(source, icons)
                actual_source = wrapper_file
                self._add_log_msg(f"✅ 包装器: {wrapper_file}\n")
            else:
                actual_source = source
            
            # 收集数据文件
            self.message_queue.put(('progress', (20, "收集资源...")))
            data_files = self._collect_data_files(source, icons)
            self._add_log_msg(f"✅ 收集了 {len(data_files)} 个数据文件\n")
            
            # 构建命令
            self.message_queue.put(('progress', (25, "构建命令...")))
            cmd = self._build_command(actual_source, output_name, icons, data_files)
            
            # 执行打包
            self.message_queue.put(('progress', (30, "执行打包...")))
            self._add_log_msg(f"\n执行PyInstaller...\n")
            self._add_log_msg(f"命令: {' '.join(cmd[:15])}...\n\n")
            
            start_time = time.time()
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            progress = 30
            for line in process.stdout:
                self._add_log_msg(line)
                
                if "Building" in line or "Analyzing" in line:
                    progress = min(progress + 2, 90)
                elif "Copying" in line:
                    progress = min(progress + 1, 90)
                
                self.message_queue.put(('progress', (progress, "打包中...")))
            
            process.wait()
            elapsed = time.time() - start_time
            
            # 检查结果
            self.message_queue.put(('progress', (95, "检查结果...")))
            
            if pack_mode == 'onefile':
                exe_path = Path("dist") / f"{output_name}.exe"
            else:
                exe_path = Path("dist") / output_name / f"{output_name}.exe"
            
            if exe_path.exists():
                file_size = exe_path.stat().st_size / (1024 * 1024)
                
                self.message_queue.put(('progress', (100, f"完成！耗时 {elapsed:.1f}s")))
                
                self._add_log_msg(f"\n{'='*70}\n")
                self._add_log_msg(f"✅ 打包成功！\n")
                self._add_log_msg(f"输出: {exe_path}\n")
                self._add_log_msg(f"大小: {file_size:.2f} MB\n")
                self._add_log_msg(f"耗时: {elapsed:.1f} 秒\n")
                self._add_log_msg(f"{'='*70}\n")
                
                if pack_mode == 'onedir':
                    folder = Path("dist") / output_name
                    total = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
                    self._add_log_msg(f"文件夹总大小: {total / (1024*1024):.2f} MB\n")
                
                messagebox.showinfo("成功", 
                    f"✅ 打包完成！\n\n"
                    f"文件: {exe_path}\n"
                    f"大小: {file_size:.2f} MB\n"
                    f"耗时: {elapsed:.1f} 秒")
            else:
                self.message_queue.put(('progress', (100, "失败")))
                self._add_log_msg(f"\n❌ 打包失败 - 未找到输出文件\n")
                messagebox.showerror("失败", "打包失败！请查看日志")
        
        except Exception as e:
            self.message_queue.put(('progress', (100, f"错误: {e}")))
            self._add_log_msg(f"\n❌ 打包出错: {e}\n")
            self._add_log_msg(traceback.format_exc())
            messagebox.showerror("错误", f"打包出错: {e}")
        
        finally:
            # 清理临时文件
            for f in [wrapper_file, temp_ico]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
            
            self.message_queue.put(('enable_btn', "🚀 打包"))
    
    def _prepare_icons(self) -> Dict[str, str]:
        """准备图标文件"""
        icons = {}
        
        try:
            from PIL import Image
            has_pil = True
        except ImportError:
            has_pil = False
            self._add_log_msg("⚠️ Pillow未安装，无法转换PNG到ICO\n")
        
        # EXE图标
        exe_icon = self.exe_icon_entry.get()
        if exe_icon:
            abs_path = os.path.abspath(exe_icon)
            if os.path.exists(abs_path):
                if abs_path.lower().endswith('.png') and has_pil:
                    try:
                        img = Image.open(abs_path)
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        
                        ico_path = "temp_app_icon.ico"
                        sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
                        img.save(ico_path, format='ICO', sizes=sizes)
                        
                        icons['exe'] = os.path.abspath(ico_path)
                        self._add_log_msg(f"✅ 生成ICO: {ico_path}\n")
                    except Exception as e:
                        self._add_log_msg(f"⚠️ ICO转换失败: {e}\n")
                        icons['exe'] = abs_path
                else:
                    icons['exe'] = abs_path
        
        # 窗口和任务栏图标
        for key, entry in [('window', self.window_icon_entry), ('taskbar', self.taskbar_icon_entry)]:
            path = entry.get()
            if path:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    icons[key] = abs_path
        
        return icons
    
    def _create_wrapper(self, source: str, icons: Dict[str, str]) -> str:
        """创建包装器文件"""
        try:
            with open(source, 'r', encoding='utf-8') as f:
                original = f.read()
        except UnicodeDecodeError:
            with open(source, 'r', encoding='gbk') as f:
                original = f.read()
        
        window_icon = os.path.basename(icons.get('window', '')) if icons.get('window') else ''
        taskbar_icon = os.path.basename(icons.get('taskbar', '')) if icons.get('taskbar') else ''
        
        cleanup_code = ''
        if self.pack_mode_var.get() == 'onefile':
            if self.cleanup_strategy_var.get() == 'atexit':
                cleanup_code = '''
# 临时文件夹清理（Atexit策略）
import sys, os, atexit, shutil, time

def _cleanup_meipass():
    if hasattr(sys, '_MEIPASS'):
        try:
            time.sleep(0.3)
            shutil.rmtree(sys._MEIPASS, ignore_errors=True)
        except: pass

if hasattr(sys, '_MEIPASS'):
    atexit.register(_cleanup_meipass)
'''
        
        wrapper_code = f'''# -*- coding: utf-8 -*-
# 自动生成的包装器 v{VERSION}
{cleanup_code}
import sys, os

def _setup_icons():
    try:
        if hasattr(sys, '_MEIPASS'):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        
        window_icon = "{window_icon}"
        taskbar_icon = "{taskbar_icon}"
        
        def find_icon(name):
            if not name: return None
            for p in [os.path.join(base, name), os.path.join(os.getcwd(), name), name]:
                if os.path.exists(p): return os.path.abspath(p)
            return None
        
        try:
            import tkinter as tk
            _orig_tk = tk.Tk.__init__
            def _new_tk(self, *a, **kw):
                _orig_tk(self, *a, **kw)
                try:
                    icon = find_icon(window_icon)
                    if icon and icon.endswith('.png'):
                        photo = tk.PhotoImage(file=icon)
                        self.iconphoto(True, photo)
                        self._icon_ref = photo
                    elif icon:
                        self.iconbitmap(icon)
                except: pass
            tk.Tk.__init__ = _new_tk
        except: pass
        
        try:
            import pygame
            _orig_init = pygame.init
            def _new_init(*a, **kw):
                r = _orig_init(*a, **kw)
                try:
                    icon = find_icon(window_icon)
                    if icon:
                        pygame.display.set_icon(pygame.image.load(icon))
                except: pass
                return r
            pygame.init = _new_init
        except: pass
    except: pass

_setup_icons()

# ===== 原始代码 =====
'''
        
        wrapper = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                               suffix='.py', delete=False)
        wrapper.write(wrapper_code)
        wrapper.write(original)
        wrapper.close()
        
        return wrapper.name
    
    def _collect_data_files(self, source: str, icons: Dict[str, str]) -> List[Tuple[str, str]]:
        """收集数据文件"""
        data_files = []
        collected = set()
        
        source_dir = os.path.dirname(os.path.abspath(source)) or '.'
        
        # 从源码提取引用的文件
        try:
            with open(source, 'r', encoding='utf-8') as f:
                code = f.read()
        except:
            code = ""
        
        patterns = [
            r'["\']([^"\']+\.(?:png|jpg|jpeg|gif|ico|bmp))["\']',
            r'["\']([^"\']+\.(?:json|txt|xml|cfg|ini|yaml|yml))["\']',
            r'["\']([^"\']+\.(?:wav|mp3|ogg|flac))["\']',
            r'["\']([^"\']+\.(?:ttf|otf))["\']',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                ref = match.group(1)
                for full in [os.path.join(source_dir, ref), os.path.abspath(ref)]:
                    if os.path.exists(full):
                        abs_path = os.path.abspath(full)
                        if abs_path not in collected:
                            data_files.append((abs_path, '.'))
                            collected.add(abs_path)
                        break
        
        # 添加图标
        for icon_path in icons.values():
            if icon_path and os.path.exists(icon_path):
                abs_path = os.path.abspath(icon_path)
                if abs_path not in collected:
                    data_files.append((abs_path, '.'))
                    collected.add(abs_path)
        
        return data_files
    
    def _build_command(self, source: str, output_name: str, 
                       icons: Dict[str, str], data_files: List[Tuple[str, str]]) -> List[str]:
        """构建PyInstaller命令"""
        cmd = [self.python_exe, "-m", "PyInstaller"]
        
        # 基本选项
        if self.clean_var.get():
            cmd.append("--clean")
        cmd.append("--noconfirm")
        
        # 打包模式
        if self.pack_mode_var.get() == 'onefile':
            cmd.append("--onefile")
        else:
            cmd.append("--onedir")
        
        # 控制台
        if self.no_console_var.get():
            cmd.append("--noconsole")
        
        # 图标
        if 'exe' in icons:
            cmd.extend(["--icon", icons['exe']])
        
        # 输出名
        cmd.extend(["--name", output_name])
        
        # 排除模块（提速 + 消除警告）
        if self.fast_mode_var.get():
            for exclude in EXCLUDE_MODULES:
                cmd.extend(["--exclude-module", exclude])
        
        # 数据文件
        sep = ';' if sys.platform == 'win32' else ':'
        for src, dst in data_files:
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])
        
        # 隐藏导入
        added_hidden = set()
        
        for mod in self.all_imports:
            if mod not in STDLIB_MODULES and mod not in added_hidden:
                # 检查是否被排除
                skip = False
                for excl in EXCLUDE_MODULES:
                    if mod.startswith(excl.split('.')[0]):
                        skip = True
                        break
                if not skip:
                    cmd.extend(["--hidden-import", mod])
                    added_hidden.add(mod)
        
        # 隐式依赖
        for mod in self.hidden_imports:
            if mod not in added_hidden:
                cmd.extend(["--hidden-import", mod])
                added_hidden.add(mod)
        
        # v5.0 关键：自动 collect-submodules
        if self.collect_all_var.get():
            for mod in self.all_imports:
                top = mod.split('.')[0]
                if top in COMPLEX_PACKAGES and top not in STDLIB_MODULES:
                    cmd.extend(["--collect-submodules", top])
                    self._add_log_msg(f"  📦 collect-submodules: {top}\n")
        
        # 安全模式
        if self.safe_mode_var.get():
            cmd.extend(["--collect-all", "pkg_resources"])
            cmd.extend(["--collect-all", "tkinter"])
        
        # 管理员权限
        if self.admin_var.get():
            cmd.append("--uac-admin")
        
        # UPX
        if self.upx_var.get() and shutil.which('upx'):
            cmd.append("--upx-dir=.")
        else:
            cmd.append("--noupx")
        
        # 源文件
        cmd.append(source)
        
        return cmd
    
    def run(self):
        """运行程序"""
        # 居中显示
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        
        self.root.mainloop()


def main():
    """主函数"""
    print(f"{'='*70}")
    print(f"游戏一键打包工具 v{VERSION} - 缓存增强版")
    print("="*70)
    print("✅ 缓存有效期：7 天（解决重复检测问题）")
    print("✅ 缓存位置：用户目录（换目录不丢失）")
    print("✅ 修复：pyinstaller/torch 等模块检测")
    print("✅ 兼容性：自动 collect-submodules 处理复杂库")
    print("="*70)
    print()
    
    try:
        app = GamePackagerV5()
        app.run()
    except Exception as e:
        print(f"启动失败: {e}")
        traceback.print_exc()
        input("按Enter键退出...")


if __name__ == "__main__":
    main()
