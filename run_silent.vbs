Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Admin\.gemini\antigravity\scratch\pdf-editor\backend"
WshShell.Run "python -m uvicorn main:app --host 0.0.0.0 --port 8000", 0, False
