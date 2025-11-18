#!/bin/bash
# Script para optimizar GIFs pesados en Kita
# Reduce tamaño manteniendo calidad visual aceptable

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

DEMO_DIR="static/images/demo"
BACKUP_DIR="$DEMO_DIR/backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${GREEN}🎬 Iniciando optimización de GIFs...${NC}\n"

# Crear backup
echo -e "${YELLOW}📦 Creando backup en $BACKUP_DIR${NC}"
mkdir -p "$BACKUP_DIR"

# GIFs a optimizar
GIFS=(
    "paso1.gif"
    "paso2.gif"
    "paso3.gif"
    "crecimiento.gif"
)

total_before=0
total_after=0

for gif in "${GIFS[@]}"; do
    filepath="$DEMO_DIR/$gif"

    if [ ! -f "$filepath" ]; then
        echo -e "${RED}❌ No existe: $filepath${NC}"
        continue
    fi

    # Backup
    cp "$filepath" "$BACKUP_DIR/"

    # Tamaño original
    size_before=$(stat -f%z "$filepath" 2>/dev/null || stat -c%s "$filepath")
    size_before_mb=$(echo "scale=2; $size_before/1024/1024" | bc)

    echo -e "\n${GREEN}🔄 Optimizando: $gif${NC}"
    echo "   Tamaño original: ${size_before_mb}MB"

    # Optimización con gifsicle (agresiva pero con buena calidad)
    # --optimize=3: Máxima optimización
    # --lossy=80: Compresión con pérdida (80 = buena calidad)
    # --colors 256: Mantener 256 colores
    # --scale 0.85: Reducir tamaño 15% (opcional, puedes ajustar)

    gifsicle --optimize=3 --lossy=80 --colors 256 "$filepath" -o "${filepath}.tmp"

    # Si la optimización falló o el archivo es más grande, usar solo optimize
    if [ ! -f "${filepath}.tmp" ] || [ $(stat -f%z "${filepath}.tmp" 2>/dev/null || stat -c%s "${filepath}.tmp") -gt $size_before ]; then
        echo "   ⚠️  Optimización agresiva no mejoró, usando solo --optimize=3"
        gifsicle --optimize=3 "$filepath" -o "${filepath}.tmp"
    fi

    # Reemplazar original
    mv "${filepath}.tmp" "$filepath"

    # Tamaño nuevo
    size_after=$(stat -f%z "$filepath" 2>/dev/null || stat -c%s "$filepath")
    size_after_mb=$(echo "scale=2; $size_after/1024/1024" | bc)
    reduction=$(echo "scale=1; ($size_before - $size_after) * 100 / $size_before" | bc)

    echo "   Tamaño optimizado: ${size_after_mb}MB"
    echo -e "   ${GREEN}✅ Reducción: ${reduction}%${NC}"

    total_before=$((total_before + size_before))
    total_after=$((total_after + size_after))
done

# Resumen
total_before_mb=$(echo "scale=2; $total_before/1024/1024" | bc)
total_after_mb=$(echo "scale=2; $total_after/1024/1024" | bc)
total_reduction=$(echo "scale=1; ($total_before - $total_after) * 100 / $total_before" | bc)
saved_mb=$(echo "scale=2; $total_before_mb - $total_after_mb" | bc)

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 RESUMEN DE OPTIMIZACIÓN${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Tamaño original:   ${total_before_mb}MB"
echo "Tamaño optimizado: ${total_after_mb}MB"
echo -e "Ahorro:            ${GREEN}${saved_mb}MB (${total_reduction}%)${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n${YELLOW}💾 Backup guardado en: $BACKUP_DIR${NC}"
echo -e "${GREEN}✅ Optimización completada${NC}\n"
