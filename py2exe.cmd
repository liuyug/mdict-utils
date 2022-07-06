
setlocal
rmdir build /s /q
rmdir dist\mdict_utils /s /q

mkdir build

set script=build\script.py
echo import mdict_utils.__main__ >> %script%
echo mdict_utils.__main__.run() >> %script%

type %script%

call ..\env_noqt\Scripts\activate
pyinstaller ^
--name mdict ^
--icon logo.ico ^
--noconfirm ^
--onefile ^
--console ^
%script%

call ..\env_noqt\Scripts\deactivate

del *.spec

endlocal

dist\mdict.exe --version
