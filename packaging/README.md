# Windows packaging notes

After testing the app on Windows and installing PyInstaller:

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Nasheed Studio" app.py
```

This initial command does not bundle FFmpeg automatically. Before delivery, include trusted Windows `ffmpeg.exe` and `ffprobe.exe` binaries in `tools/` and confirm the `find_tool()` lookup works in the packaged layout. Test the resulting `dist/Nasheed Studio/` folder on a clean Windows account without Python installed. Consider an installer only after that smoke test passes.

Do not distribute third-party binaries until their source and applicable license/redistribution requirements have been checked.
