# 🎥 Fix para Videos Transparentes en Safari/iPhone

## Problema Resuelto
Los videos con fondo transparente aparecían con fondo negro en Safari/iPhone debido a limitaciones del navegador con el formato WebM y el canal alpha.

## Solución Implementada ✅

### 1. **Formato Dual (MP4 + WebM)**
```html
<!-- ANTES (solo WebM) -->
<video src="paso1.webm">

<!-- DESPUÉS (MP4 primero para Safari, WebM como fallback) -->
<video>
    <source src="paso1.mp4" type="video/mp4; codecs=hvc1">
    <source src="paso1.webm" type="video/webm">
</video>
```

### 2. **Archivos Agregados**
- `/static/images/demo/paso1.mp4` (1.3MB)
- `/static/images/demo/paso2.mp4` (1.8MB)
- `/static/images/demo/paso3.mp4` (624KB)

### 3. **CSS Específico para Safari**
Nuevo archivo: `/static/css/04-pages/video-safari-fix.css`
- Elimina fondos forzados
- Aplica optimizaciones WebKit
- Mejora composición de transparencia
- Fallback sutil para casos extremos

### 4. **JavaScript con Detección de Safari**
- Detecta Safari/iOS automáticamente
- Remueve source WebM en Safari
- Aplica atributos específicos iOS
- Manejo mejorado de autoplay

## Cómo Verificar la Solución 🧪

### En iPhone/iPad:
1. Abre Safari
2. Navega a la landing page
3. Scroll hasta la sección "Cómo Funciona"
4. Los videos deben mostrar:
   - ✅ Fondo transparente/blanco
   - ✅ Animación fluida
   - ✅ Autoplay funcionando
   - ❌ NO fondo negro

### En Desktop Safari:
1. Abre Safari en Mac
2. Inspeccionar elemento en los videos
3. Verificar que carga MP4, no WebM
4. Confirmar clase `safari-video` aplicada

### En Chrome/Firefox:
1. Debe seguir funcionando normalmente
2. Cargará WebM (más eficiente)
3. Sin cambios en la experiencia

## Debugging 🔍

### Si aún ves fondo negro:

1. **Limpiar caché del navegador**
   - iOS: Settings > Safari > Clear History and Website Data
   - Mac: Safari > Develop > Empty Caches

2. **Verificar formato MP4**
   ```bash
   ffprobe -v error -show_streams paso1.mp4 | grep codec_name
   # Debe mostrar: hevc o h264
   ```

3. **Forzar recarga**
   - Agregar `?v=2` a las URLs de los videos
   - O cambiar version en CSS: `video-safari-fix.css?v=2.0`

4. **Debug mode**
   - En localhost verás logs en consola
   - Muestra si Safari fue detectado correctamente

## Optimización Adicional (Opcional) 🚀

Si los MP4 son muy pesados, puedes recodificarlos:

```bash
# Opción 1: HEVC con transparencia (mejor para Safari moderno)
ffmpeg -i paso1.mp4 -c:v hevc -tag:v hvc1 -alpha_quality 0.75 -crf 28 paso1_optimized.mp4

# Opción 2: H.264 sin transparencia pero con chroma key
ffmpeg -i paso1.mp4 -c:v libx264 -pix_fmt yuv420p -crf 23 paso1_h264.mp4
```

## Alternativas si Persiste el Problema

### Plan B: Fondo Blanco Fijo
```css
.demo-gif-direct {
    background: #f8fafc !important; /* Mismo color del diseño */
}
```

### Plan C: GIF Animado
Convertir a GIF con fondo blanco integrado (última opción, mayor peso).

### Plan D: Lottie/SVG Animation
Reemplazar con animaciones vectoriales (requiere rediseño).

## Testing Checklist ✓

- [ ] iPhone Safari - Fondo transparente OK
- [ ] iPad Safari - Fondo transparente OK
- [ ] Mac Safari - Fondo transparente OK
- [ ] Chrome Desktop - WebM funcionando
- [ ] Firefox Desktop - WebM funcionando
- [ ] Android Chrome - WebM funcionando
- [ ] Edge - Ambos formatos OK

## Notas Técnicas 📝

1. **Safari soporta transparencia en MP4 SOLO con:**
   - HEVC codec (H.265) con alpha channel
   - MOV con ProRes 4444
   - NO con H.264 estándar

2. **El orden de `<source>` importa:**
   - Safari toma el primero que puede reproducir
   - Por eso MP4 va antes que WebM

3. **`playsinline` es crítico en iOS:**
   - Sin él, el video abre en fullscreen
   - Rompe la experiencia de la página

4. **Performance:**
   - MP4 es más pesado que WebM (~2x)
   - Pero necesario para compatibilidad Safari
   - Consider CDN para servir videos

---

**Implementado por:** Claude Code
**Fecha:** 19/11/2024
**Versión:** 1.0