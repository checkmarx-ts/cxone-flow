from typing import Callable
from pathlib import Path


class AdditionalScanContentWriter:
    def __init__(self, relative_path : str, content : bytearray, content_decoder : Callable[[bytearray], bool]=None):
        self.__relative_path = relative_path
        self.__content = content
        self.__decoder = content_decoder if content_decoder is not None else lambda x: x

    async def write_content(self, dest_path : str) -> None:
        async with open(Path(dest_path.rstrip("/") / Path(self.__relative_path.lstrip("/"))), "rt") as f:
            f.write(self.__decoder(self.__content))
