#!/usr/bin/env python3
"""Digital signature tool for Python scripts.

Signs Python (.py) files with an X.509 certificate, embedding a detached
signature block as a trailing comment. Signatures can be verified to ensure
scripts haven't been tampered with after signing.

Usage:
    # Generate a signing certificate (first time):
    python sign-python.py generate-cert

    # Sign a script:
    python sign-python.py sign myscript.py

    # Sign all .py files in a directory:
    python sign-python.py sign mypackage/

    # Verify a signed script:
    python sign-python.py verify myscript.py

    # Verify all .py files in a directory:
    python sign-python.py verify mypackage/

    # Strip signature from a script:
    python sign-python.py strip myscript.py

    # Use a specific cert/key:
    python sign-python.py sign --cert mycert.pem --key mykey.pem myscript.py
"""

import argparse
import base64
import datetime
import hashlib
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

# Signature block markers
SIG_BEGIN = "# -----BEGIN SCRIPT SIGNATURE-----"
SIG_END = "# -----END SCRIPT SIGNATURE-----"
SIG_PATTERN = re.compile(
    rf"^{re.escape(SIG_BEGIN)}$.*?^{re.escape(SIG_END)}$",
    re.MULTILINE | re.DOTALL,
)

# Defaults
DEFAULT_CERT = "signing-cert.pem"
DEFAULT_KEY = "signing-key.pem"
DEFAULT_SUBJECT = "/C=US/ST=Virginia/L=Richmond/O=DLA/OU=IT/CN=Python Script Signer"
DEFAULT_DAYS = 3650


def strip_signature(content: str) -> str:
    """Remove any existing signature block from script content."""
    # Remove signature block and any trailing whitespace/newlines after it
    stripped = SIG_PATTERN.sub("", content)
    return stripped.rstrip("\n") + "\n"


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of the script content (without signature block)."""
    clean = strip_signature(content)
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def sign_content(content_hash: str, key_path: str) -> bytes:
    """Create an RSA signature of the content hash using openssl."""
    hash_bytes = content_hash.encode("utf-8")
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_path],
        input=hash_bytes,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"openssl signing failed: {result.stderr.decode()}")
    return result.stdout


def verify_signature(content_hash: str, signature_b64: str, cert_path: str) -> bool:
    """Verify an RSA signature against the content hash using openssl."""
    import tempfile

    sig_bytes = base64.b64decode(signature_b64)
    hash_bytes = content_hash.encode("utf-8")

    with tempfile.NamedTemporaryFile(suffix=".sig", delete=False) as sig_file:
        sig_file.write(sig_bytes)
        sig_path = sig_file.name

    try:
        # Extract public key from cert
        pubkey_result = subprocess.run(
            ["openssl", "x509", "-in", cert_path, "-pubkey", "-noout"],
            capture_output=True,
        )
        if pubkey_result.returncode != 0:
            raise RuntimeError(f"Failed to extract public key: {pubkey_result.stderr.decode()}")

        with tempfile.NamedTemporaryFile(suffix=".pub", delete=False, mode="wb") as pub_file:
            pub_file.write(pubkey_result.stdout)
            pub_path = pub_file.name

        try:
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", pub_path, "-signature", sig_path],
                input=hash_bytes,
                capture_output=True,
            )
            return result.returncode == 0
        finally:
            os.unlink(pub_path)
    finally:
        os.unlink(sig_path)


def build_signature_block(signature_b64: str, cert_path: str, filepath: str) -> str:
    """Build the signature comment block to embed in the script."""
    # Get cert fingerprint
    result = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-fingerprint", "-sha256", "-noout"],
        capture_output=True, text=True,
    )
    fingerprint = result.stdout.strip().split("=", 1)[-1] if result.returncode == 0 else "unknown"

    # Get cert subject
    result = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-subject", "-noout"],
        capture_output=True, text=True,
    )
    subject = result.stdout.strip().replace("subject=", "").strip() if result.returncode == 0 else "unknown"

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Wrap base64 signature to 76 chars per line
    wrapped_sig = "\n".join(f"# {line}" for line in textwrap.wrap(signature_b64, 76))

    block = f"""{SIG_BEGIN}
