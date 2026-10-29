#!/usr/bin/env bash
# hwp2hwpx(neolord0, Apache-2.0)를 소스에서 빌드해 vendor/hwp2hwpx-cli.jar 하나로 묶는다.
# 의존 jar는 Maven Central에서 받아 SHA-1을 검증한다. Maven 없이 javac만 사용.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor"
HWP2HWPX_COMMIT="62d95b980a4e3a6766877dd3fb6f7f45f4afcf3d"   # 2026-10-26 main
declare -A JARS=(
  [hwplib-1.1.10.jar]="kr/dogfoot/hwplib/1.1.10/hwplib-1.1.10.jar 64335f538b584957a0860d16c09ba47285b65e3a"
  [hwpxlib-1.0.9.jar]="kr/dogfoot/hwpxlib/1.0.9/hwpxlib-1.0.9.jar e10a0d019d0d7d3b449e7fd2b78cf1fcdb28b011"
)

mkdir -p "$VENDOR/lib" "$VENDOR/src"

for name in "${!JARS[@]}"; do
  read -r path sha <<<"${JARS[$name]}"
  dest="$VENDOR/lib/$name"
  if [[ ! -f "$dest" ]]; then
    echo "download $name"
    curl -fsSL "https://repo1.maven.org/maven2/$path" -o "$dest"
  fi
  echo "$sha  $dest" | sha1sum -c --quiet
done

SRC="$VENDOR/src/hwp2hwpx-$HWP2HWPX_COMMIT"
if [[ ! -d "$SRC" ]]; then
  echo "download hwp2hwpx@$HWP2HWPX_COMMIT"
  mkdir -p "$SRC"
  curl -fsSL "https://codeload.github.com/neolord0/hwp2hwpx/tar.gz/$HWP2HWPX_COMMIT" \
    | tar xz -C "$SRC" --strip-components=1
fi

BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
CP="$VENDOR/lib/hwplib-1.1.10.jar:$VENDOR/lib/hwpxlib-1.0.9.jar"

find "$SRC/src/main/java" -name '*.java' > "$BUILD/sources.txt"
echo "$ROOT/tools/hwp2hwpx/Hwp2HwpxCli.java" >> "$BUILD/sources.txt"
javac -encoding UTF-8 -nowarn -d "$BUILD/classes" -cp "$CP" @"$BUILD/sources.txt"

# 의존 jar를 풀어 하나의 실행 jar로 묶는다
(cd "$BUILD/classes" && for j in "$VENDOR"/lib/*.jar; do jar xf "$j"; done && rm -rf META-INF)
printf 'Main-Class: Hwp2HwpxCli\n' > "$BUILD/manifest.txt"
jar cfm "$VENDOR/hwp2hwpx-cli.jar" "$BUILD/manifest.txt" -C "$BUILD/classes" .
echo "built $VENDOR/hwp2hwpx-cli.jar"
