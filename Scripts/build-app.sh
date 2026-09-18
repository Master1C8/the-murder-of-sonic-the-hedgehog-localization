#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-/private/tmp/murder-sonic-installer-swift-cache}"
export SWIFT_MODULECACHE_PATH="${SWIFT_MODULECACHE_PATH:-$CLANG_MODULE_CACHE_PATH}"
export SWIFTPM_MODULECACHE_OVERRIDE="${SWIFTPM_MODULECACHE_OVERRIDE:-$CLANG_MODULE_CACHE_PATH}"
scratch_root="${VN_SWIFT_SCRATCH_PATH:-$project_dir/.build-app}"
architectures=(arm64 x86_64)

for architecture in "${architectures[@]}"; do
  swift build \
    -c release \
    --disable-sandbox \
    --scratch-path "$scratch_root/$architecture" \
    --triple "${architecture}-apple-macosx14.0"
done

app="$project_dir/dist/Murder of Sonic — VN Revival.app"
legacy_app="$project_dir/dist/Murder of Sonic — Русский.app"
arm_binary="$scratch_root/arm64/out/Products/Release/MurderOfSonicLocalizationInstaller"
x86_binary="$scratch_root/x86_64/out/Products/Release/MurderOfSonicLocalizationInstaller"
resource_bundle="$scratch_root/arm64/out/Products/Release/MurderOfSonicLocalizationInstaller_MurderOfSonicLocalizationInstaller.bundle"
universal_binary="$scratch_root/MurderOfSonicLocalizationInstaller-universal"

lipo -create "$arm_binary" "$x86_binary" -output "$universal_binary"
rm -rf "$app" "$legacy_app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$universal_binary" "$app/Contents/MacOS/MurderOfSonicLocalizationInstaller"
cp -R "$resource_bundle" "$app/Contents/Resources/"
cp "$project_dir/App/Info.plist" "$app/Contents/Info.plist"
cp "$project_dir/App/App.icns" "$app/Contents/Resources/App.icns"
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"
echo "$app"
