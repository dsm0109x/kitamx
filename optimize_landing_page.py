#!/usr/bin/env python3
"""
Script de Optimización Automática - Landing Page Kita
====================================================

Aplica optimizaciones automáticas basadas en los findings de la auditoría:
- Optimiza imágenes (convierte a WebP)
- Elimina console.log de archivos JS
- Genera reporte de optimizaciones aplicadas

Uso:
    python optimize_landing_page.py [--dry-run] [--images] [--js]
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
import shutil
import re


class LandingPageOptimizer:
    """Optimizador automático para la landing page."""

    def __init__(self, base_path: str, dry_run: bool = False):
        self.base_path = Path(base_path)
        self.static_path = self.base_path / "static"
        self.dry_run = dry_run
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "optimizations": []
        }

    def optimize_images_to_webp(self) -> dict:
        """Convierte imágenes PNG/JPG a WebP."""
        print("\n🖼️  Optimizando imágenes a WebP...")

        if self.dry_run:
            print("⚠️  [DRY RUN] - No se aplicarán cambios reales")

        optimized = []
        skipped = []
        errors = []

        # Buscar imágenes grandes (> 500KB)
        large_images = []
        for ext in ['.png', '.jpg', '.jpeg']:
            for img in self.static_path.glob(f"**/*{ext}"):
                size = img.stat().st_size
                if size > 500 * 1024:  # > 500KB
                    large_images.append(img)

        print(f"📊 Encontradas {len(large_images)} imágenes > 500KB para optimizar")

        for img_path in large_images:
            try:
                # Verificar si ya existe versión WebP
                webp_path = img_path.with_suffix('.webp')

                if webp_path.exists():
                    print(f"   ⏭️  Ya existe: {webp_path.name}")
                    skipped.append(str(img_path.relative_to(self.base_path)))
                    continue

                if not self.dry_run:
                    # Intentar convertir con cwebp (si está instalado)
                    try:
                        result = subprocess.run(
                            ['cwebp', '-q', '85', str(img_path), '-o', str(webp_path)],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )

                        if result.returncode == 0:
                            original_size = img_path.stat().st_size
                            webp_size = webp_path.stat().st_size
                            savings = ((original_size - webp_size) / original_size) * 100

                            print(f"   ✅ {img_path.name} → {webp_path.name} "
                                  f"({savings:.1f}% reducción)")

                            optimized.append({
                                "file": str(img_path.relative_to(self.base_path)),
                                "webp_file": str(webp_path.relative_to(self.base_path)),
                                "original_size_kb": round(original_size / 1024, 2),
                                "webp_size_kb": round(webp_size / 1024, 2),
                                "savings_percent": round(savings, 1)
                            })
                        else:
                            errors.append({
                                "file": str(img_path.relative_to(self.base_path)),
                                "error": result.stderr
                            })

                    except FileNotFoundError:
                        print("   ⚠️  cwebp no instalado. Instala con: sudo apt-get install webp")
                        return {
                            "status": "error",
                            "message": "cwebp no disponible",
                            "optimized": [],
                            "skipped": skipped,
                            "errors": []
                        }
                    except subprocess.TimeoutExpired:
                        errors.append({
                            "file": str(img_path.relative_to(self.base_path)),
                            "error": "Timeout durante conversión"
                        })
                else:
                    print(f"   [DRY RUN] Convertiría: {img_path.name} → WebP")
                    optimized.append({
                        "file": str(img_path.relative_to(self.base_path)),
                        "note": "dry_run"
                    })

            except Exception as e:
                errors.append({
                    "file": str(img_path.relative_to(self.base_path)),
                    "error": str(e)
                })

        return {
            "status": "success",
            "optimized": optimized,
            "skipped": skipped,
            "errors": errors
        }

    def remove_console_logs(self) -> dict:
        """Elimina console.log de archivos JavaScript."""
        print("\n⚡ Eliminando console.log de archivos JS...")

        if self.dry_run:
            print("⚠️  [DRY RUN] - No se aplicarán cambios reales")

        cleaned = []
        errors = []

        js_files = list(self.static_path.glob("**/*.js"))

        for js_file in js_files:
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()

                # Contar console.log antes
                console_logs_before = len(re.findall(r'console\.log\([^)]*\)', original_content))

                if console_logs_before == 0:
                    continue

                # Eliminar console.log (comentar en lugar de eliminar para mantener line numbers)
                cleaned_content = re.sub(
                    r'(\s*)console\.log\([^)]*\);?',
                    r'\1// [REMOVED] console.log();',
                    original_content
                )

                console_logs_after = len(re.findall(r'console\.log\([^)]*\)', cleaned_content))

                if not self.dry_run:
                    # Hacer backup
                    backup_path = js_file.with_suffix('.js.backup')
                    shutil.copy2(js_file, backup_path)

                    # Escribir archivo limpio
                    with open(js_file, 'w', encoding='utf-8') as f:
                        f.write(cleaned_content)

                    print(f"   ✅ {js_file.name}: {console_logs_before} console.log removidos "
                          f"(backup: {backup_path.name})")

                    cleaned.append({
                        "file": str(js_file.relative_to(self.base_path)),
                        "console_logs_removed": console_logs_before,
                        "backup": str(backup_path.relative_to(self.base_path))
                    })
                else:
                    print(f"   [DRY RUN] {js_file.name}: {console_logs_before} console.log a remover")
                    cleaned.append({
                        "file": str(js_file.relative_to(self.base_path)),
                        "console_logs_to_remove": console_logs_before,
                        "note": "dry_run"
                    })

            except Exception as e:
                errors.append({
                    "file": str(js_file.relative_to(self.base_path)),
                    "error": str(e)
                })

        return {
            "status": "success",
            "cleaned": cleaned,
            "errors": errors
        }

    def generate_missing_metatags_template(self) -> dict:
        """Genera un template snippet con los meta tags faltantes."""
        print("\n🏷️  Generando snippet de meta tags faltantes...")

        meta_tags_snippet = """<!-- Meta Tags Recomendados para Landing Page -->
