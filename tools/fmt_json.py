#!/usr/bin/env python3
"""Re-format content/*.json in the house style: objects indented, short arrays
and small objects kept on one line, so entries stay easy to edit by hand.

    python3 tools/fmt_json.py            # every file in content/
    python3 tools/fmt_json.py press      # just content/press.json
"""
import json
import pathlib
import sys

CONTENT = pathlib.Path(__file__).resolve().parent.parent / "content"
WIDTH = 118


def inline(v):
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def fmt(v, ind=0):
    pad, sub = "  " * ind, "  " * (ind + 1)
    one = inline(v)
    if not isinstance(v, (dict, list)) or len(one) + len(pad) <= WIDTH and "\n" not in one and (
            isinstance(v, list) and all(not isinstance(x, (dict, list)) or len(inline(x)) < 60 for x in v)
            or isinstance(v, dict) and all(not isinstance(x, (dict, list)) for x in v.values())
            or isinstance(v, dict) and set(v) <= {"en", "ko"}):
        return one
    if isinstance(v, list):
        return "[\n" + ",\n".join(sub + fmt(x, ind + 1) for x in v) + "\n" + pad + "]"
    return "{\n" + ",\n".join(f"{sub}{json.dumps(k, ensure_ascii=False)}: {fmt(x, ind + 1)}" for k, x in v.items()) + "\n" + pad + "}"


def main(names):
    files = [CONTENT / f"{n}.json" for n in names] if names else sorted(CONTENT.glob("*.json"))
    for f in files:
        data = json.loads(f.read_text("utf-8"))
        f.write_text(fmt(data) + "\n", "utf-8")
        print("formatted", f.relative_to(CONTENT.parent))


if __name__ == "__main__":
    main(sys.argv[1:])
