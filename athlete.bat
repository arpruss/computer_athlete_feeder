c:
tasklist | findstr /i ^dolphin.exe && goto skip
start /B C:\gog\Dolphin-x64\Dolphin.exe
:skip
\Python39\python athlete.py