<!-- Agregar en templates/base_minimal.html o en el {% block extra_head %} -->

<!-- Primary Meta Tags -->
<meta name="title" content="Kita - Enlaces de Pago y Facturación CFDI 4.0 Automática">
<meta name="description" content="Crea enlaces de pago en 30 segundos y genera facturas CFDI 4.0 automáticamente. Auto-facturación para tus clientes, integración con Mercado Pago®. Prueba 30 días gratis.">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="{{ request.build_absolute_uri }}">
<meta property="og:title" content="Kita - Enlaces de Pago y Facturación CFDI 4.0 Automática">
<meta property="og:description" content="Crea enlaces de pago en 30 segundos y genera facturas CFDI 4.0 automáticamente. Auto-facturación para tus clientes.">
<meta property="og:image" content="{{ request.scheme }}://{{ request.get_host }}{% static 'images/og/kita-og-home.png' %}">

<!-- Twitter -->
<meta property="twitter:card" content="summary_large_image">
<meta property="twitter:url" content="{{ request.build_absolute_uri }}">
<meta property="twitter:title" content="Kita - Enlaces de Pago y Facturación CFDI 4.0 Automática">
<meta property="twitter:description" content="Crea enlaces de pago en 30 segundos y genera facturas CFDI 4.0 automáticamente.">
<meta property="twitter:image" content="{{ request.scheme }}://{{ request.get_host }}{% static 'images/og/kita-og-home.png' %}">

