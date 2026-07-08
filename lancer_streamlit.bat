@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel .venv...
    py -3 -m venv .venv
    if errorlevel 1 (
        py -3 -m venv --without-pip .venv
    )
    if errorlevel 1 (
        python -m venv .venv
    )
    if errorlevel 1 (
        python -m venv --without-pip .venv
    )
    if errorlevel 1 (
        echo Impossible de creer le venv.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"
set "SITE_PACKAGES=.venv\Lib\site-packages"

"%VENV_PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip absent du venv, installation cible via le pip global...
    py -3 -m pip install --upgrade --target "%SITE_PACKAGES%" -r requirements.txt
    if errorlevel 1 (
        python -m pip install --upgrade --target "%SITE_PACKAGES%" -r requirements.txt
        if errorlevel 1 (
            echo Installation des dependances impossible.
            pause
            exit /b 1
        )
    )
) else (
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation des dependances impossible.
        pause
        exit /b 1
    )
)

"%VENV_PY%" -m streamlit run app.py --server.port 8585 --server.address 127.0.0.1
