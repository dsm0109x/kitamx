#!/bin/bash
###############################################################################
# KITA IMAGE OPTIMIZATION SCRIPT
# Optimiza GIFs y convierte imágenes a WebP
# Impacto esperado: 102MB → ~8MB (-92%)
###############################################################################

set -e  # Exit on error

echo "🎨 KITA IMAGE OPTIMIZATION"
echo "=========================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar herramientas necesarias
echo "📦 Verificando dependencias..."
if ! command -v gifsicle &> /dev/null; then
    echo -e "${RED}✗ gifsicle no instalado${NC}"
    echo "  Instalar con: sudo apt install gifsicle"
    exit 1
fi

if ! command -v cwebp &> /dev/null; then
    echo -e "${RED}✗ cwebp no instalado${NC}"
    echo "  Instalar con: sudo apt install webp"
    exit 1
fi

echo -e "${GREEN}✓ Todas las dependencias instaladas${NC}"
echo ""

# Directorios
DEMO_DIR="./static/images/demo"
BACKUP_DIR="./static/images/demo/original_backup_$(date +%Y%m%d_%H%M%S)"

# Crear backup (con path absoluto)
echo "💾 Creando backup en: $BACKUP_DIR"

# Crear directorio desde la raíz del proyecto
mkdir -p "$BACKUP_DIR"

# Verificar que se creó
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}✗ Error creando directorio de backup${NC}"
    exit 1
fi

# Función para formatear tamaño
format_size() {
    local size=$1
    if [ $size -gt 1048576 ]; then
        echo "$(echo "scale=1; $size/1048576" | bc)MB"
    else
        echo "$(echo "scale=1; $size/1024" | bc)KB"
    fi
}

# Función para optimizar un GIF
optimize_gif() {
    local input_file=$1
    local output_file="${input_file%.gif}-optimized.gif"
    local filename=$(basename "$input_file")

    # Calcular backup path absoluto desde donde estamos
    local backup_file="../original_backup_$(basename $BACKUP_DIR)/$filename"

    echo ""
    echo "🔄 Procesando: $filename"

    # Crear directorio de backup si no existe
    mkdir -p "$(dirname "$backup_file")"

    # Backup original
    cp "$input_file" "$backup_file"

    # Tamaño original
    local size_before=$(stat -f%z "$input_file" 2>/dev/null || stat -c%s "$input_file")
    echo "   Tamaño original: $(format_size $size_before)"

    # Optimizar con gifsicle
    # -O3: Optimización máxima
    # --colors 128: Reducir paleta a 128 colores (de 256)
    # --lossy=80: Compresión con pérdida moderada
    gifsicle -O3 --colors 128 --lossy=80 "$input_file" -o "$output_file"

    # Tamaño optimizado
    local size_after=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file")
    local reduction=$(echo "scale=1; 100 - ($size_after * 100 / $size_before)" | bc)

    echo "   Tamaño optimizado: $(format_size $size_after)"
    echo -e "   ${GREEN}✓ Reducción: ${reduction}%${NC}"

    # Si la optimización fue exitosa (>50% reducción), reemplazar original
    if (( $(echo "$reduction > 50" | bc -l) )); then
        mv "$output_file" "$input_file"
        echo -e "   ${GREEN}✓ Archivo reemplazado${NC}"
    else
        echo -e "   ${YELLOW}⚠ Optimización menor al 50%, archivo original mantenido${NC}"
        rm "$output_file"
    fi
}

# Función para convertir a WebP
convert_to_webp() {
    local input_file=$1
    local output_file="${input_file%.*}.webp"

    echo ""
    echo "🔄 Convirtiendo a WebP: $(basename $input_file)"

    # Convertir a WebP con calidad 85
    cwebp -q 85 "$input_file" -o "$output_file"

    # Comparar tamaños
    local size_original=$(stat -f%z "$input_file" 2>/dev/null || stat -c%s "$input_file")
    local size_webp=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file")
    local reduction=$(echo "scale=1; 100 - ($size_webp * 100 / $size_original)" | bc)

    echo "   Original: $(format_size $size_original)"
    echo "   WebP: $(format_size $size_webp)"
    echo -e "   ${GREEN}✓ Reducción: ${reduction}%${NC}"
}

# PASO 1: Optimizar GIFs
echo "================================================"
echo "PASO 1: OPTIMIZANDO GIFs EN $DEMO_DIR"
echo "================================================"

cd "$DEMO_DIR" || exit 1

total_before=0
total_after=0

# Procesar GIFs específicos
for gif in paso1.gif paso2.gif paso3.gif crecimiento.gif stars-bg.gif; do
    if [ -f "$gif" ] && [[ ! "$gif" =~ "-optimized" ]]; then
        size_before=$(stat -f%z "$gif" 2>/dev/null || stat -c%s "$gif")
        total_before=$((total_before + size_before))

        optimize_gif "$gif"

        size_after=$(stat -f%z "$gif" 2>/dev/null || stat -c%s "$gif")
        total_after=$((total_after + size_after))
    fi
done

cd - > /dev/null

echo ""
echo "================================================"
echo "RESUMEN DE OPTIMIZACIÓN"
echo "================================================"
echo "Total antes: $(format_size $total_before)"
echo "Total después: $(format_size $total_after)"

if [ $total_before -gt 0 ]; then
    reduction=$(echo "scale=1; 100 - ($total_after * 100 / $total_before)" | bc)
    echo -e "${GREEN}✓ Reducción total: ${reduction}%${NC}"
fi

echo ""
echo "💾 Backup guardado en: $BACKUP_DIR"
echo ""
echo -e "${GREEN}✅ OPTIMIZACIÓN COMPLETADA${NC}"
echo ""
echo "⚠️  IMPORTANTE: Después de ejecutar este script:"
echo "   1. Probar los GIFs en el navegador"
echo "   2. Si todo funciona bien, eliminar el backup:"
echo "      rm -rf $BACKUP_DIR"
echo "   3. Hacer commit de los archivos optimizados"
echo ""
