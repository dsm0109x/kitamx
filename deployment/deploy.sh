#!/bin/bash
# ============================================
# Kita Production Deployment Script
# ============================================
# Ejecutado por CircleCI via SSH
# NO requiere Docker - deployment directo
# ============================================

set -e  # Exit on error

echo "============================================"
echo "🚀 KITA PRODUCTION DEPLOYMENT"
echo "============================================"
echo ""

# Variables
PROJECT_DIR="/home/kita/kita"
VENV_DIR="$PROJECT_DIR/venv"
BRANCH="production"

# Timestamp para logs
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "⏰ Started at: $TIMESTAMP"
echo "👤 Running as: $(whoami)"
echo ""

# Cambiar al directorio del proyecto
cd $PROJECT_DIR

# ============================================
# 1. PULL LATEST CODE
# ============================================
echo "📦 1. Pulling latest code from $BRANCH..."
sudo -u kita git -C $PROJECT_DIR fetch origin $BRANCH
sudo -u kita git -C $PROJECT_DIR reset --hard origin/$BRANCH
COMMIT=$(sudo -u kita git -C $PROJECT_DIR rev-parse --short HEAD)
echo "   ✅ Code updated to commit: $COMMIT"
echo ""

# ============================================
# 2. INSTALL/UPDATE DEPENDENCIES
# ============================================
echo "📦 2. Installing dependencies..."
sudo -u kita $VENV_DIR/bin/pip install -r $PROJECT_DIR/requirements.txt --quiet --no-cache-dir
echo "   ✅ Dependencies installed"
echo ""

# ============================================
# 3. RUN MIGRATIONS
# ============================================
echo "🗄️  3. Running database migrations..."
sudo -u kita $VENV_DIR/bin/python $PROJECT_DIR/manage.py migrate --noinput
echo "   ✅ Migrations completed"
echo ""

# ============================================
# 4. COLLECT STATIC FILES
# ============================================
echo "📂 4. Collecting static files..."
sudo -u kita $VENV_DIR/bin/python $PROJECT_DIR/manage.py collectstatic --noinput --clear
echo "   ✅ Static files collected"
echo ""

# ============================================
# 5. RESTART SERVICES
# ============================================
echo "🔄 5. Restarting services..."

# Gunicorn (Django app)
echo "   → Restarting kita-gunicorn..."
sudo systemctl restart kita-gunicorn
sleep 2

# Celery worker
echo "   → Restarting kita-celery..."
sudo systemctl restart kita-celery
sleep 1

# Celery beat
echo "   → Restarting kita-celery-beat..."
sudo systemctl restart kita-celery-beat
sleep 1

echo "   ✅ All services restarted"
echo ""

# ============================================
# 6. VERIFY SERVICES
# ============================================
echo "🔍 6. Verifying services status..."

# Check systemd services
GUNICORN_STATUS=$(sudo systemctl is-active kita-gunicorn)
CELERY_STATUS=$(sudo systemctl is-active kita-celery)
BEAT_STATUS=$(sudo systemctl is-active kita-celery-beat)

echo "   Gunicorn: $GUNICORN_STATUS"
echo "   Celery:   $CELERY_STATUS"
echo "   Beat:     $BEAT_STATUS"

if [ "$GUNICORN_STATUS" != "active" ]; then
    echo "   ⚠️  WARNING: Gunicorn is not active!"
    sudo systemctl status kita-gunicorn --no-pager -l
fi

echo ""

# ============================================
# 7. CLEANUP
# ============================================
echo "🧹 7. Cleanup..."

# Limpiar archivos .pyc (ignorar errores de permisos)
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -delete 2>/dev/null || true

echo "   ✅ Cleanup completed"
echo ""

# ============================================
# DEPLOYMENT COMPLETE
# ============================================
END_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================"
echo "✅ DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "============================================"
echo "   Commit:  $COMMIT"
echo "   Started: $TIMESTAMP"
echo "   Ended:   $END_TIMESTAMP"
echo ""
echo "🌐 Application: https://kita.mx"
echo "============================================"

exit 0
