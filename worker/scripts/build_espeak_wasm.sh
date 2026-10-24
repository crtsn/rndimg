#!/bin/bash
# Builds worker/src/speech.{js,wasm}: espeak-ng (English-only data, klatt) +
# libopus, linked into one Emscripten module with the data embedded.
#
# Requirements (macOS): homebrew emscripten, autoconf, automake, libtool,
# espeak-ng (for the prebuilt espeak-ng-data of the SAME version).
set -euo pipefail

ESPEAK_VERSION=1.52.0
OPUS_VERSION=1.5.2
WORKDIR="${1:-$(mktemp -d)}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/src"

cd "$WORKDIR"

if [ ! -d espeak-ng ]; then
	git clone --depth 1 --branch "$ESPEAK_VERSION" https://github.com/espeak-ng/espeak-ng.git
fi
if [ ! -d "opus-$OPUS_VERSION" ]; then
	curl -sL -o opus.tar.gz "https://github.com/xiph/opus/releases/download/v$OPUS_VERSION/opus-$OPUS_VERSION.tar.gz"
	tar xzf opus.tar.gz
fi

# --- espeak-ng: cross-configure and build the static lib -------------------
cd espeak-ng
if [ !f Makefile ] 2>/dev/null || [ ! -f Makefile ]; then
	export PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH"
	./autogen.sh
	emconfigure ./configure --without-async --without-mbrola --without-pcaudiolib --without-sonic --disable-shared --enable-static
fi

# Compatibility patch for emscripten >= 6 (musl sysroot declares isw*, which
# espeak-ng's compat macros would collide with). Idempotent.
if ! grep -q '__EMSCRIPTEN__' src/include/compat/wctype.h; then
	python3 - <<'EOF'
path = 'src/include/compat/wctype.h'
src = open(path).read()
old = '#define iswalnum  ucd_isalnum'
new = '#ifndef __EMSCRIPTEN__\n#define iswalnum  ucd_isalnum'
src = src.replace(old, new, 1)
src = src.replace('#define toupper udc_toupper', '#define toupper udc_toupper\n#endif', 1)
open(path, 'w').write(src)
EOF
fi

# English-only data from the brew install of the same version.
if [ ! -d espeak-ng-data ]; then
	SRC="$(brew --prefix)/share/espeak-ng-data"
	mkdir -p espeak-ng-data/voices espeak-ng-data/lang/gmw
	cp "$SRC/phondata" "$SRC/phonindex" "$SRC/phontab" "$SRC/intonations" "$SRC/phondata-manifest" "$SRC/en_dict" espeak-ng-data/
	cp -R "$SRC/voices/!v" espeak-ng-data/voices/
	cp "$SRC"/lang/gmw/en "$SRC"/lang/gmw/en-029 "$SRC"/lang/gmw/en-GB-scotland "$SRC"/lang/gmw/en-GB-x-gbclan "$SRC"/lang/gmw/en-GB-x-gbcwmd "$SRC"/lang/gmw/en-GB-x-rp "$SRC"/lang/gmw/en-US "$SRC"/lang/gmw/en-US-nyc espeak-ng-data/lang/gmw/
fi

emmake make src/libespeak-ng.la -j"$(sysctl -n hw.ncpu)"
cd ..

# --- libopus: static lib ----------------------------------------------------
cd "opus-$OPUS_VERSION"
if [ ! -f Makefile ]; then
	emconfigure ./configure --disable-shared --enable-static --disable-doc --disable-extra-programs --disable-rtcd
fi
emmake make -j"$(sysctl -n hw.ncpu)"
cd ..

# --- shim + link ------------------------------------------------------------
if [ ! -f speech_shim.c ]; then
	echo "speech_shim.c missing; it lives next to this script in git" >&2
	exit 1
fi

emcc -c speech_shim.c -Iespeak-ng/src/include -Iespeak-ng/src/ucd-tools/src/include -I"opus-$OPUS_VERSION/include" -O3 -o speech_shim.o
em++ speech_shim.o espeak-ng/src/.libs/libespeak-ng.a "opus-$OPUS_VERSION/.libs/libopus.a" \
	-O3 -o "$OUT/speech.js" \
	--embed-file espeak-ng/espeak-ng-data@/espeak-ng-data \
	-s MODULARIZE=1 -s EXPORT_ES6=1 -s ENVIRONMENT=web -s ALLOW_MEMORY_GROWTH=1 \
	-s EXPORTED_FUNCTIONS=_sp_init,_sp_set_voice,_sp_synth,_sp_rate,_sp_probe,_sp_packet_count,_sp_packet_bytes,_sp_packet_data,_sp_packet_sizes \
	-s EXPORTED_RUNTIME_METHODS=ccall,HEAPU8,HEAP32 -s FILESYSTEM=1 --no-entry

echo "built $OUT/speech.js + $OUT/speech.wasm"
