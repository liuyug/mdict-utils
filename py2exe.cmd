
rmdir build /s /q
rmdir dist\mdict_utils /s /q
pyinstaller mdict_utils.spec

dist\mdict.exe --version
