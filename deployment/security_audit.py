#!/usr/bin/env python3
"""
Django Security Configuration Audit
Verifica configuraciones críticas de seguridad antes de deployment
"""
import re
import sys
from pathlib import Path

def audit_settings():
    """Ejecuta audit de seguridad en settings.py"""

    settings_file = Path("kita/settings.py")

    if not settings_file.exists():
        print("❌ ERROR: kita/settings.py not found")
        sys.exit(1)

    with open(settings_file, 'r') as f:
        settings_content = f.read()

    print("=" * 60)
    print("🔐 DJANGO SECURITY CONFIGURATION AUDIT")
    print("=" * 60)
    print()

    critical_failures = []
    warnings = []

    # 1. SECRET_KEY
    print("1️⃣  SECRET_KEY Configuration")
    if re.search(r"SECRET_KEY\s*=\s*['\"][^{$]", settings_content):
        critical_failures.append("SECRET_KEY is hardcoded")
        print("   ❌ FAIL: SECRET_KEY is hardcoded")
    elif re.search(r"SECRET_KEY\s*=\s*env\(", settings_content):
        print("   ✅ PASS: SECRET_KEY from environment")
    else:
        warnings.append("SECRET_KEY unclear")
        print("   ⚠️  WARN: SECRET_KEY configuration unclear")

    # 2. DEBUG
    print("\n2️⃣  DEBUG Mode")
    if re.search(r"DEBUG\s*=\s*True(?!\s*#)", settings_content):
        critical_failures.append("DEBUG hardcoded to True")
        print("   ❌ FAIL: DEBUG=True hardcoded")
    elif re.search(r"DEBUG\s*=\s*env\(", settings_content):
        print("   ✅ PASS: DEBUG from environment")
    else:
        warnings.append("DEBUG unclear")
        print("   ⚠️  WARN: DEBUG not from environment")

    # 3. ALLOWED_HOSTS
    print("\n3️⃣  ALLOWED_HOSTS")
    if re.search(r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]?\*['\"]?\s*\]", settings_content):
        critical_failures.append("ALLOWED_HOSTS allows all")
        print("   ❌ FAIL: ALLOWED_HOSTS=['*'] is dangerous")
    elif re.search(r"ALLOWED_HOSTS\s*=\s*env", settings_content):
        print("   ✅ PASS: From environment")
    else:
        print("   ✅ PASS: Configured")

    # 4. Security Headers
    print("\n4️⃣  Security Headers")
    security_checks = {
        "SECURE_SSL_REDIRECT": r"SECURE_SSL_REDIRECT\s*=\s*True",
        "SESSION_COOKIE_SECURE": r"SESSION_COOKIE_SECURE\s*=\s*True",
        "CSRF_COOKIE_SECURE": r"CSRF_COOKIE_SECURE\s*=\s*True",
        "SECURE_HSTS_SECONDS": r"SECURE_HSTS_SECONDS\s*=\s*\d+",
        "X_FRAME_OPTIONS": r"X_FRAME_OPTIONS\s*=",
    }

    for check, pattern in security_checks.items():
        if re.search(pattern, settings_content):
            print(f"   ✅ {check}")
        else:
            warnings.append(f"{check} not set")
            print(f"   ⚠️  {check} not found")

    # 5. Database
    print("\n5️⃣  Database")
    if "sqlite3" in settings_content.lower():
        if re.search(r"if\s+DEBUG", settings_content):
            print("   ✅ PASS: SQLite only in DEBUG")
        else:
            warnings.append("SQLite in production")
            print("   ⚠️  WARN: May use SQLite in production")
    else:
        print("   ✅ PASS: Production database")

    # 6. debug_toolbar
    print("\n6️⃣  Debug Toolbar")
    if "debug_toolbar" in settings_content:
        warnings.append("debug_toolbar enabled")
        print("   ⚠️  WARN: debug_toolbar in INSTALLED_APPS")
    else:
        print("   ✅ PASS: Not installed")

    # Resultado final
    print("\n" + "=" * 60)
    print("📊 AUDIT RESULTS")
    print("=" * 60)

    if critical_failures:
        print(f"\n❌ CRITICAL FAILURES ({len(critical_failures)}):")
        for failure in critical_failures:
            print(f"   • {failure}")
        print("\n🚫 DEPLOYMENT BLOCKED - Fix critical issues")
        sys.exit(1)

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   • {warning}")
        print("\n💡 Review warnings - deployment will continue")

    print("\n✅ SECURITY AUDIT PASSED")
    print("   All critical security checks passed")
    print("=" * 60)

if __name__ == "__main__":
    audit_settings()
