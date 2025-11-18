# 📦 FORM COMPONENTS - GUÍA DE USO

Sistema unificado de componentes de formulario para Kita Platform.

## 🎯 Componentes Disponibles

### 1. `form_field.html` - Campo de Formulario Genérico

**Uso básico**:
```django
{% include 'components/form_field.html' with field=form.email %}
```

**Uso avanzado**:
```django
{% include 'components/form_field.html' with
    field=form.first_name
    help_text="Tu nombre como aparece en tu identificación"
    placeholder="Juan"
    autocomplete="given-name"
    input_class="custom-class"
    wrapper_class="mb-4"
%}
```

**Parámetros**:
- `field` (requerido): Campo del formulario Django
- `help_text`: Texto de ayuda personalizado
- `placeholder`: Placeholder del input
- `input_class`: Clases CSS adicionales para el input
- `wrapper_class`: Clases CSS adicionales para el wrapper
- `show_label`: Boolean (default: `True`)
- `required_indicator`: Boolean (default: `True`)
- `autocomplete`: Atributo HTML autocomplete
- `error_style`: `'bootstrap'` (default) o `'legacy'`

---

### 2. `password_field.html` - Campo de Contraseña con Toggle

**Uso básico**:
```django
{% include 'components/password_field.html' with field=form.password1 %}
```

**Uso avanzado**:
```django
{% include 'components/password_field.html' with
    field=form.password
    help_text="Mínimo 8 caracteres"
    autocomplete="current-password"
    error_style="legacy"
    show_toggle=True
%}
```

**Parámetros**:
- Mismos que `form_field.html` +
- `show_toggle`: Boolean (default: `True`) - Muestra botón de visibilidad
- `autocomplete`: Default `"current-password"`

---

## 🔄 MIGRACIÓN DE CÓDIGO EXISTENTE

### Patrón ANTES (Manual):

```django
<!-- ❌ Código repetitivo -->
<div class="form-group">
    <label for="{{ form.email.id_for_label }}">Email</label>
    <input type="email"
           name="email"
           id="{{ form.email.id_for_label }}"
           class="form-control {% if form.email.errors %}is-invalid{% endif %}">
    {% if form.email.errors %}
        <div class="invalid-feedback d-block">
            {{ form.email.errors|join:", " }}
        </div>
    {% endif %}
</div>
```

### Patrón DESPUÉS (Componente):

```django
<!-- ✅ Una sola línea -->
{% include 'components/form_field.html' with field=form.email %}
```

---

## 🎨 ESTILOS DE ERROR

### Bootstrap Style (Default)
Usa `.invalid-feedback` - Compatible con JavaScript moderno.

```django
{% include 'components/form_field.html' with field=form.email %}
```

Genera:
```html
<div class="invalid-feedback d-block" role="alert">Error message</div>
```

### Legacy Style
Usa `.form-error` - Compatible con `auth-*-enhanced.js`.

```django
{% include 'components/form_field.html' with field=form.email error_style="legacy" %}
```

Genera:
```html
<div class="form-error" role="alert">
    <small>Error message</small>
</div>
```

---

## 📋 PLAN DE MIGRACIÓN

### Fase 1: Password Reset (✅ LISTO)
```django
{% include 'components/form_field.html' with field=form.email error_style="legacy" %}
```

### Fase 2: Login (✅ LISTO)
```django
{% include 'components/form_field.html' with field=form.login error_style="legacy" %}
{% include 'components/password_field.html' with field=form.password error_style="legacy" %}
```

### Fase 3: Signup (EN PROGRESO)
```django
{% include 'components/form_field.html' with field=form.first_name error_style="legacy" %}
{% include 'components/form_field.html' with field=form.last_name error_style="legacy" %}
{% include 'components/form_field.html' with field=form.email error_style="legacy" %}
{% include 'components/password_field.html' with field=form.password1 error_style="legacy" %}
{% include 'components/password_field.html' with field=form.password2 error_style="legacy" %}
```

### Fase 4: Onboarding (USAR BOOTSTRAP STYLE)
```django
{# Ya usan el patrón correcto - migrar a componente sin error_style #}
{% include 'components/form_field.html' with field=form.rfc %}
```

---

## ✅ BENEFICIOS

1. **Menos código**: 15+ líneas → 1 línea
2. **Consistencia**: Mismo markup en toda la app
3. **WCAG compliant**: aria-describedby, role=alert automáticos
4. **Mantenibilidad**: Cambios centralizados
5. **Backward compatible**: Soporta código JavaScript existente
6. **Type-safe**: Django template tags validados

---

## 🔍 TESTING CHECKLIST

Antes de migrar un formulario, verificar:

- [ ] Identificar error_style usado (buscar en JS: `querySelector('.form-error')` o `.invalid-feedback`)
- [ ] Probar envío con errores (verificar que aparezcan mensajes)
- [ ] Probar validación JavaScript (si existe)
- [ ] Verificar aria-describedby apunta correctamente
- [ ] Probar toggle de password (si aplica)
- [ ] Verificar help_text se muestra correctamente
- [ ] Testing en mobile (responsive)

---

## 📝 NOTAS TÉCNICAS

### IDs Generados Automáticamente

```django
{% with field_id=field.id_for_label|default:field.html_name %}
{% with error_id="error_"|add:field_id %}
{% with help_id="help_"|add:field_id %}
```

Esto garantiza IDs únicos para WCAG compliance.

### CSS Clases Aplicadas

```html
<div class="form-group has-error">  <!-- has-error solo si field.errors -->
    <input class="form-control is-invalid">  <!-- is-invalid solo si field.errors -->
    <div class="invalid-feedback d-block">  <!-- d-block para forzar display -->
</div>
```

### JavaScript Selectors Compatibles

```javascript
// ✅ Ambos funcionan
input.parentElement.querySelector('.form-error');
input.parentElement.querySelector('.invalid-feedback');

// ✅ Clases en input también funcionan
input.classList.add('is-invalid');
input.classList.remove('is-invalid');
```

---

## 🚨 TROUBLESHOOTING

### Problema: "Error messages no aparecen"
**Solución**: Verificar que `field.errors` exista en el contexto. Revisar vista Django.

### Problema: "JavaScript no encuentra .form-error"
**Solución**: Agregar `error_style="legacy"` al include.

### Problema: "Password toggle no funciona"
**Solución**: Verificar que iconoir icons estén cargados. Revisar console de browser.

### Problema: "Help text siempre visible (incluso con errores)"
**Solución**: El componente oculta help_text cuando hay errores. Verificar lógica en component.

---

## 📞 SOPORTE

Para dudas o problemas con los componentes:
1. Revisar este README
2. Verificar templates existentes migrados
3. Consultar CSS en `brutalist-overrides.css`

**Última actualización**: 2025-10-21
