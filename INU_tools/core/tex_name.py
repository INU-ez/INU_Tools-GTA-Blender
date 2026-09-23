"""Game texture names from Blender image / node names.

Blender decorates image names: ``tex.png``, ``tex.png.001``, ``tex.png001``,
``tex.001``. None of that belongs in a DFF material or a TXD entry — the game
matches textures by the bare name, and the DFF and the TXD must agree on it.
``os.path.splitext`` only sees the LAST dot, so ``tex.png.001`` came out as
``tex.png`` in the TXD and ``tex.png.001`` in the DFF.

No Blender dependency.
"""

import re

# An image extension and EVERYTHING after it (".png", ".png.001", ".png001",
# ".PNG_1"). The extension must not run on into letters (".pngish" is a name).
_EXT_TAIL = re.compile(
    r'\.(?:png|jpe?g|bmp|tga|dds|tiff?|webp|exr|hdr|gif)(?![a-z]).*$',
    re.IGNORECASE)
# Blender's duplicate suffix left without an extension: "tex.001".
_DUP_TAIL = re.compile(r'(?:\.\d+)+$')


def clean_texture_name(name: str) -> str:
    """``render_tex_1.png.001`` → ``render_tex_1``; ``tex.001`` → ``tex``."""
    name = (name or '').strip()
    cleaned = _DUP_TAIL.sub('', _EXT_TAIL.sub('', name))
    return cleaned or name
