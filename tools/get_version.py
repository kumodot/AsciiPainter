"""Print the VERSION string of an ASCIIPAINT_v*.py file (used by the .bat build scripts)."""
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
print(m.group(1) if m else "dev")
