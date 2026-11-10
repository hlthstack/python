"""Generate the sync resources module from the async one.

python scripts/unasync.py          # rewrite src/hlthstack/_sync_resources.py
python scripts/unasync.py --check  # exit 1 if it is out of date
"""

import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "hlthstack"
SOURCE = PACKAGE / "_async_resources.py"
TARGET = PACKAGE / "_sync_resources.py"

HEADER = "# This file is generated from _async_resources.py by scripts/unasync.py. Do not edit.\n"
SUBS = [
    (r"\basync def\b", "def"),
    (r"\basync with\b", "with"),
    (r"\bawait ", ""),
    (r"\b_async_client\b", "_client"),
    (r"\bAsyncHlthstack\b", "Hlthstack"),
    (r"\b_Async([A-Z]\w*)", r"_\1"),
    (r"\bAsync([A-Z]\w*)", r"\1"),
]


def generate() -> str:
    text = SOURCE.read_text()
    for pattern, replacement in SUBS:
        text = re.sub(pattern, replacement, text)
    return HEADER + text


def main() -> int:
    output = generate()
    if "--check" in sys.argv[1:]:
        if TARGET.read_text() != output:
            print(f"{TARGET.name} is out of date; run python scripts/unasync.py")
            return 1
        return 0
    TARGET.write_text(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
