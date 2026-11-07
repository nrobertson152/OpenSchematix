"""``python -m openschematix``: the window, or with a command first (``pdf``, ``components``, ``version``) the command line for other
programs (openschematix.cli), which never starts tkinter."""
import sys


def _main() -> int:
    from openschematix.cli import COMMANDS
    argv = sys.argv[1:]
    if argv and argv[0] in COMMANDS:
        from openschematix.cli import main
        return main(argv)
    from openschematix.gui.app import main
    return main()


if __name__ == "__main__":
    sys.exit(_main())
