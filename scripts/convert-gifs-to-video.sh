#!/bin/bash
# Script para convertir GIFs pesados a video MP4
# Reducción esperada: 70-80% del tamaño original

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEMO_DIR="static/images/demo"

echo -e "${GREEN}🎬 Convirtiendo GIFs a MP4...${NC}\n"

# GIFs a convertir
GIFS=(
    "paso1.gif"
    "paso2.gif"
    "paso3.gif"
    "crecimiento.gif"
)

total_before=0
total_after=0

for gif in "${GIFS[@]}"; do
    gif_path="$DEMO_DIR/$gif"
    mp4_path="$DEMO_DIR/${gif%.gif}.mp4"

    if [ ! -f "$gif_path" ]; then
        echo -e "${YELLOW}⚠️  No existe: $gif_path${NC}"
        continue
    fi

    # Tamaño original
    size_before=$(stat -c%s "$gif_path" 2>/dev/null || stat -f%z "$gif_path")
    size_before_mb=$(echo "scale=2; $size_before/1024/1024" | bc)

    echo -e "${BLUE}🔄 Convirtiendo: $gif → ${gif%.gif}.mp4${NC}"
    echo "   Tamaño GIF: ${size_before_mb}MB"

    # Convertir GIF a MP4
    # -movflags faststart: Optimiza para streaming web
    # -pix_fmt yuv420p: Formato compatible con todos los navegadores
    # -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2": Asegura dimensiones pares
    # -b:v 1M: Bitrate de 1Mbps (balance calidad/tamaño)
    # -crf 28: Factor de calidad (18-28 es buen rango, 28=menor tamaño)
    # -an: Sin audio

    ffmpeg -i "$gif_path" \
        -movflags faststart \
        -pix_fmt yuv420p \
        -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
        -c:v libx264 \
        -crf 28 \
        -preset slow \
        -an \
        -y \
        "$mp4_path" \
        2>&1 | grep -E "(frame|Stream|Duration)" | tail -3

    if [ ! -f "$mp4_path" ]; then
        echo -e "${YELLOW}❌ Error al convertir $gif${NC}"
        continue
    fi

    # Tamaño nuevo
    size_after=$(stat -c%s "$mp4_path" 2>/dev/null || stat -f%z "$mp4_path")
    size_after_mb=$(echo "scale=2; $size_after/1024/1024" | bc)
    reduction=$(echo "scale=1; ($size_before - $size_after) * 100 / $size_before" | bc)

    echo "   Tamaño MP4: ${size_after_mb}MB"
    echo -e "   ${GREEN}✅ Reducción: ${reduction}%${NC}\n"

    total_before=$((total_before + size_before))
    total_after=$((total_after + size_after))
done

# Resumen
total_before_mb=$(echo "scale=2; $total_before/1024/1024" | bc)
total_after_mb=$(echo "scale=2; $total_after/1024/1024" | bc)
total_reduction=$(echo "scale=1; ($total_before - $total_after) * 100 / $total_before" | bc)
saved_mb=$(echo "scale=2; $total_before_mb - $total_after_mb" | bc)

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 RESUMEN DE CONVERSIÓN${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Total GIFs:        ${total_before_mb}MB"
echo "Total MP4s:        ${total_after_mb}MB"
echo -e "Ahorro:            ${GREEN}${saved_mb}MB (${total_reduction}%)${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n${YELLOW}📝 NOTA: Los archivos GIF originales se mantienen como fallback${NC}"
echo -e "${GREEN}✅ Conversión completada${NC}\n"
