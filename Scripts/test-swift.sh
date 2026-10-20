#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
export DEVELOPER_DIR="${DEVELOPER_DIR:-$(xcode-select -p)}"
arguments=(--build-system native --disable-sandbox --no-parallel --disable-xctest)
frameworks="$DEVELOPER_DIR/Library/Developer/Frameworks"
if [[ -d "$frameworks/Testing.framework" ]]; then
  arguments+=(-Xswiftc -F -Xswiftc "$frameworks" -Xlinker -rpath -Xlinker "$frameworks")
fi
swift test "${arguments[@]}"
