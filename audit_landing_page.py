#!/usr/bin/env python
"""
Auditoría Multi-Dimensional para Landing Page de Kita
======================================================

Este script audita la landing page desde múltiples perspectivas:
- Performance & Core Web Vitals
- SEO & Structured Data
- Accesibilidad (WCAG)
- Seguridad
- UX/UI
- Calidad de Código
- Optimización de Conversión

Uso:
    python audit_landing_page.py [--url URL] [--output OUTPUT]
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re
import argparse


class LandingPageAuditor:
    """Auditor comprehensivo para la landing page de Kita."""

    def __init__(self, base_path: str, url: str = "http://localhost:8000/"):
        self.base_path = Path(base_path)
        self.url = url
        self.template_path = self.base_path / "templates" / "home.html"
        self.static_path = self.base_path / "static"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "scores": {},
            "issues": {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
                "info": []
            },
            "recommendations": [],
            "metrics": {}
        }

    def audit_html_structure(self) -> Dict[str, Any]:
        """Audita la estructura HTML del template."""
        print("📄 Auditando estructura HTML...")

        issues = []
        metrics = {}

        if not self.template_path.exists():
            issues.append({
                "severity": "critical",
                "category": "html",
                "message": f"Template no encontrado: {self.template_path}"
            })
            return {"issues": issues, "metrics": metrics}

        with open(self.template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        metrics["total_lines"] = len(html_content.split('\n'))
        metrics["total_chars"] = len(html_content)

        # Verificar semantic HTML
        semantic_tags = ['header', 'nav', 'main', 'section', 'article', 'aside', 'footer']
        found_semantic = []
        for tag in semantic_tags:
            pattern = f'<{tag}[\\s>]'
            if re.search(pattern, html_content):
                found_semantic.append(tag)

        metrics["semantic_tags_used"] = len(found_semantic)
        metrics["semantic_tags_found"] = found_semantic

        if len(found_semantic) < 5:
            issues.append({
                "severity": "medium",
                "category": "html",
                "message": f"Solo {len(found_semantic)} tags semánticos encontrados. Considera usar más: {', '.join(set(semantic_tags) - set(found_semantic))}"
            })

        # Verificar heading hierarchy
        h1_count = len(re.findall(r'<h1[\\s>]', html_content))
        h2_count = len(re.findall(r'<h2[\\s>]', html_content))
        h3_count = len(re.findall(r'<h3[\\s>]', html_content))

        metrics["headings"] = {"h1": h1_count, "h2": h2_count, "h3": h3_count}

        if h1_count == 0:
            issues.append({
                "severity": "critical",
                "category": "seo",
                "message": "No se encontró ningún <h1>. Crítico para SEO."
            })
        elif h1_count > 1:
            issues.append({
                "severity": "medium",
                "category": "seo",
                "message": f"Se encontraron {h1_count} <h1>. Recomendado: solo 1."
            })

        # Verificar meta tags (en el template o base)
        meta_viewport = re.search(r'<meta[^>]*name=["\']viewport["\']', html_content)
        if not meta_viewport:
            issues.append({
                "severity": "high",
                "category": "mobile",
                "message": "Meta viewport no encontrado. Crítico para responsive design."
            })

        # Verificar alt text en imágenes
        img_tags = re.findall(r'<img[^>]*>', html_content)
        metrics["total_images"] = len(img_tags)

        images_without_alt = 0
        for img in img_tags:
            if 'alt=' not in img:
                images_without_alt += 1

        metrics["images_without_alt"] = images_without_alt

        if images_without_alt > 0:
            issues.append({
                "severity": "high",
                "category": "accessibility",
                "message": f"{images_without_alt} imágenes sin atributo alt. Crítico para accesibilidad."
            })

        # Verificar ARIA attributes
        aria_labels = len(re.findall(r'aria-label=', html_content))
        aria_labelledby = len(re.findall(r'aria-labelledby=', html_content))
        aria_describedby = len(re.findall(r'aria-describedby=', html_content))
        aria_hidden = len(re.findall(r'aria-hidden=', html_content))

        metrics["aria_attributes"] = {
            "aria-label": aria_labels,
            "aria-labelledby": aria_labelledby,
            "aria-describedby": aria_describedby,
            "aria-hidden": aria_hidden,
            "total": aria_labels + aria_labelledby + aria_describedby + aria_hidden
        }

        # Verificar links
        links = re.findall(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>', html_content)
        metrics["total_links"] = len(links)

        external_links = [link for link in links if link.startswith('http')]
        metrics["external_links"] = len(external_links)

        # Verificar si external links tienen rel="noopener noreferrer"
        external_links_without_rel = 0
        for link in external_links:
            link_tag = re.search(f'<a[^>]*href=["\'].*{re.escape(link)}["\'][^>]*>', html_content)
            if link_tag:
                if 'rel=' not in link_tag.group():
                    external_links_without_rel += 1

        if external_links_without_rel > 0:
            issues.append({
                "severity": "medium",
                "category": "security",
                "message": f"{external_links_without_rel} enlaces externos sin rel='noopener noreferrer'. Riesgo de seguridad."
            })

        # Verificar CTAs
        cta_buttons = len(re.findall(r'(btn-primary|btn-hero|data-tracking=["\']cta-)', html_content))
        metrics["cta_buttons"] = cta_buttons

        if cta_buttons < 3:
            issues.append({
                "severity": "low",
                "category": "conversion",
                "message": f"Solo {cta_buttons} CTAs encontrados. Considera agregar más oportunidades de conversión."
            })

        # Verificar structured data (JSON-LD)
        json_ld = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_content, re.DOTALL)
        if json_ld:
            try:
                structured_data = json.loads(json_ld.group(1))
                metrics["structured_data"] = "present"
                metrics["structured_data_type"] = structured_data.get("@type", "unknown")
            except json.JSONDecodeError:
                issues.append({
                    "severity": "medium",
                    "category": "seo",
                    "message": "Structured data JSON-LD presente pero mal formado."
                })
        else:
            issues.append({
                "severity": "medium",
                "category": "seo",
                "message": "No se encontró structured data (JSON-LD). Recomendado para SEO."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_css_resources(self) -> Dict[str, Any]:
        """Audita los recursos CSS."""
        print("🎨 Auditando recursos CSS...")

        issues = []
        metrics = {}

        css_files = list(self.static_path.glob("**/*.css"))
        metrics["total_css_files"] = len(css_files)

        total_css_size = 0
        css_details = []

        for css_file in css_files:
            size = css_file.stat().st_size
            total_css_size += size

            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()

            css_details.append({
                "file": str(css_file.relative_to(self.base_path)),
                "size_kb": round(size / 1024, 2),
                "lines": len(content.split('\n')),
                "rules_approx": len(re.findall(r'\{', content))
            })

        metrics["total_css_size_kb"] = round(total_css_size / 1024, 2)
        metrics["css_files_details"] = css_details

        if total_css_size > 200 * 1024:  # > 200KB
            issues.append({
                "severity": "medium",
                "category": "performance",
                "message": f"Total CSS size: {round(total_css_size / 1024, 2)} KB. Considera minificar o eliminar CSS no usado."
            })

        # Verificar si hay critical CSS
        critical_css = any('critical' in str(f) for f in css_files)
        metrics["has_critical_css"] = critical_css

        if critical_css:
            issues.append({
                "severity": "info",
                "category": "performance",
                "message": "✓ Critical CSS detectado. Buena práctica para performance."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_js_resources(self) -> Dict[str, Any]:
        """Audita los recursos JavaScript."""
        print("⚡ Auditando recursos JavaScript...")

        issues = []
        metrics = {}

        js_files = list(self.static_path.glob("**/*.js"))
        metrics["total_js_files"] = len(js_files)

        total_js_size = 0
        js_details = []

        for js_file in js_files:
            size = js_file.stat().st_size
            total_js_size += size

            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Buscar posibles issues
            has_console_log = 'console.log' in content
            has_debugger = 'debugger' in content

            js_details.append({
                "file": str(js_file.relative_to(self.base_path)),
                "size_kb": round(size / 1024, 2),
                "lines": len(content.split('\n')),
                "has_console_log": has_console_log,
                "has_debugger": has_debugger
            })

            if has_console_log:
                issues.append({
                    "severity": "low",
                    "category": "quality",
                    "message": f"console.log encontrado en {js_file.name}. Considera remover para producción."
                })

            if has_debugger:
                issues.append({
                    "severity": "medium",
                    "category": "quality",
                    "message": f"debugger statement en {js_file.name}. Remover para producción."
                })

        metrics["total_js_size_kb"] = round(total_js_size / 1024, 2)
        metrics["js_files_details"] = js_details

        if total_js_size > 300 * 1024:  # > 300KB
            issues.append({
                "severity": "medium",
                "category": "performance",
                "message": f"Total JS size: {round(total_js_size / 1024, 2)} KB. Considera code splitting o lazy loading."
            })

        # Verificar si hay bundle
        has_bundle = any('bundle' in str(f) for f in js_files)
        metrics["has_bundle"] = has_bundle

        if has_bundle:
            issues.append({
                "severity": "info",
                "category": "performance",
                "message": "✓ Bundle JS detectado. Buena práctica para reducir HTTP requests."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_images(self) -> Dict[str, Any]:
        """Audita las imágenes."""
        print("🖼️  Auditando imágenes...")

        issues = []
        metrics = {}

        # Buscar imágenes en static
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']
        images = []
        for ext in image_extensions:
            images.extend(self.static_path.glob(f"**/*{ext}"))

        metrics["total_images"] = len(images)

        total_image_size = 0
        large_images = []
        image_details = []

        for img in images:
            size = img.stat().st_size
            total_image_size += size

            image_details.append({
                "file": str(img.relative_to(self.base_path)),
                "size_kb": round(size / 1024, 2),
                "extension": img.suffix
            })

            if size > 500 * 1024 and img.suffix != '.svg':  # > 500KB
                large_images.append({
                    "file": img.name,
                    "size_kb": round(size / 1024, 2)
                })

        metrics["total_image_size_kb"] = round(total_image_size / 1024, 2)
        metrics["image_details"] = image_details
        metrics["large_images_count"] = len(large_images)

        if large_images:
            issues.append({
                "severity": "high",
                "category": "performance",
                "message": f"{len(large_images)} imágenes > 500KB encontradas. Optimiza con compresión o WebP.",
                "details": large_images
            })

        # Verificar si hay WebP
        webp_images = [img for img in images if img.suffix == '.webp']
        metrics["webp_images"] = len(webp_images)

        if len(webp_images) == 0 and len(images) > 0:
            issues.append({
                "severity": "medium",
                "category": "performance",
                "message": "No se encontraron imágenes WebP. Considera convertir a WebP para mejor performance."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_accessibility(self) -> Dict[str, Any]:
        """Audita aspectos de accesibilidad."""
        print("♿ Auditando accesibilidad...")

        issues = []
        metrics = {}

        with open(self.template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verificar role attributes
        nav_with_role = re.search(r'<nav[^>]*role=["\']navigation["\']', html_content)
        main_with_role = re.search(r'<main[^>]*role=["\']main["\']', html_content)

        if nav_with_role:
            metrics["nav_role"] = "present"
        else:
            issues.append({
                "severity": "low",
                "category": "accessibility",
                "message": "Considera agregar role='navigation' al <nav> para mejor accesibilidad."
            })

        if main_with_role:
            metrics["main_role"] = "present"
        else:
            issues.append({
                "severity": "low",
                "category": "accessibility",
                "message": "Considera agregar role='main' al <main> para mejor accesibilidad."
            })

        # Verificar skip links
        skip_link = re.search(r'href=["\']#main', html_content)
        metrics["has_skip_link"] = bool(skip_link)

        if not skip_link:
            issues.append({
                "severity": "medium",
                "category": "accessibility",
                "message": "No se encontró skip link. Importante para usuarios de teclado."
            })

        # Verificar tabindex
        negative_tabindex = re.findall(r'tabindex=["\'](-[0-9]+)["\']', html_content)
        if negative_tabindex:
            metrics["negative_tabindex_count"] = len(negative_tabindex)
            # tabindex="-1" es válido en algunos casos (como main para focus programático)
            if any(int(idx) < -1 for idx in negative_tabindex):
                issues.append({
                    "severity": "medium",
                    "category": "accessibility",
                    "message": f"Tabindex negativos encontrados. Verifica que sean intencionales."
                })

        # Verificar contraste de colores (básico - solo verifica si hay estilos de color)
        color_styles = len(re.findall(r'(color:|background-color:)', html_content))
        metrics["inline_color_styles"] = color_styles

        if color_styles > 10:
            issues.append({
                "severity": "low",
                "category": "maintainability",
                "message": f"{color_styles} estilos de color inline encontrados. Considera centralizar en CSS."
            })

        # Verificar buttons vs links
        links_with_onclick = len(re.findall(r'<a[^>]*onclick=', html_content))
        if links_with_onclick > 0:
            issues.append({
                "severity": "medium",
                "category": "accessibility",
                "message": f"{links_with_onclick} links con onclick. Usa <button> para acciones, <a> para navegación."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_seo(self) -> Dict[str, Any]:
        """Audita aspectos de SEO."""
        print("🔍 Auditando SEO...")

        issues = []
        metrics = {}

        with open(self.template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verificar meta description
        meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html_content)
        if meta_desc:
            desc_length = len(meta_desc.group(1))
            metrics["meta_description_length"] = desc_length

            if desc_length < 120:
                issues.append({
                    "severity": "medium",
                    "category": "seo",
                    "message": f"Meta description muy corta ({desc_length} chars). Recomendado: 120-160 chars."
                })
            elif desc_length > 160:
                issues.append({
                    "severity": "medium",
                    "category": "seo",
                    "message": f"Meta description muy larga ({desc_length} chars). Recomendado: 120-160 chars."
                })
        else:
            issues.append({
                "severity": "high",
                "category": "seo",
                "message": "Meta description no encontrada. Crítico para SEO."
            })

        # Verificar Open Graph tags
        og_tags = {
            "og:title": re.search(r'property=["\']og:title["\']', html_content),
            "og:description": re.search(r'property=["\']og:description["\']', html_content),
            "og:image": re.search(r'property=["\']og:image["\']', html_content),
            "og:url": re.search(r'property=["\']og:url["\']', html_content),
            "og:type": re.search(r'property=["\']og:type["\']', html_content)
        }

        metrics["og_tags"] = {tag: bool(found) for tag, found in og_tags.items()}

        missing_og = [tag for tag, found in og_tags.items() if not found]
        if missing_og:
            issues.append({
                "severity": "medium",
                "category": "seo",
                "message": f"Open Graph tags faltantes: {', '.join(missing_og)}. Importantes para social sharing."
            })

        # Verificar Twitter Card
        twitter_card = re.search(r'name=["\']twitter:card["\']', html_content)
        metrics["has_twitter_card"] = bool(twitter_card)

        if not twitter_card:
            issues.append({
                "severity": "low",
                "category": "seo",
                "message": "Twitter Card no encontrado. Recomendado para compartir en Twitter."
            })

        # Verificar canonical URL
        canonical = re.search(r'<link[^>]*rel=["\']canonical["\']', html_content)
        metrics["has_canonical"] = bool(canonical)

        if not canonical:
            issues.append({
                "severity": "medium",
                "category": "seo",
                "message": "Canonical URL no encontrado. Importante para evitar contenido duplicado."
            })

        # Verificar lang attribute
        lang_attr = re.search(r'<html[^>]*lang=["\']([^"\']*)["\']', html_content)
        if lang_attr:
            metrics["html_lang"] = lang_attr.group(1)
        else:
            issues.append({
                "severity": "high",
                "category": "seo",
                "message": "Atributo lang no encontrado en <html>. Crítico para SEO internacional."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_performance(self) -> Dict[str, Any]:
        """Audita aspectos de performance."""
        print("⚡ Auditando performance...")

        issues = []
        metrics = {}

        with open(self.template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verificar loading attributes en imágenes
        lazy_images = len(re.findall(r'<img[^>]*loading=["\']lazy["\']', html_content))
        eager_images = len(re.findall(r'<img[^>]*loading=["\']eager["\']', html_content))
        total_img_tags = len(re.findall(r'<img[^>]*>', html_content))

        metrics["lazy_images"] = lazy_images
        metrics["eager_images"] = eager_images
        metrics["total_images_in_html"] = total_img_tags

        if lazy_images < total_img_tags - 2:  # Permitir 2 eager (hero)
            issues.append({
                "severity": "medium",
                "category": "performance",
                "message": f"Solo {lazy_images}/{total_img_tags} imágenes con lazy loading. Considera agregar loading='lazy' a más imágenes."
            })

        # Verificar defer/async en scripts
        scripts = re.findall(r'<script[^>]*>', html_content)
        scripts_with_defer = len([s for s in scripts if 'defer' in s])
        scripts_with_async = len([s for s in scripts if 'async' in s])

        metrics["total_scripts"] = len(scripts)
        metrics["scripts_with_defer"] = scripts_with_defer
        metrics["scripts_with_async"] = scripts_with_async

        blocking_scripts = len(scripts) - scripts_with_defer - scripts_with_async
        if blocking_scripts > 2:
            issues.append({
                "severity": "high",
                "category": "performance",
                "message": f"{blocking_scripts} scripts bloqueantes encontrados. Usa defer o async."
            })

        # Verificar preload/prefetch
        preload_tags = len(re.findall(r'<link[^>]*rel=["\']preload["\']', html_content))
        prefetch_tags = len(re.findall(r'<link[^>]*rel=["\']prefetch["\']', html_content))

        metrics["preload_tags"] = preload_tags
        metrics["prefetch_tags"] = prefetch_tags

        if preload_tags == 0:
            issues.append({
                "severity": "low",
                "category": "performance",
                "message": "No se encontraron preload hints. Considera precargar recursos críticos."
            })

        # Verificar inline styles
        style_tags = len(re.findall(r'<style[^>]*>', html_content))
        metrics["inline_style_tags"] = style_tags

        if style_tags > 2:
            issues.append({
                "severity": "low",
                "category": "maintainability",
                "message": f"{style_tags} tags <style> inline. Considera mover a archivos externos."
            })

        return {"issues": issues, "metrics": metrics}

    def audit_conversion(self) -> Dict[str, Any]:
        """Audita aspectos de conversión y UX."""
        print("📈 Auditando optimización de conversión...")

        issues = []
        metrics = {}

        with open(self.template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Contar CTAs
        primary_ctas = len(re.findall(r'(btn-primary|btn-hero|btn-accent)', html_content))
        secondary_ctas = len(re.findall(r'btn-outline|btn-secondary', html_content))

        metrics["primary_ctas"] = primary_ctas
        metrics["secondary_ctas"] = secondary_ctas

        if primary_ctas < 3:
            issues.append({
                "severity": "medium",
                "category": "conversion",
                "message": f"Solo {primary_ctas} CTAs primarios. Considera agregar más oportunidades de conversión."
            })

        # Verificar trust signals
        trust_signals = [
            (r'shield', "Iconos de seguridad"),
            (r'check', "Iconos de verificación"),
            (r'testimonial|review|rating', "Testimonios/Reviews"),
            (r'guarantee|garantía', "Garantías"),
            (r'secure|segur', "Menciones de seguridad")
        ]

        found_trust_signals = []
        for pattern, name in trust_signals:
            if re.search(pattern, html_content, re.IGNORECASE):
                found_trust_signals.append(name)

        metrics["trust_signals"] = found_trust_signals
        metrics["trust_signals_count"] = len(found_trust_signals)

        # Verificar data-tracking attributes (analytics)
        tracking_attrs = len(re.findall(r'data-tracking=', html_content))
        metrics["tracking_attributes"] = tracking_attrs

        if tracking_attrs == 0:
            issues.append({
                "severity": "medium",
                "category": "analytics",
                "message": "No se encontraron atributos data-tracking. Importante para medir conversiones."
            })

        # Verificar forms
        forms = len(re.findall(r'<form[^>]*>', html_content))
        metrics["forms"] = forms

        # Verificar mobile responsiveness indicators
        mobile_classes = len(re.findall(r'(d-sm-|d-md-|d-lg-|col-sm-|col-md-|col-lg-)', html_content))
        metrics["responsive_classes"] = mobile_classes

        if mobile_classes < 10:
            issues.append({
                "severity": "medium",
                "category": "ux",
                "message": f"Solo {mobile_classes} clases responsive. Verifica que sea mobile-first."
            })

        # Verificar social proof
        social_proof_indicators = [
            r'[0-9]+\\s*(usuarios|clientes|empresas)',
            r'[0-9]+%',
            r'desde\\s*20[0-9]{2}'
        ]

        social_proof_found = []
        for pattern in social_proof_indicators:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                social_proof_found.extend(matches)

        metrics["social_proof_mentions"] = len(social_proof_found)

        return {"issues": issues, "metrics": metrics}

    def calculate_scores(self):
        """Calcula scores basados en los issues encontrados."""
        print("📊 Calculando scores...")

        # Contar issues por severidad
        severity_counts = {
            "critical": len(self.results["issues"]["critical"]),
            "high": len(self.results["issues"]["high"]),
            "medium": len(self.results["issues"]["medium"]),
            "low": len(self.results["issues"]["low"])
        }

        # Calcular score general (0-100)
        penalties = {
            "critical": 15,
            "high": 10,
            "medium": 5,
            "low": 2
        }

        total_penalty = sum(
            severity_counts[sev] * penalties[sev]
            for sev in penalties.keys()
        )

        general_score = max(0, 100 - total_penalty)

        self.results["scores"]["general"] = general_score
        self.results["scores"]["severity_counts"] = severity_counts

        # Scores por categoría
        categories = ["seo", "accessibility", "performance", "security", "conversion"]
        for category in categories:
            category_issues = sum(
                len([i for i in self.results["issues"][sev] if i.get("category") == category])
                for sev in ["critical", "high", "medium", "low"]
            )

            category_score = max(0, 100 - (category_issues * 8))
            self.results["scores"][f"{category}_score"] = category_score

        # Determinar rating
        if general_score >= 90:
            rating = "A - Excelente"
        elif general_score >= 80:
            rating = "B - Bueno"
        elif general_score >= 70:
            rating = "C - Aceptable"
        elif general_score >= 60:
            rating = "D - Necesita mejoras"
        else:
            rating = "F - Crítico"

        self.results["scores"]["rating"] = rating

    def generate_recommendations(self):
        """Genera recomendaciones basadas en los hallazgos."""
        print("💡 Generando recomendaciones...")

        recs = []

        # Analizar patrones en los issues
        critical_count = len(self.results["issues"]["critical"])
        high_count = len(self.results["issues"]["high"])

        if critical_count > 0:
            recs.append({
                "priority": "CRÍTICO",
                "title": "Resolver issues críticos inmediatamente",
                "description": f"Hay {critical_count} issues críticos que requieren atención inmediata."
            })

        if high_count > 0:
            recs.append({
                "priority": "ALTO",
                "title": "Abordar issues de alta prioridad",
                "description": f"Hay {high_count} issues de alta prioridad que afectan significativamente la experiencia."
            })

        # Recomendaciones específicas basadas en métricas
        if self.results["scores"].get("seo_score", 100) < 80:
            recs.append({
                "priority": "ALTO",
                "title": "Mejorar optimización SEO",
                "description": "El score de SEO es bajo. Revisa meta tags, structured data y Open Graph."
            })

        if self.results["scores"].get("accessibility_score", 100) < 80:
            recs.append({
                "priority": "ALTO",
                "title": "Mejorar accesibilidad",
                "description": "El score de accesibilidad es bajo. Revisa ARIA attributes, alt text y navegación por teclado."
            })

        if self.results["scores"].get("performance_score", 100) < 80:
            recs.append({
                "priority": "MEDIO",
                "title": "Optimizar performance",
                "description": "El score de performance es bajo. Considera lazy loading, code splitting y optimización de imágenes."
            })

        self.results["recommendations"] = recs

    def run_audit(self) -> Dict[str, Any]:
        """Ejecuta todas las auditorías."""
        print("\n" + "="*60)
        print("🔍 AUDITORÍA COMPREHENSIVA - LANDING PAGE KITA")
        print("="*60 + "\n")

        # Ejecutar auditorías
        audits = [
            ("html_structure", self.audit_html_structure),
            ("css_resources", self.audit_css_resources),
            ("js_resources", self.audit_js_resources),
            ("images", self.audit_images),
            ("accessibility", self.audit_accessibility),
            ("seo", self.audit_seo),
            ("performance", self.audit_performance),
            ("conversion", self.audit_conversion)
        ]

        for audit_name, audit_func in audits:
            try:
                result = audit_func()

                # Categorizar issues por severidad
                for issue in result.get("issues", []):
                    severity = issue.get("severity", "info")
                    if severity in self.results["issues"]:
                        self.results["issues"][severity].append(issue)

                # Guardar métricas
                if audit_name not in self.results["metrics"]:
                    self.results["metrics"][audit_name] = {}
                self.results["metrics"][audit_name].update(result.get("metrics", {}))

            except Exception as e:
                print(f"❌ Error en {audit_name}: {str(e)}")
                self.results["issues"]["high"].append({
                    "severity": "high",
                    "category": "system",
                    "message": f"Error ejecutando auditoría {audit_name}: {str(e)}"
                })

        # Calcular scores y generar recomendaciones
        self.calculate_scores()
        self.generate_recommendations()

        print("\n" + "="*60)
        print("✅ AUDITORÍA COMPLETADA")
        print("="*60 + "\n")

        return self.results

    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Genera reporte en formato Markdown."""

        if output_path is None:
            output_path = self.base_path / f"AUDIT_LANDING_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        report = []
        report.append("# 🔍 Auditoría Comprehensiva - Landing Page Kita\n")
        report.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**URL:** {self.url}\n")
        report.append("\n---\n")

        # Executive Summary
        report.append("\n## 📊 Executive Summary\n")
        report.append(f"**Score General:** {self.results['scores']['general']}/100 - {self.results['scores']['rating']}\n")
        report.append("\n### Resumen de Issues\n")
        report.append(f"- 🔴 **Críticos:** {self.results['scores']['severity_counts']['critical']}\n")
        report.append(f"- 🟠 **Altos:** {self.results['scores']['severity_counts']['high']}\n")
        report.append(f"- 🟡 **Medios:** {self.results['scores']['severity_counts']['medium']}\n")
        report.append(f"- 🔵 **Bajos:** {self.results['scores']['severity_counts']['low']}\n")

        # Scores por categoría
        report.append("\n### Scores por Categoría\n")
        report.append(f"- **SEO:** {self.results['scores'].get('seo_score', 'N/A')}/100\n")
        report.append(f"- **Accesibilidad:** {self.results['scores'].get('accessibility_score', 'N/A')}/100\n")
        report.append(f"- **Performance:** {self.results['scores'].get('performance_score', 'N/A')}/100\n")
        report.append(f"- **Seguridad:** {self.results['scores'].get('security_score', 'N/A')}/100\n")
        report.append(f"- **Conversión:** {self.results['scores'].get('conversion_score', 'N/A')}/100\n")

        # Recomendaciones
        if self.results["recommendations"]:
            report.append("\n## 💡 Recomendaciones Prioritarias\n")
            for i, rec in enumerate(self.results["recommendations"], 1):
                report.append(f"\n### {i}. [{rec['priority']}] {rec['title']}\n")
                report.append(f"{rec['description']}\n")

        # Issues detallados por severidad
        report.append("\n## 🚨 Issues Detallados\n")

        for severity in ["critical", "high", "medium", "low"]:
            issues = self.results["issues"][severity]
            if issues:
                severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
                report.append(f"\n### {severity_emoji[severity]} {severity.upper()} ({len(issues)})\n")

                # Agrupar por categoría
                by_category = {}
                for issue in issues:
                    cat = issue.get("category", "other")
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append(issue)

                for category, cat_issues in by_category.items():
                    report.append(f"\n**{category.upper()}**\n")
                    for issue in cat_issues:
                        report.append(f"- {issue['message']}\n")
                        if "details" in issue:
                            report.append(f"  ```\n")
                            report.append(f"  {json.dumps(issue['details'], indent=2)}\n")
                            report.append(f"  ```\n")

        # Métricas detalladas
        report.append("\n## 📈 Métricas Detalladas\n")

        for audit_name, metrics in self.results["metrics"].items():
            report.append(f"\n### {audit_name.replace('_', ' ').title()}\n")

            for key, value in metrics.items():
                if isinstance(value, (dict, list)) and len(str(value)) > 100:
                    report.append(f"**{key}:**\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```\n")
                else:
                    report.append(f"- **{key}:** {value}\n")

        # Guardar reporte
        report_content = "".join(report)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"\n✅ Reporte generado: {output_path}")

        return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Auditoría comprehensiva de landing page")
    parser.add_argument("--url", default="http://localhost:8000/", help="URL de la landing page")
    parser.add_argument("--output", help="Ruta del archivo de salida")

    args = parser.parse_args()

    # Detectar base path
    base_path = Path(__file__).parent

    # Crear auditor
    auditor = LandingPageAuditor(base_path, args.url)

    # Ejecutar auditoría
    results = auditor.run_audit()

    # Generar reporte
    report_path = auditor.generate_report(args.output)

    # Mostrar resumen
    print("\n" + "="*60)
    print("📊 RESUMEN")
    print("="*60)
    print(f"Score General: {results['scores']['general']}/100 - {results['scores']['rating']}")
    print(f"\nIssues:")
    print(f"  🔴 Críticos: {results['scores']['severity_counts']['critical']}")
    print(f"  🟠 Altos: {results['scores']['severity_counts']['high']}")
    print(f"  🟡 Medios: {results['scores']['severity_counts']['medium']}")
    print(f"  🔵 Bajos: {results['scores']['severity_counts']['low']}")
    print(f"\nReporte guardado en: {report_path}")
    print("="*60 + "\n")

    # Return code basado en issues críticos
    if results['scores']['severity_counts']['critical'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
