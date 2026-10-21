; SpaceMissionStudio Windows installer -- Inno Setup script.
;
; A setup wizard: Welcome -> License -> install location -> Install, then a
; Start Menu (and optional Desktop) shortcut that starts the GUI.
;
; Self-contained: the setup program carries a private CPython 3.11
; (python-build-standalone) with Basilisk, SpaceMissionStudio and every
; Python package installed, plus the support data (SPICE kernels, gravity
; fields, magnetic field model, albedo maps) and the Earth orientation
; files -- the folder packaging/bundle_python.py builds. Installing needs
; no Python on the machine and no internet.
;
; Building this installer (on Windows, with Inno Setup 6,
; https://jrsoftware.org/isinfo.php; ISCC.exe on PATH), from SpaceMissionStudio\:
;
;   1. Build SpaceMissionStudio's wheel:
;        powershell -File packaging\build_wheel.ps1 packaging\windows\dist
;   2. Build the bundled Python into packaging\windows\python\ (needs
;      Python 3.11.4 or later to run the script, and internet access):
;        python packaging\bundle_python.py --platform windows --dest packaging\windows\python ^
;            --wheel packaging\windows\dist\spacemissionstudio-1.1.0-py3-none-any.whl
;   3. Compile this script:
;        ISCC packaging\windows\spacemissionstudio.iss
;      -> packaging\windows\Output\spacemissionstudio-1.1.0-setup.exe
;
; Verification: .github/workflows/spacemissionstudio-release.yml and
; spacemissionstudio-windows-installer.yml build it on a Windows runner,
; install it silently and run the installed tool; packaging/README.md
; records the results. The wizard has not been clicked through by hand on
; a real Windows 10/11 machine.

#define MyAppName "SpaceMissionStudio"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "SpaceMissionStudio contributors"
#define MyAppURL "https://github.com/AVSLab/basilisk"
; The bundled Python folder; CI passes a short path (ISCC /DPythonDir=...)
; to stay clear of Windows' 260-character path limit while building.
#ifndef PythonDir
  #define PythonDir "python"
#endif

[Setup]
; A fixed, random GUID identifying this application across upgrades --
; do not reuse for a different app. Regenerated for the missionStudio ->
; SpaceMissionStudio rename (the original was
; {B96F3E9D-6C0B-4C61-9C1E-8B9E3E5B6F7A}) -- this is a new application
; identity, not an in-place upgrade of the old one, since no end user has
; ever installed the old missionStudio build via this installer (it was
; never run on a real Windows machine -- see this file's own header
; comment).
AppId={{D9A6194C-1034-4A25-946A-689B2B13E86D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
; Installs under the current user's local app data by default -- no admin
; rights/UAC prompt needed, matching install.ps1's own default
; ($env:LOCALAPPDATA\spacemissionstudio) and philosophy (a per-user tool, not
; a system-wide one).
DefaultDirName={localappdata}\SpaceMissionStudio
DefaultGroupName=SpaceMissionStudio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
LicenseFile=..\..\LICENSE
OutputDir=Output
OutputBaseFilename=spacemissionstudio-{#MyAppVersion}-setup
; About 1.5 GB of files (Qt WebEngine, Basilisk, de430.bsp): LZMA2 in a
; separate process with several block threads keeps the build time down.
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
; Basilisk publishes wheels for Windows 10/11 (x86_64) specifically (see
; ../../docs/source/Install.rst's "Prebuilt wheel availability" table) --
; this installer targets the same.
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The bundled Python (packaging\bundle_python.py), copied as it is.
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; A fresh copy on every install or upgrade, and what setups up to 1.1.0
; left: a virtual environment built at install time, the wheel, the
; bootstrap script and the constraints file.
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\dist"
Type: files; Name: "{app}\bootstrap_env.ps1"
Type: files; Name: "{app}\constraints.txt"

[Icons]
; pythonw.exe, the windowless interpreter, so no console window opens;
; -I isolates it from any PYTHONPATH or user site-packages.
Name: "{group}\SpaceMissionStudio"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I -m spacemissionstudio.cli gui"; WorkingDir: "{app}"; IconFilename: "{app}\python\python.exe"
Name: "{group}\Uninstall SpaceMissionStudio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SpaceMissionStudio"; Filename: "{app}\python\pythonw.exe"; Parameters: "-I -m spacemissionstudio.cli gui"; WorkingDir: "{app}"; IconFilename: "{app}\python\python.exe"; Tasks: desktopicon

[Run]
; Bytecode for the folder chosen here, so tracebacks name the installed
; files rather than the build machine's (the setup program does not know
; the folder when it is built). Unchecked hashes: valid whatever times the
; files get. Nothing is downloaded.
Filename: "{app}\python\python.exe"; Parameters: "-I -m compileall -q -f -j 0 -x \.tmpl\.py$ --invalidation-mode unchecked-hash ""{app}\python"""; StatusMsg: "Preparing the Python files..."; Flags: runhidden waituntilterminated
; The Earth orientation files' manifest records absolute paths; point
; them at the folder chosen here (the .deb gets this at build time,
; packaging\bundle_python.py's relocate_earth_orientation).
Filename: "{app}\python\python.exe"; Parameters: "-I -c ""import json, pathlib, sys; d = pathlib.Path(sys.prefix, 'share', 'spacemissionstudio', 'earth_orientation'); m = d / 'manifest.json'; e = json.loads(m.read_text(encoding='utf-8')); m.write_text(json.dumps([dict(k, path=str(d / pathlib.Path(k['path']).name)) for k in e], indent=2), encoding='utf-8')"""; StatusMsg: "Preparing the Python files..."; Flags: runhidden waituntilterminated
Filename: "{app}\python\pythonw.exe"; Parameters: "-I -m spacemissionstudio.cli gui"; WorkingDir: "{app}"; Description: "Launch SpaceMissionStudio now"; Flags: postinstall skipifsilent nowait unchecked

[UninstallDelete]
; Bytecode written by the step above is not in [Files].
Type: filesandordirs; Name: "{app}\python"
