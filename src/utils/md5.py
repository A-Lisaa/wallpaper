import hashlib


def get_file_md5(name: str) -> str:
    """
    Gets md5 of a file

    Args:
        name (str): path and name to the file

    Returns:
        str: md5 string of a file
    """
    hash_md5 = hashlib.md5()
    with open(name, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()
