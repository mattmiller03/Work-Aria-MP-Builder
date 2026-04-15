#!/bin/bash
# ============================================================================
# Aria Operations Management Pack — PAK Signing Script
#
# Signs a .pak file with a custom X.509 certificate in the same format
# VMware uses for their official management packs (signature.cert + signature.mf).
#
# Usage:
#   # First time — generate a signing certificate:
#   ./sign-pak.sh --generate-cert
#
#   # Sign a pak file:
#   ./sign-pak.sh path/to/your.pak
#
#   # Sign with a specific cert/key:
#   ./sign-pak.sh --cert mycert.pem --key mykey.pem path/to/your.pak
#
# Requirements: openssl, zip, sha1sum (or shasum on macOS)
# ============================================================================

set -euo pipefail

# Defaults
CERT_FILE="signing-cert.pem"
KEY_FILE="signing-key.pem"
CERT_SUBJECT="/C=US/ST=Virginia/L=Richmond/O=DLA/OU=IT/CN=Aria Ops Custom Pak Signer"
CERT_DAYS=3650  # 10 years

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---------- SHA1 helper (works on Linux and macOS) ----------
sha1_hash() {
    if command -v sha1sum &>/dev/null; then
        sha1sum "$1" | awk '{print $1}'
    elif command -v shasum &>/dev/null; then
        shasum -a 1 "$1" | awk '{print $1}'
    else
        openssl dgst -sha1 "$1" | awk '{print $NF}'
    fi
}

# ---------- Generate signing certificate ----------
generate_cert() {
    info "Generating self-signed certificate for pak signing..."
    info "Subject: $CERT_SUBJECT"
    info "Validity: $CERT_DAYS days"

    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -days "$CERT_DAYS" \
        -subj "$CERT_SUBJECT" \
        -sha256 2>/dev/null

    chmod 600 "$KEY_FILE"

    info "Certificate generated:"
    info "  Certificate: $CERT_FILE"
    info "  Private key: $KEY_FILE (keep this secure!)"
    echo ""
    openssl x509 -in "$CERT_FILE" -text -noout | head -15
    echo ""
    info "You can now sign paks with: $0 path/to/your.pak"
}

# ---------- Sign a pak file ----------
sign_pak() {
    local PAK_FILE="$1"

    # Validate inputs
    [[ -f "$PAK_FILE" ]] || error "Pak file not found: $PAK_FILE"
    [[ -f "$CERT_FILE" ]] || error "Certificate not found: $CERT_FILE (run $0 --generate-cert first)"
    [[ -f "$KEY_FILE" ]] || error "Private key not found: $KEY_FILE"

    # Verify it's a zip file
    file "$PAK_FILE" | grep -qi "zip" || warn "File may not be a valid pak/zip archive"

    info "Signing pak: $PAK_FILE"

    # Create temp working directory
    WORK_DIR=$(mktemp -d)
    trap "rm -rf $WORK_DIR" EXIT

    # Extract pak
    info "Extracting pak..."
    unzip -q "$PAK_FILE" -d "$WORK_DIR/pak"

    # Remove any existing signature files
    rm -f "$WORK_DIR/pak/signature.cert" "$WORK_DIR/pak/signature.mf"

    # Generate SHA1 manifest
    info "Computing SHA1 hashes..."
    MANIFEST="$WORK_DIR/pak/signature.mf"

    cd "$WORK_DIR/pak"
    # Find all files (excluding signature files), compute hashes
    find . -type f -not -name "signature.cert" -not -name "signature.mf" | sort | while read -r filepath; do
        # Strip leading ./
        relative="${filepath#./}"
        hash=$(sha1_hash "$filepath")
        echo "SHA1($relative)= $hash"
    done > "$MANIFEST"

    info "Manifest has $(wc -l < "$MANIFEST") entries"

    # Copy certificate into pak
    cp "$CERT_FILE" "$WORK_DIR/pak/signature.cert"

    # Rebuild the pak with signature files
    info "Rebuilding signed pak..."
    SIGNED_PAK="$(cd "$(dirname "$PAK_FILE")" && pwd)/$(basename "$PAK_FILE")"

    # Remove original and re-create
    rm -f "$SIGNED_PAK"
    cd "$WORK_DIR/pak"
    zip -r -q "$SIGNED_PAK" .

    cd - > /dev/null

    info "Signed pak written to: $SIGNED_PAK"
    echo ""

    # Verify
    info "Verification:"
    unzip -l "$SIGNED_PAK" | grep -E "signature\.(cert|mf)" || warn "Signature files not found in pak!"
    echo ""
    info "Manifest preview:"
    head -5 "$MANIFEST"
    echo "  ... ($(wc -l < "$MANIFEST") total entries)"
    echo ""
    info "Done. Test installing this pak WITHOUT 'ignore unsigned' to see if Aria Ops accepts it."
    warn "If Aria Ops rejects the custom cert, you may need to add it to the appliance trust store."
    warn "Check: /usr/lib/vmware-vcops/user/conf/ssl/ or /etc/vmware-vcops/ on the Aria Ops node."
}

# ---------- Parse arguments ----------
GENERATE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --generate-cert)
            GENERATE=true
            shift
            ;;
        --cert)
            CERT_FILE="$2"
            shift 2
            ;;
        --key)
            KEY_FILE="$2"
            shift 2
            ;;
        --subject)
            CERT_SUBJECT="$2"
            shift 2
            ;;
        --days)
            CERT_DAYS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS] [pak-file]"
            echo ""
            echo "Options:"
            echo "  --generate-cert     Generate a new self-signed signing certificate"
            echo "  --cert FILE         Path to signing certificate (default: signing-cert.pem)"
            echo "  --key FILE          Path to private key (default: signing-key.pem)"
            echo "  --subject SUBJECT   Certificate subject DN (for --generate-cert)"
            echo "  --days DAYS         Certificate validity in days (default: 3650)"
            echo ""
            echo "Examples:"
            echo "  $0 --generate-cert"
            echo "  $0 build/MyAdapter-1.0.0.pak"
            echo "  $0 --cert org-cert.pem --key org-key.pem build/MyAdapter-1.0.0.pak"
            exit 0
            ;;
        *)
            PAK_INPUT="$1"
            shift
            ;;
    esac
done

if $GENERATE; then
    generate_cert
elif [[ -n "${PAK_INPUT:-}" ]]; then
    sign_pak "$PAK_INPUT"
else
    echo "Usage: $0 --generate-cert | $0 [--cert FILE --key FILE] <pak-file>"
    echo "Run $0 --help for details."
    exit 1
fi
