#!/bin/sh
# Instalador automático para ZouPlayer - GitHub: theking-cs

echo "********************************************************"
echo "* Instalando ZouPlayer v1.1                 *"
echo "* por theking-cs                         *"
echo "********************************************************"

# Definir variables
PLUGIN_NAME="ZouPlayer"
PLUGIN_PATH="/usr/lib/enigma2/python/Plugins/Extensions/$PLUGIN_NAME"
URL_ZIP="https://github.com/theking-cs/ZouPlayer/archive/refs/heads/main.zip"

# Limpiar instalaciones previas
echo "> Eliminando versiones antiguas si existen..."
rm -rf $PLUGIN_PATH
rm -rf /tmp/ZouPlayer.zip
rm -rf /tmp/ZouPlayer-main

# Descargar desde GitHub
echo "> Descargando última versión..."
wget --no-check-certificate $URL_ZIP -O /tmp/ZouPlayer.zip

# Descomprimir
echo "> Extrayendo archivos..."
unzip -q /tmp/ZouPlayer.zip -d /tmp/

# Mover a la ruta de Enigma2
echo "> Instalando en el sistema..."
mv /tmp/ZouPlayer-main/$PLUGIN_NAME /usr/lib/enigma2/python/Plugins/Extensions/

# Dar permisos de ejecución
echo "> Configurando permisos..."
chmod -R 755 $PLUGIN_PATH

# Limpieza final
rm -rf /tmp/ZouPlayer.zip /tmp/ZouPlayer-main

echo "********************************************************"
echo "* INSTALACIÓN COMPLETADA - REINICIANDO ENIGMA2       *"
echo "********************************************************"
killall -9 enigma2

exit 0
