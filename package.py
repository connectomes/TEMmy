#! /usr/bin/env python

# Build/push all the TEMmy tools to where they belong

import subprocess

if __name__ == "__main__":
    from datetime import datetime
    import os
    from os.path import join
    import shutil

    # Get a timestamp for reuse:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    os.makedirs("script_packages", exist_ok=True)

    # Package TEM macros
    def write_macro(macro, content, file, all_python_file):
        num, name, *scope_name = macro.split('-')
        is_python = name.endswith(".py")
        # Don't allow backslashes in SerialEM python, because they cause a pipe error:
        if is_python:
            assert '\\"' not in content, f"Backslash-quote detected in {macro}--This won't work on SerialEM, so use a single-quoted string and remove the escape sequence instead"
            assert '\\n' not in content, f"Backslash-newline detected in {macro}--This won't work on SerialEM, so use the global var newline instead"

        name = name.replace('.py', '')
        name = name.replace('.txt', '')
        try:
            # Macros with number prefix will be put through this function first because of lexicographical ordering
            num = int(macro.split("-")[0])
            file.write(f"Macro\t{num}\n")
            if not is_python:
                file.write(f"MacroName {name}\n")
            else:
                # Collect all python code in one file to run static type-checking on
                all_python_file.write(f"{content}\n")

                if name != "Util":
                    # Write the python macro boilerplate
                    file.write("#!Python3.9\n")
                    file.write(f"#MacroName {name}\n")
                    file.write("#include Util\n")
                    file.write("import serialem as sem\n")
            file.write(f"{content}\n")
            if name != "Util":
                file.write("EndMacro\n")
        except:
            # Macros with the Util prefix will come through last
            file.write(f"############# {macro} #############\n\n{content}\n\n")
            all_python_file.write(f"{content}\n")

    macros = sorted(os.listdir('macros'))

    tem1_package_name = f"script_packages/tem1package-{timestamp}.txt"
    tem2_package_name = f"script_packages/tem2package-{timestamp}.txt"
    tem1_all_python_filename = f"script_packages/tem1-python-{timestamp}.py"
    tem2_all_python_filename = f"script_packages/tem2-python-{timestamp}.py"
    with open(tem1_package_name, "w") as macro_package_tem1, open(tem2_package_name, "w") as macro_package_tem2, open(tem1_all_python_filename, "w") as tem1_all_python_file, open(tem2_all_python_filename, "w") as tem2_all_python_file:

        macro_package_tem1.write("MaxMacros\t40\n")
        macro_package_tem2.write("MaxMacros\t40\n")
        tem1_all_python_file.write("import serialem as sem # type: ignore\n")
        tem2_all_python_file.write("import serialem as sem # type: ignore\n")
        tem1_all_python_file.write("from typing import List as list\n")
        tem2_all_python_file.write("from typing import List as list\n")
        tem1_all_python_file.write("from typing import Dict as dict\n")
        tem2_all_python_file.write("from typing import Dict as dict\n")
        for macro in macros:
            if macro.endswith(".txt") or macro.endswith(".py"):
                with open(f'macros/{macro}', "r") as macro_file: 
                    macro_content = macro_file.read()
                    if "tem1" in macro.lower():
                        write_macro(macro, macro_content, macro_package_tem1, tem1_all_python_file)
                    elif "tem2" in macro.lower():
                        write_macro(macro, macro_content, macro_package_tem2, tem2_all_python_file)
                    else:
                        write_macro(macro, macro_content, macro_package_tem1, tem1_all_python_file)
                        write_macro(macro, macro_content, macro_package_tem2, tem2_all_python_file)
        # Util needs EndMacro statement
        macro_package_tem1.write("EndMacro\n")
        macro_package_tem2.write("EndMacro\n")

    # Type-check python TEM macros
    subprocess.run(["mypy", "--config-file", "mypy.ini", tem1_all_python_filename])
    subprocess.run(["mypy", "--config-file", "mypy.ini", tem2_all_python_filename])

    os.makedirs("T:/Temmy/script_packages", exist_ok=True)
    shutil.copyfile(tem1_package_name, f"T:/Temmy/{tem1_package_name}")
    shutil.copyfile(tem2_package_name, f"T:/Temmy/{tem2_package_name}")