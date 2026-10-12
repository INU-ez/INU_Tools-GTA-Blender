"""Loose DFF/TXD/COL sources for IPL import; no Blender dependency."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelFile:
    name: str
    path: str


class ModelFolder:
    def __init__(self, root):
        self.root = root
        self.files = {}
        self.duplicates = set()
        for directory, dirs, names in os.walk(root):
            dirs.sort(key=str.casefold)
            for name in sorted(names, key=str.casefold):
                if os.path.splitext(name)[1].lower() not in ('.dff', '.txd', '.col'):
                    continue
                key = name.lower()
                if key in self.files:
                    self.duplicates.add(name)
                    continue
                self.files[key] = ModelFile(name, os.path.join(directory, name))

    def read_directory(self, root):
        return list(self.files.values())

    def extract_file(self, root, name):
        entry = self.files.get(name.lower())
        if entry is None:
            return None
        with open(entry.path, 'rb') as stream:
            return stream.read()

    def col_index(self):
        from .col_library import col_chunks
        index = {}
        for entry in self.files.values():
            if not entry.name.lower().endswith('.col'):
                continue
            for start, end, name, _mid in col_chunks(self.extract_file(self.root, entry.name)):
                index.setdefault(name.lower(), (self.root, entry.name, start, end - start))
        return index
