@echo off
REM ============================================================
REM  Build Voice Chat Soundboard.exe
REM  Run this ON WINDOWS, in the same folder as soundboard.py.
REM  You need Python installed and on PATH first: https://python.org
REM ============================================================

REM Figure out which "python" command actually works (some installs only
REM register "py" - the Windows launcher - and not "python" on PATH).
where python >nul 2>nul
if %errorlevel%==0 (
    set PYCMD=python
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set PYCMD=py
    ) else (
        echo Could not find Python on PATH. Install it from https://python.org
        echo and make sure to check "Add python.exe to PATH" during setup.
        pause
        exit /b 1
    )
)

echo Using %PYCMD% ...
echo Installing/updating dependencies...
%PYCMD% -m pip install -r requirements.txt
%PYCMD% -m pip install pyinstaller

echo.
echo Building exe (this can take a minute or two)...
REM Calling PyInstaller as a module (python -m PyInstaller) instead of the
REM bare "pyinstaller" command avoids "not recognized" errors when pip's
REM Scripts folder isn't on PATH.
%PYCMD% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "VoiceChatSoundboard" ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --collect-all keyboard ^
    soundboard.py

echo.
if exist dist\VoiceChatSoundboard.exe (
    echo SUCCESS. Your portable exe is at: dist\VoiceChatSoundboard.exe
    echo You can copy that single file anywhere and run it directly.
) else (
    echo Something went wrong - scroll up for the error from PyInstaller.
    pause
    exit /b 1
)

echo.
echo Looking for Inno Setup to also build the installer...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %ISCC% (
    echo Found Inno Setup - building installer too...
    %ISCC% installer.iss
    if exist installer_output\VoiceChatSoundboard-Setup.exe (
        echo SUCCESS. Your installer is at: installer_output\VoiceChatSoundboard-Setup.exe
    ) else (
        echo Installer build failed - scroll up for the error from ISCC.
    )
) else (
    echo Inno Setup not found - skipping the installer build.
    echo ^(This is optional. Install it from https://jrsoftware.org/isdl.php
    echo  and re-run this script if you also want a Setup.exe installer.^)
)

pause
