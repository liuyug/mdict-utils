
setlocal
rmdir build /s /q
rmdir dist\mdict_utils /s /q

mkdir build

set script=build\script.py
echo import mdict_utils.__main__ >> %script%
echo mdict_utils.__main__.run() >> %script%

for /F %%i in ('python -c "import random, string; print(''.join(random.choices(string.digits + string.ascii_letters, k=16)))"') do ( set key=%%i)

type %script%
echo %key%

call ..\env_noqt\Scripts\activate
pyinstaller ^
--key %key% ^
--name mdict ^
--icon logo.ico ^
--exclude-module tkinter ^
--noconfirm ^
--onefile ^
--console ^
%script%

rem --log-level=DEBUG ^
call ..\env_noqt\Scripts\deactivate


dist\mdict.exe --version

cd dist
del mdict-win32.7z /q
set c7z="C:\Program Files\7-Zip\7z.exe"
%c7z% a mdict-win32.7z mdict.exe
cd ..

del *.spec
endlocal
