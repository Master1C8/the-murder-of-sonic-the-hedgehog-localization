#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"
config="$project_dir/Sources/MurderOfSonicLocalizationInstaller/Resources/PackageConfig.json"

jq -e '.schemaVersion == 2 and .sourceLocale == "en" and (.languages | length == 30)' "$config" >/dev/null
find Sources -name '*.json' -type f -print0 | xargs -0 -n1 jq empty
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/murder-sonic-localization-pycache}" \
  python3 -m unittest discover -s Tests -p 'test_*.py'

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-/private/tmp/murder-sonic-installer-swift-cache}"
export SWIFT_MODULECACHE_PATH="${SWIFT_MODULECACHE_PATH:-$CLANG_MODULE_CACHE_PATH}"
export SWIFTPM_MODULECACHE_OVERRIDE="${SWIFTPM_MODULECACHE_OVERRIDE:-$CLANG_MODULE_CACHE_PATH}"
swift test --disable-sandbox

if [[ "${ALLOW_INCOMPLETE_PAYLOAD:-0}" != "1" ]]; then
  jq -e '.payloadReady == true and (.files | length > 0) and all(.languages[]; .ready == true)' "$config" >/dev/null || {
    echo 'Release blocked: the unified 30-language payload is intentionally not ready.' >&2
    exit 1
  }
fi

"$project_dir/Scripts/build-app.sh"
