"""Smoke test for IndicTrans2 en↔ur (requires HF access + deps). Run from repo Backend folder:

  cd Backend
  python test_indictrans2.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PYTHONUTF8", "1")


def main() -> None:
    from app.services.translation_service import translate_en_to_ur, translate_ur_to_en

    en = "The contract shall terminate upon breach of payment terms."
    ur = translate_en_to_ur(en)
    print("EN:", en)
    print("UR:", ur)
    print()

    back = translate_ur_to_en(ur)
    print("UR (input):", ur[:200] + ("…" if len(ur) > 200 else ""))
    print("EN (round-trip):", back)
    print()
    print("OK" if ur.strip() and back.strip() else "FAIL (empty output)")


if __name__ == "__main__":
    main()
