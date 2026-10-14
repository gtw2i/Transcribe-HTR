#!/usr/bin/env bash
# Sign and notarize a macOS .app or .dmg -- or do nothing when no Apple
# credentials are configured (the PyInstaller ad-hoc signature stays; see
# DESKTOP_PLAN.md, "Unsigned builds").
#
#   packaging/sign/sign_macos.sh app path/to/Transcribe-HTR.app
#   packaging/sign/sign_macos.sh dmg path/to/Transcribe-HTR.dmg
#
# Environment (all required to sign):
#   APPLE_SIGNING_IDENTITY   "Developer ID Application: <Name> (<TEAMID>)"
#   APPLE_CERT_P12_BASE64    the Developer ID certificate + key (.p12, base64)
#   APPLE_CERT_PASSWORD      its password
#   APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD   for notarytool
set -euo pipefail

kind="$1"; target="$2"
if [[ -z "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  echo "macOS signing skipped: APPLE_SIGNING_IDENTITY is not set (ad-hoc signed build)."
  exit 0
fi

here="$(cd "$(dirname "$0")" && pwd)"

# Import the certificate into a throwaway keychain (CI has no login keychain).
keychain="$RUNNER_TEMP/htr-signing.keychain-db"
security create-keychain -p "" "$keychain"
security set-keychain-settings -lut 3600 "$keychain"
security unlock-keychain -p "" "$keychain"
echo "$APPLE_CERT_P12_BASE64" | base64 --decode > "$RUNNER_TEMP/cert.p12"
security import "$RUNNER_TEMP/cert.p12" -k "$keychain" -P "$APPLE_CERT_PASSWORD" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple: -s -k "" "$keychain" >/dev/null
security list-keychains -d user -s "$keychain" $(security list-keychains -d user | tr -d '"')

sign() {
  codesign --force --timestamp --options runtime \
    --entitlements "$here/entitlements.plist" --keychain "$keychain" \
    --sign "$APPLE_SIGNING_IDENTITY" "$@"
}

notarize() {
  xcrun notarytool submit "$1" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" --wait
}

case "$kind" in
  app)
    # Inside-out: every nested binary first, then the bundle itself.
    find "$target/Contents" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -111 \) -print0 |
      while IFS= read -r -d '' f; do
        if file "$f" | grep -q "Mach-O"; then sign "$f"; fi
      done
    sign "$target"
    codesign --verify --deep --strict --verbose=2 "$target"
    zip="$RUNNER_TEMP/notarize-app.zip"
    ditto -c -k --keepParent "$target" "$zip"
    notarize "$zip"
    xcrun stapler staple "$target"
    ;;
  dmg)
    codesign --force --timestamp --keychain "$keychain" --sign "$APPLE_SIGNING_IDENTITY" "$target"
    notarize "$target"
    xcrun stapler staple "$target"
    ;;
  *) echo "usage: $0 app|dmg PATH" >&2; exit 2 ;;
esac
echo "Signed and notarized $target"
