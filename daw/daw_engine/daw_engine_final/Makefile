# ────────────────────────────────────────────────────────────
#  Makefile — DAW Engine
#
#  Uso:
#    make              → release
#    make debug        → com símbolos
#    make clean        → remove build
#    make check        → compila + testa bridge
#
#  Pré-requisito: baixe miniaudio.h antes de compilar:
#    curl -o src/miniaudio.h \
#      https://raw.githubusercontent.com/mackron/miniaudio/master/miniaudio.h
# ────────────────────────────────────────────────────────────

CC      = gcc
SRC     = src/daw_engine.c
INC     = -I src
OUTDIR  = bin

# ── Detecta plataforma ──────────────────────────────────────
UNAME := $(shell uname -s 2>/dev/null || echo Windows)

ifeq ($(UNAME), Linux)
    TARGET  = $(OUTDIR)/daw_engine.so
    LDFLAGS = -shared -fPIC -lpthread -lm -ldl
    PYLIB   = daw_engine.so
endif
ifeq ($(UNAME), Darwin)
    TARGET  = $(OUTDIR)/daw_engine.dylib
    LDFLAGS = -dynamiclib -lpthread -lm
    PYLIB   = daw_engine.dylib
endif
ifeq ($(UNAME), Windows)
    TARGET  = $(OUTDIR)/daw_engine.dll
    LDFLAGS = -shared -lwinmm -lole32 -ldsound
    PYLIB   = daw_engine.dll
endif

CFLAGS_RELEASE = -O2 -Wall -Wextra
CFLAGS_DEBUG   = -O0 -g3 -Wall -Wextra -DDAW_DEBUG

.PHONY: all release debug clean check miniaudio

all: check_miniaudio $(TARGET)

release: all

debug: CFLAGS_RELEASE = $(CFLAGS_DEBUG)
debug: all
	@echo "  [debug build]"

$(OUTDIR):
	mkdir -p $(OUTDIR)

$(TARGET): $(SRC) src/daw_engine.h src/miniaudio.h | $(OUTDIR)
	@echo "  CC  $@"
	$(CC) $(CFLAGS_RELEASE) $(INC) $(LDFLAGS) -o $@ $(SRC)
	@echo "  ✅  $(TARGET)"

check_miniaudio:
	@if [ ! -f src/miniaudio.h ]; then \
	    echo ""; \
	    echo "  ⚠  src/miniaudio.h não encontrado!"; \
	    echo "     Baixe com:"; \
	    echo "       curl -o src/miniaudio.h https://raw.githubusercontent.com/mackron/miniaudio/master/miniaudio.h"; \
	    echo ""; \
	    echo "  (usando stub para compilação sem rede)"; \
	fi

check: all
	@echo ""
	@echo "  Testando bridge Python..."
	python3 python/daw_bridge.py

clean:
	rm -f $(OUTDIR)/daw_engine.so \
	       $(OUTDIR)/daw_engine.dylib \
	       $(OUTDIR)/daw_engine.dll
	@echo "  ✅  limpo"
