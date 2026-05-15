# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 打包 80/20 极化训练法跑步计划 App
构建命令: pyinstaller pyinstaller.spec --clean --noconfirm
"""

import os, certifi
from PyInstaller.utils.hooks import collect_submodules

_spec_dir = SPECPATH if SPECPATH else os.path.dirname(os.path.abspath(SPEC))
BASE = _spec_dir if os.path.isdir(os.path.join(_spec_dir, "backend")) else os.path.dirname(os.path.abspath(SPEC))
BACKEND_DIR = os.path.join(BASE, "backend")
FRONTEND_DIST = os.path.join(BASE, "frontend", "dist")

# Auto-collect all submodules of Crypto (compiled extensions & ciphers)
crypto_hidden = collect_submodules("Crypto")

a = Analysis(
    [os.path.join(BACKEND_DIR, "launcher.py")],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=[
        (FRONTEND_DIST, "frontend/dist"),
        (certifi.where(), "certifi"),
    ],
    hiddenimports=[
        # Auth & DB
        "passlib.handlers.bcrypt",
        "sqlalchemy.sql.default_comparator",
        # Server
        "fastapi.middleware.cors",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        # coros-training-mcp & deps
        "coros_api",
        "auth",
        "auth.storage",
        "auth.encrypted_store",
        "auth.keyring_store",
        "models",
        "fastmcp",
        "fastmcp.server",
        "fastmcp.client",
        "mcp",
        "mcp.server",
        "mcp.client",
        "keyring",
        "keyring.backends",
        "keyring.backends.Windows",
        "keyring.backends.chainer",
        "pycryptodome",
        "questionary",
        "nest_asyncio",
        "python_dotenv",
        # sse-starlette (MCP transport)
        "sse_starlette",
        # SSL / HTTP
        "certifi",
        "httpcore",
        "h2",
        "hpack",
        "hyperframe",
        # MCP/stdio
        "anyio",
        "sniffio",
        "jsonrpc",
        "jsonschema",
        "jsonschema.validators",
    ] + crypto_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "PIL",
        "jedi", "ipython", "spyder", "pyqt", "tornado",
        "notebook", "IPython",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RunningTrainer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RunningTrainer",
)