# Signer:      {subject}
# Fingerprint:  {fingerprint}
# Timestamp:   {timestamp}
# Algorithm:   RSA-SHA256
# File:        {os.path.basename(filepath)}
#
{wrapped_sig}
{SIG_END}"""
    return block


def extract_signature_b64(content: str) -> str | None:
    """Extract the base64 signature data from a signed script."""
    match = SIG_PATTERN.search(content)
    if not match:
        return None

    block = match.group(0)
    lines = block.split("\n")
    sig_lines = []
    for line in lines:
        stripped = line.lstrip("# ").strip()
        # Skip markers, metadata lines, and empty comment lines
        if line in (SIG_BEGIN, SIG_END) or ":" in stripped.split()[0] if stripped else True:
            continue
        # Check if it looks like base64
        if stripped and re.match(r'^[A-Za-z0-9+/=]+$', stripped):
            sig_lines.append(stripped)

    return "".join(sig_lines) if sig_lines else None


def find_python_files(path: str) -> list[Path]:
    """Find all .py files at the given path."""
    p = Path(path)
    if p.is_file() and p.suffix == ".py":
        return [p]
    elif p.is_dir():
        return sorted(p.rglob("*.py"))
    else:
        print(f"  [SKIP] Not a .py file: {path}")
        return []


# ===== Commands =====

def cmd_generate_cert(args):
    """Generate a self-signed certificate for script signing."""
    cert_path = args.cert
    key_path = args.key

    if os.path.exists(cert_path) and not args.force:
        print(f"Certificate already exists: {cert_path}")
        print("Use --force to overwrite.")
        return 1

    print(f"Generating self-signed certificate...")
    print(f"  Subject: {args.subject}")
    print(f"  Validity: {args.days} days")

    result = subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key_path,
        "-out", cert_path,
        "-days", str(args.days),
        "-subj", args.subject,
        "-sha256",
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  [ERROR] openssl failed: {result.stderr}")
        return 1

    os.chmod(key_path, 0o600)
    print(f"  Certificate: {cert_path}")
    print(f"  Private key: {key_path} (keep this secure!)")

    # Show cert info
    info = subprocess.run(
        ["openssl", "x509", "-in", cert_path, "-text", "-noout"],
        capture_output=True, text=True,
    )
    for line in info.stdout.split("\n")[:12]:
        print(f"  {line.strip()}")

    print("\nYou can now sign scripts with:")
    print(f"  python {sys.argv[0]} sign myscript.py")
    return 0


def cmd_sign(args):
    """Sign one or more Python scripts."""
    cert_path = args.cert
    key_path = args.key

    if not os.path.exists(cert_path):
        print(f"Certificate not found: {cert_path}")
        print(f"Run: python {sys.argv[0]} generate-cert")
        return 1
    if not os.path.exists(key_path):
        print(f"Private key not found: {key_path}")
        return 1

    files = []
    for target in args.targets:
        files.extend(find_python_files(target))

    if not files:
        print("No .py files found to sign.")
        return 1

    errors = 0
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")

            # Strip any existing signature
            clean_content = strip_signature(content)

            # Compute hash of clean content
            content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()

            # Sign the hash
            sig_bytes = sign_content(content_hash, key_path)
            sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

            # Build signature block
            sig_block = build_signature_block(sig_b64, cert_path, str(filepath))

            # Append signature to clean content
            signed_content = clean_content + "\n" + sig_block + "\n"
            filepath.write_text(signed_content, encoding="utf-8")

            print(f"  [SIGNED] {filepath}")

        except Exception as e:
            print(f"  [ERROR]  {filepath}: {e}")
            errors += 1

    print(f"\n{len(files) - errors}/{len(files)} files signed.")
    return 1 if errors else 0


def cmd_verify(args):
    """Verify signatures on one or more Python scripts."""
    cert_path = args.cert

    if not os.path.exists(cert_path):
        print(f"Certificate not found: {cert_path}")
        return 1

    files = []
    for target in args.targets:
        files.extend(find_python_files(target))

    if not files:
        print("No .py files found to verify.")
        return 1

    passed = 0
    failed = 0
    unsigned = 0

    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
            sig_b64 = extract_signature_b64(content)

            if sig_b64 is None:
                print(f"  [UNSIGNED] {filepath}")
                unsigned += 1
                continue

            content_hash = compute_hash(content)
            if verify_signature(content_hash, sig_b64, cert_path):
                print(f"  [VALID]    {filepath}")
                passed += 1
            else:
                print(f"  [INVALID]  {filepath} — signature does not match!")
                failed += 1

        except Exception as e:
            print(f"  [ERROR]    {filepath}: {e}")
            failed += 1

    print(f"\nResults: {passed} valid, {failed} invalid, {unsigned} unsigned")
    return 1 if failed else 0


def cmd_strip(args):
    """Strip signatures from one or more Python scripts."""
    files = []
    for target in args.targets:
        files.extend(find_python_files(target))

    if not files:
        print("No .py files found.")
        return 1

    for filepath in files:
        content = filepath.read_text(encoding="utf-8")
        if SIG_BEGIN in content:
            clean = strip_signature(content)
            filepath.write_text(clean, encoding="utf-8")
            print(f"  [STRIPPED] {filepath}")
        else:
            print(f"  [SKIP]    {filepath} (not signed)")

    return 0


# ===== CLI =====

def main():
    parser = argparse.ArgumentParser(
        description="Sign and verify Python scripts with X.509 certificates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s generate-cert
              %(prog)s sign app/adapter.py
              %(prog)s sign app/collectors/
              %(prog)s verify app/
              %(prog)s strip app/adapter.py
        """),
    )
    parser.add_argument("--cert", default=DEFAULT_CERT, help="Signing certificate (default: signing-cert.pem)")
    parser.add_argument("--key", default=DEFAULT_KEY, help="Private key (default: signing-key.pem)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate-cert
    gen_parser = subparsers.add_parser("generate-cert", help="Generate a self-signed signing certificate")
    gen_parser.add_argument("--subject", default=DEFAULT_SUBJECT, help="Certificate subject DN")
    gen_parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Validity in days (default: 3650)")
    gen_parser.add_argument("--force", action="store_true", help="Overwrite existing cert")

    # sign
    sign_parser = subparsers.add_parser("sign", help="Sign Python scripts")
    sign_parser.add_argument("targets", nargs="+", help="Files or directories to sign")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify script signatures")
    verify_parser.add_argument("targets", nargs="+", help="Files or directories to verify")

    # strip
    strip_parser = subparsers.add_parser("strip", help="Remove signatures from scripts")
    strip_parser.add_argument("targets", nargs="+", help="Files or directories to strip")

    args = parser.parse_args()

    commands = {
        "generate-cert": cmd_generate_cert,
        "sign": cmd_sign,
        "verify": cmd_verify,
        "strip": cmd_strip,
    }

    sys.exit(commands[args.command](args))


if __name__ == "__main__":
    main()
