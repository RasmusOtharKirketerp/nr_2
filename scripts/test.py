"""Legacy shim kept for backwards compatibility."""

import sys


def main() -> None:
    print("This helper script is deprecated. Run `pytest` from the project root instead.")


if __name__ == "__main__":
    sys.exit(main())
