#!/bin/sh
# Instalador corregido para ZouPlayer - theking-cs

echo "********************************************************"
echo "* Instalando ZouPlayer v1.1                            *"
echo "********************************************************"

PLUGIN_NAME="ZouPlayer"
PLUGIN_PATH="/usr/lib/enigma2/python/Plugins/Extensions/$PLUGIN_NAME"

# Limpiar carpetas temporales y previas
rm -rf $PLUGIN_PATH
rm -rf /tmp/ZouPlayer.zip
rm -rf /tmp/ZouPlayer-main

echo "> Descargando desde GitHub..."
wget --no-check-certificate https://github.com/theking-cs/ZouPlayer/archive/refs/heads/main.zip -O /tmp/ZouPlayer.zip

echo "> Extrayendo archivos..."
unzip -q /tmp/ZouPlayer.zip -d /tmp/

# Esta es la parte corregida: 
# Movemos la carpeta que crea GitHub (ZouPlayer-main) directamente a la ruta de Enigma2 con el nombre correcto
echo "> Instalando en el sistema..."
mv /tmp/ZouPlayer-main $PLUGIN_PATH

# Dar permisos
echo "> Configurando permisos..."
chmod -R 755 $PLUGIN_PATH

# Limpieza
rm -rf /tmp/ZouPlayer.zip

echo "********************************************************"
echo "* INSTALACIÓN COMPLETADA - REINICIANDO ENIGMA2       *"
echo "********************************************************"
killall -9 enigma2

exit 0