<!-- Canonical URL -->
<link rel="canonical" href="{{ request.build_absolute_uri }}">
"""

        output_path = self.base_path / "templates" / "snippets" / "meta_tags_landing.html"

        if not self.dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(meta_tags_snippet)

            print(f"   ✅ Snippet generado: {output_path}")
        else:
            print(f"   [DRY RUN] Generaría snippet en: {output_path}")

        return {
            "status": "success",
            "snippet_path": str(output_path.relative_to(self.base_path)) if not self.dry_run else "N/A",
            "message": "Incluye este snippet en tu template base"
        }

    def run_optimizations(self, optimize_images: bool = True, optimize_js: bool = True) -> dict:
        """Ejecuta todas las optimizaciones."""
        print("\n" + "="*60)
        print("🚀 OPTIMIZACIÓN AUTOMÁTICA - LANDING PAGE KITA")
        if self.dry_run:
            print("⚠️  MODO DRY RUN - Sin cambios reales")
        print("="*60)

        if optimize_images:
            images_result = self.optimize_images_to_webp()
            self.results["optimizations"].append({
                "type": "images",
                "result": images_result
            })

        if optimize_js:
            js_result = self.remove_console_logs()
            self.results["optimizations"].append({
                "type": "javascript",
                "result": js_result
            })

        # Siempre generar snippet de meta tags
        metatags_result = self.generate_missing_metatags_template()
        self.results["optimizations"].append({
            "type": "metatags",
            "result": metatags_result
        })

        print("\n" + "="*60)
        print("✅ OPTIMIZACIÓN COMPLETADA")
        print("="*60 + "\n")

        return self.results

    def generate_report(self, output_path: str = None) -> str:
        """Genera reporte de optimizaciones."""
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = self.base_path / f"OPTIMIZATION_REPORT_{timestamp}.md"

        report = []
        report.append("# 🚀 Reporte de Optimización - Landing Page Kita\n")
        report.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**Modo:** {'DRY RUN (sin cambios reales)' if self.dry_run else 'PRODUCCIÓN (cambios aplicados)'}\n")
        report.append("\n---\n")

        for opt in self.results["optimizations"]:
            opt_type = opt["type"]
            result = opt["result"]

            if opt_type == "images":
                report.append("\n## 🖼️  Optimización de Imágenes\n")
                report.append(f"**Imágenes optimizadas:** {len(result.get('optimized', []))}\n")
                report.append(f"**Imágenes omitidas:** {len(result.get('skipped', []))}\n")
                report.append(f"**Errores:** {len(result.get('errors', []))}\n")

                if result.get('optimized'):
                    report.append("\n### Imágenes Convertidas a WebP\n")
                    for img in result['optimized']:
                        if 'savings_percent' in img:
                            report.append(
                                f"- `{img['file']}` → `{img['webp_file']}` "
                                f"({img['original_size_kb']} KB → {img['webp_size_kb']} KB, "
                                f"{img['savings_percent']}% reducción)\n"
                            )
                        else:
                            report.append(f"- `{img['file']}` (dry run)\n")

            elif opt_type == "javascript":
                report.append("\n## ⚡ Limpieza de JavaScript\n")
                report.append(f"**Archivos limpiados:** {len(result.get('cleaned', []))}\n")
                report.append(f"**Errores:** {len(result.get('errors', []))}\n")

                if result.get('cleaned'):
                    report.append("\n### Console.log Removidos\n")
                    total_removed = sum(f.get('console_logs_removed', f.get('console_logs_to_remove', 0))
                                      for f in result['cleaned'])
                    report.append(f"**Total console.log removidos:** {total_removed}\n\n")

                    for js in result['cleaned'][:10]:  # Top 10
                        count = js.get('console_logs_removed', js.get('console_logs_to_remove', 0))
                        report.append(f"- `{js['file']}`: {count} removidos\n")

                    if len(result['cleaned']) > 10:
                        report.append(f"\n... y {len(result['cleaned']) - 10} archivos más\n")

            elif opt_type == "metatags":
                report.append("\n## 🏷️  Meta Tags\n")
                report.append(f"**Snippet generado:** `{result.get('snippet_path', 'N/A')}`\n")
                report.append(f"\n{result.get('message', '')}\n")

        # Próximos pasos
        report.append("\n## 📋 Próximos Pasos\n")
        report.append("1. **Meta Tags**: Incluye el snippet generado en `templates/base_minimal.html`\n")
        report.append("2. **Imágenes WebP**: Actualiza los templates para usar las imágenes WebP con fallback\n")
        report.append("3. **Testing**: Verifica que todo funcione correctamente\n")
        report.append("4. **Re-auditar**: Ejecuta `python audit_landing_page.py` para ver mejoras\n")

        report_content = "".join(report)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"\n✅ Reporte de optimización generado: {output_path}\n")

        return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Optimizador automático de landing page")
    parser.add_argument("--dry-run", action="store_true", help="Simula optimizaciones sin aplicar cambios")
    parser.add_argument("--no-images", action="store_true", help="No optimizar imágenes")
    parser.add_argument("--no-js", action="store_true", help="No limpiar JavaScript")

    args = parser.parse_args()

    base_path = Path(__file__).parent

    optimizer = LandingPageOptimizer(base_path, dry_run=args.dry_run)

    results = optimizer.run_optimizations(
        optimize_images=not args.no_images,
        optimize_js=not args.no_js
    )

    report_path = optimizer.generate_report()

    print("="*60)
    print("📊 RESUMEN DE OPTIMIZACIÓN")
    print("="*60)

    for opt in results["optimizations"]:
        if opt["type"] == "images":
            optimized_count = len(opt["result"].get("optimized", []))
            print(f"🖼️  Imágenes: {optimized_count} optimizadas")
        elif opt["type"] == "javascript":
            cleaned_count = len(opt["result"].get("cleaned", []))
            print(f"⚡ JavaScript: {cleaned_count} archivos limpiados")

    print(f"\n📄 Reporte: {report_path}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
