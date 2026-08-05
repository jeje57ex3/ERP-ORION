#!/usr/bin/env python3
"""Rendu de template minimal : remplace __KEY__ par une valeur littérale.
Usage : _render.py TEMPLATE OUTPUT KEY=VALUE [KEY=@fichier ...]
Une valeur préfixée par '@' est lue depuis un fichier (utile pour un blob
base64 trop volumineux/dangereux à passer en argument shell/sed).
"""
import pathlib
import sys


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 1

    template_path, output_path, *kvs = sys.argv[1:]
    text = pathlib.Path(template_path).read_text(encoding="utf-8")

    for kv in kvs:
        key, _, value = kv.partition("=")
        if value.startswith("@"):
            value = pathlib.Path(value[1:]).read_text(encoding="utf-8").strip()
        text = text.replace(f"__{key}__", value)

    pathlib.Path(output_path).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
