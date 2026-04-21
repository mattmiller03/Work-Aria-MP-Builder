"""Scrub sensitive data from log files before committing.

Usage:
    python scrub.py <input_file> [output_file]     # single file
    python scrub.py <input_dir>  [output_dir]      # every file in a folder
    python scrub.py -r <input_dir> [output_dir]    # recurse into subfolders

Add hostnames, IPs, and other sensitive strings to REPLACEMENTS below.

File/dir behavior:
- Single file, no output: overwrite in place.
- Single file, with output: write scrubbed copy to output path.
- Directory, no output: scrub each file in place.
- Directory, with output: mirror the tree under output.
- Binary files (non-decodable as UTF-8) are skipped with a notice.
"""

import os
import re
import sys

# ============================================================
# Add your sensitive values here — these get replaced
# ============================================================
REPLACEMENTS = {
    # Hostnames
    "DAISV0TP003": "ARIAOPS-NODE",
    "DAISV0TP004": "CLOUD-PROXY",
    "daisv0tp003": "ariaops-node",
    "daisv0tp004": "cloud-proxy",

    # Internal domain / site names — catches FQDNs the hostname replace missed
    ".dev-test.dla.mil": ".INTERNAL-DOMAIN",
    "dev-test.dla.mil":  "INTERNAL-DOMAIN",
    "dla.mil":           "INTERNAL-DOMAIN",
    "dev-test":          "SITE",

    # IPs — exact match, or use x / * as octet wildcards
    "214.73.76.134": "MP-BUILDER-IP",
    "214.73.76.149": "CLOUD-PROXY-IP",
    "214.73.x.x": "INTERNAL-IP",   # matches 192.168.1.5, 192.168.200.17, etc.
    # "10.*.*.*":    "RFC1918-IP",    # * and x both work as wildcards

    # Usernames
    "vropsssh": "svcaccount",

    # Azure tenant/subscription — add if needed
     "6dee1d83-8de8-49bb-bc0d-fd8812473904": "TENANT-ID",
     "988779d0-a914-4d28-8db2-56ae35c26853": "SUB-ID",
     "a3e73c56-50f4-401e-8695-791bc44afed5": "SUB-ID-2",
}


# Detects patterns like 192.168.x.x, 10.*.*.*, 172.16.x.100 — four octets where each
# octet is digits, 'x', 'X', or '*'. Anything else is treated as a literal string.
_IP_WILDCARD_RE = re.compile(r'[\dxX*]{1,3}(\.[\dxX*]{1,3}){3}')


def _compile_if_ip_pattern(key):
    """Return a compiled regex if key looks like an IP wildcard pattern, else None."""
    if not _IP_WILDCARD_RE.fullmatch(key):
        return None
    pat = re.escape(key)                       # escapes dots; x/X pass through; * → \*
    pat = pat.replace('x', r'\d{1,3}')
    pat = pat.replace('X', r'\d{1,3}')
    pat = pat.replace(r'\*', r'\d{1,3}')
    return re.compile(r'\b' + pat + r'\b')


def scrub(text):
    for sensitive, placeholder in REPLACEMENTS.items():
        regex = _compile_if_ip_pattern(sensitive)
        if regex is not None:
            text = regex.sub(placeholder, text)
        else:
            text = text.replace(sensitive, placeholder)

    # Also catch any IP addresses not in the list (x.x.x.x pattern)
    # Uncomment the next line to replace ALL IPs:
    # text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', 'X.X.X.X', text)

    return text


def scrub_file(input_file, output_file):
    """Scrub a single file. Returns True if written, False if skipped."""
    try:
        with open(input_file, "rb") as f:
            raw = f.read()
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        print(f"  [SKIP] {input_file} (binary / not UTF-8)")
        return False

    scrubbed = scrub(content)

    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(scrubbed)
    print(f"  [OK]   {input_file} -> {output_file}")
    return True


def iter_files(root, recursive):
    # Never scrub this script itself — that would turn REPLACEMENTS into a no-op dict.
    self_path = os.path.abspath(__file__)
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                path = os.path.join(dirpath, name)
                if os.path.abspath(path) == self_path:
                    continue
                yield path
    else:
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isfile(path):
                continue
            if os.path.abspath(path) == self_path:
                continue
            yield path


def main():
    args = sys.argv[1:]
    recursive = False
    if args and args[0] in ("-r", "--recursive"):
        recursive = True
        args = args[1:]

    if not args:
        print((__doc__ or "Usage: python scrub.py <input> [output]").strip())
        sys.exit(1)

    input_path = args[0]
    output_path = args[1] if len(args) > 1 else None

    if os.path.isfile(input_path):
        out = output_path if output_path else input_path
        scrub_file(input_path, out)
        return

    if not os.path.isdir(input_path):
        print(f"ERROR: {input_path} is not a file or directory")
        sys.exit(1)

    scrubbed = 0
    skipped = 0
    for src in iter_files(input_path, recursive):
        if output_path:
            rel = os.path.relpath(src, input_path)
            dst = os.path.join(output_path, rel)
        else:
            dst = src
        if scrub_file(src, dst):
            scrubbed += 1
        else:
            skipped += 1

    print(f"\nDone: {scrubbed} scrubbed, {skipped} skipped "
          f"({len(REPLACEMENTS)} replacement patterns)")


if __name__ == "__main__":
    main()
