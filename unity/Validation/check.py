"""Compile C# with isolated Unity signature stubs; run actual pure policy code.

This is not a substitute for Unity Editor compilation or PlayMode QA.
Set MEDGUARD_DOTNET_ROOT to a .NET 8 SDK installation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sdk = Path(os.environ["MEDGUARD_DOTNET_ROOT"])
compiler = sorted(sdk.glob("sdk/*/Roslyn/bincore/csc.dll"))[-1]
runtime = sorted(sdk.glob("shared/Microsoft.NETCore.App/*"))[-1]
files = sorted((root / "Assets/MedGuardMotion/Runtime").glob("*.cs"))
files += [root / "Validation/UnityStubs.cs", root / "Validation/CoreChecks.cs"]
with tempfile.TemporaryDirectory() as temp:
    output = Path(temp) / "CoreChecks.dll"
    args = [str(sdk / "dotnet"), "exec", str(compiler), "-nologo", "-target:exe", "-out:" + str(output)]
    args += ["-r:" + str(file) for file in runtime.glob("*.dll")]
    args += [str(file) for file in files]
    if subprocess.run(args).returncode:
        sys.exit(1)
    output.with_suffix(".runtimeconfig.json").write_text(json.dumps({"runtimeOptions": {
        "tfm":"net8.0", "framework":{"name":"Microsoft.NETCore.App", "version":runtime.name}}}))
    subprocess.run([str(sdk / "dotnet"), str(output)], check=True)
