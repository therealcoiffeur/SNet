import base64
import platform
import shutil
import subprocess
import sys
import tempfile

from pathlib import Path


DIRECTORY = Path(__file__).resolve().parent
OUTPUT = DIRECTORY / "SystemVersion.plist"
TEMPLATE = DIRECTORY / "wassup.py"
INFO_PLIST = DIRECTORY / "Info.plist"

SOURCE = r"""
#include <stdio.h>

__attribute__((visibility("default")))
int run(void)
{
    FILE *fp = fopen("/private/tmp/LOL", "w");
    if (fp == NULL) {
        perror("fopen");
        return -1;
    }

    if (fputs("Coiffeur is saying 'Wassup!' from in-memory Mach-O bundle!\n", fp) == EOF) {
        perror("fputs");
        fclose(fp);
        return -1;
    }

    if (fclose(fp) == EOF) {
        perror("fclose");
        return -1;
    }

    return 0;
}
"""


def main():
    if sys.platform != "darwin":
        print("This example requires macOS.", file=sys.stderr)
        return 1

    clang = shutil.which("clang")
    if clang is None:
        print("clang was not found. Install the Xcode Command Line Tools.", file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="wassup-") as temporary_directory:
            bundle = Path(temporary_directory) / "SystemVersion.bundle"
            command = [
                clang,
                "-x",
                "objective-c",
                "-",
                "-bundle",
                "-framework",
                "Foundation",
                "-fvisibility=hidden",
                "-Wl,-exported_symbol,_run",
                "-o",
                str(bundle),
            ]
            subprocess.run(
                command,
                input=SOURCE,
                text=True,
                check=True,
            )
            encoded_bundle = base64.b64encode(bundle.read_bytes())
    except subprocess.CalledProcessError as exc:
        print(f"clang failed with exit status {exc.returncode}.", file=sys.stderr)
        return exc.returncode or 1
    except OSError as exc:
        print(f"Could not build the executable bundle: {exc}", file=sys.stderr)
        return 1

    try:
        OUTPUT.write_bytes(encoded_bundle)
        shutil.copyfile(TEMPLATE, INFO_PLIST)
    except OSError as exc:
        print(f"Could not generate output files: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {OUTPUT}")
    print(f"Generated {INFO_PLIST}")
    print(f"Architecture: {platform.machine()}\nMach-O type: MH_BUNDLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
