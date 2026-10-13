"""Allow ``python -m imgscaleandexport``."""

import sys

from .cli import main

sys.exit(main())
