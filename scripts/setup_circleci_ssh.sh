#!/bin/bash
# ============================================
# Setup CircleCI SSH Access to Production Server
# ============================================
# Este script agrega la clave pública de CircleCI
# al authorized_keys del usuario deploy
# ============================================

set -e

SERVER="159.203.124.1"
USER="deploy"

echo "============================================"
echo "🔑 SETUP CIRCLECI SSH ACCESS"
echo "============================================"
echo ""
echo "Servidor: $SERVER"
echo "Usuario: $USER"
echo ""

# Verificar que tenemos la clave pública
if [ -z "$CIRCLECI_PUBLIC_KEY" ]; then
    echo "❌ Error: Variable CIRCLECI_PUBLIC_KEY no definida"
    echo ""
    echo "Uso:"
    echo "  export CIRCLECI_PUBLIC_KEY='ssh-rsa AAAAB3N... circleci@...'"
    echo "  ./scripts/setup_circleci_ssh.sh"
    echo ""
    exit 1
fi

echo "✓ Clave pública de CircleCI encontrada"
echo ""

# Agregar clave al servidor
echo "📤 Agregando clave al servidor..."
ssh root@$SERVER << EOF
    # Asegurar que el usuario deploy existe
    if ! id "$USER" &>/dev/null; then
        echo "Creando usuario $USER..."
        useradd -m -s /bin/bash $USER
    fi

    # Crear directorio .ssh si no existe
    mkdir -p /home/$USER/.ssh
    chmod 700 /home/$USER/.ssh

    # Agregar la clave pública
    echo "$CIRCLECI_PUBLIC_KEY" >> /home/$USER/.ssh/authorized_keys

    # Configurar permisos correctos
    chmod 600 /home/$USER/.ssh/authorized_keys
    chown -R $USER:$USER /home/$USER/.ssh

    # Dar permisos sudo al usuario deploy (sin password)
    echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
    chmod 440 /etc/sudoers.d/$USER

    echo "✅ Clave SSH agregada correctamente"
EOF

echo ""
echo "============================================"
echo "✅ SETUP COMPLETADO"
echo "============================================"
echo ""
echo "Ahora puedes probar la conexión:"
echo "  ssh $USER@$SERVER 'echo Conexión exitosa'"
echo ""
