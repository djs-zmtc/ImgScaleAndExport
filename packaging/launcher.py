"""PyInstaller entry point.

Kept outside the package because ``imgscaleandexport/__main__.py`` uses
relative imports, which fail when run as a frozen top-level script.
"""

import sys

from imgscaleandexport.cli import main

if __name__ == "__main__":
    sys.exit(main())
