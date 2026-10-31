"""Entry point used by PyInstaller builds."""
import sys

from openschematix.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
