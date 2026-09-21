#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
compiler="${WINDOWS_CC:-/opt/homebrew/bin/x86_64-w64-mingw32-gcc}"
resource_compiler="${WINDOWS_WINDRES:-/opt/homebrew/bin/x86_64-w64-mingw32-windres}"
image_converter="${MAGICK:-/opt/homebrew/bin/magick}"
resources="$project_dir/Windows/Resources"

for tool in "$compiler" "$resource_compiler" "$image_converter" /usr/bin/sips; do
  [[ -x "$tool" ]] || { echo "Required build tool is missing: $tool" >&2; exit 1; }
done
for required in "$resources/PackageConfig.json" "$resources/LocalizationPayload/BuildManifest.json" "$project_dir/Windows/install.ps1"; do
  [[ -f "$required" ]] || { echo "Required release input is missing: $required" >&2; exit 1; }
done

output_dir="$project_dir/Windows"
output="$output_dir/VN Revival Sonic Installer.exe"
work="$(mktemp -d "${TMPDIR:-/tmp}/sonic-windows-installer.XXXXXX")"
trap 'rm -rf "$work"' EXIT

/usr/bin/sips -s format png "$project_dir/App/App.icns" --out "$work/Game.png" >/dev/null
"$image_converter" "$work/Game.png" -define icon:auto-resize=256,128,64,48,32,16 "$work/Game.ico"
cp "$project_dir/Windows/Installer.manifest" "$work/Installer.manifest"
cp "$project_dir/Windows/Installer.rc" "$work/Installer.rc"
(
  cd "$work"
  "$resource_compiler" Installer.rc -O coff -o InstallerResources.o
)

"$compiler" \
  -std=c11 -O2 -Wall -Wextra -Werror -municode -mwindows \
  "$project_dir/Windows/MurderOfSonicInstaller.c" \
  "$work/InstallerResources.o" \
  -o "$output" \
  -lcomctl32 -lshell32 -lole32

file "$output" | grep -q 'PE32+ executable.*x86-64'
shasum -a 256 "$output" \
  "$project_dir/Windows/install.ps1" \
  "$resources/PackageConfig.json"
du -sh "$resources/LocalizationPayload"
