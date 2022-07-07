
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

call ..\env_noqt\Scripts\deactivate

del *.spec

endlocal

dist\mdict.exe --version
