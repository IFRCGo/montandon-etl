import os


def get_all_modules(dir: str) -> list[str]:
    """
    Get all modules within directory recursively.
    """
    modules = []
    for dirpath, _, filenames in os.walk(dir):
        for filename in filenames:
            # Get the full path of the file
            if not filename.endswith(".py"):
                continue
            file_path = os.path.join(dirpath, filename)
            file_path = file_path.replace(".py", "")
            file_path = file_path.replace("/", ".")
            modules.append(file_path)
    return modules
