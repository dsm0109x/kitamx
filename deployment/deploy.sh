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
PROJECT_DIR="/srv/kita"
VENV_DIR="$PROJECT_DIR/venv"
BRANCH="production"

# Timestamp para logs
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "⏰ Started at: $TIMESTAMP"
echo ""

# Cambiar al directorio del proyecto
cd $PROJECT_DIR

# ============================================
# 1. PULL LATEST CODE
# ============================================
echo "📦 1. Pulling latest code from $BRANCH..."
git fetch origin $BRANCH
git reset --hard origin/$BRANCH
COMMIT=$(git rev-parse --short HEAD)
echo "   ✅ Code updated to commit: $COMMIT"
echo ""

# ============================================
# 2. ACTIVATE VIRTUAL ENV
# ============================================
echo "🐍 2. Activating virtual environment..."
source $VENV_DIR/bin/activate
echo "   ✅ Virtual env activated"
echo ""

# ============================================
# 3. INSTALL/UPDATE DEPENDENCIES
# ============================================
echo "📦 3. Installing dependencies..."
pip install -r requirements.txt --quiet --no-cache-dir
echo "   ✅ Dependencies installed"
echo ""

# ============================================
# 4. RUN MIGRATIONS
# ============================================
echo "🗄️  4. Running database migrations..."
python manage.py migrate --noinput
echo "   ✅ Migrations completed"
echo ""

# ============================================
# 5. COLLECT STATIC FILES
# ============================================
echo "📂 5. Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "   ✅ Static files collected"
echo ""

# ============================================
# 6. RESTART SERVICES
# ============================================
echo "🔄 6. Restarting services..."

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
# 7. VERIFY SERVICES
# ============================================
echo "🔍 7. Verifying services status..."

# Check systemd services
GUNICORN_STATUS=$(systemctl is-active kita-gunicorn)
CELERY_STATUS=$(systemctl is-active kita-celery)
BEAT_STATUS=$(systemctl is-active kita-celery-beat)

echo "   Gunicorn: $GUNICORN_STATUS"
echo "   Celery:   $CELERY_STATUS"
echo "   Beat:     $BEAT_STATUS"

if [ "$GUNICORN_STATUS" != "active" ]; then
    echo "   ⚠️  WARNING: Gunicorn is not active!"
    sudo systemctl status kita-gunicorn --no-pager -l
fi

echo ""

# ============================================
# 8. CLEANUP
# ============================================
echo "🧹 8. Cleanup..."

# Limpiar archivos .pyc
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete

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
