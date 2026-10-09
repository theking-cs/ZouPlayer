# -*- coding: utf-8 -*-
import os, socket, urllib.request, json, shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse, parse_qs, quote
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.Label import Label
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Slider import Slider
from Components.Pixmap import Pixmap
from Components.ConfigList import ConfigListScreen
from Components.config import ConfigSelection, getConfigListEntry
from enigma import eServiceReference, eTimer, eDVBDB

PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/ZouPlayer"
M3U_FOLDER = os.path.join(PLUGIN_PATH, "m3u")
QR_PATH = os.path.join(PLUGIN_PATH, "donate.png")
BOUQUETS_FILE = "/etc/enigma2/bouquets.tv"
SETTINGS_FILE = os.path.join(PLUGIN_PATH, "player_setup.json")

VERSION = "1.5"

# Crear carpeta si no existe
if not os.path.exists(M3U_FOLDER):
    os.makedirs(M3U_FOLDER, exist_ok=True)

NEED_REFRESH = False
NEW_FILE_PATH = None

# ---------------- CONFIGURACIÓN DEL REPRODUCTOR ----------------
def get_saved_player():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f).get("player", "4097")
        except: pass
    return "4097"

def save_player(value):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"player": value}, f)
    except: pass

class ZouPlayerSettings(Screen, ConfigListScreen):
    skin = """
    <screen position="center,center" size="450,120" title="Reproductor">
        <widget name="config" position="10,20" size="430,30" scrollbarMode="showOnDemand" />
        <eLabel text="OK para guardar y salir" position="10,70" size="430,25" font="Regular;18" halign="center" transparent="1" />
    </screen>"""
    def __init__(self, session):
        Screen.__init__(self, session)
        choices = [("4097","GStreamer (4097)"),("5002","ExtPlayer3 (5002)"),("5001","GstPlayer (5001)")]
        self.player_choice = ConfigSelection(choices=choices, default=get_saved_player())
        ConfigListScreen.__init__(self, [(getConfigListEntry("Tipo de Service:", self.player_choice))], session)
        self["setup_actions"] = ActionMap(["SetupActions"], {"ok": self.save,"cancel": self.close}, -2)
    def save(self):
        save_player(self.player_choice.value)
        self.close()

# ---------------- FUNCIONES AUXILIARES ----------------
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "0.0.0.0"

# ---------------- SERVIDOR WEB ----------------
class UploadHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        global NEED_REFRESH
        try:
            if "/favicon.ico" in self.path:
                self.send_response(204); self.end_headers(); return

            files = sorted([f for f in os.listdir(M3U_FOLDER) if f.endswith(".m3u") or f.endswith(".m3u8")])
            if "/delete" in self.path:
                query = parse_qs(urlparse(self.path).query)
                if "file" in query:
                    try:
                        os.remove(os.path.join(M3U_FOLDER, query["file"][0]))
                        NEED_REFRESH = True
                    except: pass
                self.send_response(301); self.send_header("Location","/"); self.end_headers(); return

            rows = "".join(["<tr><td style='padding:15px; border-bottom:1px solid #334155;'>%s</td>"
                            "<td style='text-align:right; border-bottom:1px solid #334155;'>"
                            "<a href='/delete?file=%s'><button style='background:#ef4444; color:white; padding:10px 20px; border:0; border-radius:8px; cursor:pointer;'>BORRAR</button></a></td></tr>" % (f,f) for f in files])
            
            html = f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>" \
                   f"<style>body{{background:#0f172a;color:white;font-family:sans-serif;padding:15px;}}" \
                   f".container{{max-width:600px;margin:auto;background:#1e293b;padding:25px;border-radius:20px;}}" \
                   f"input{{width:100%;padding:15px;margin:10px 0;border-radius:10px;border:1px solid #334155;background:#0f172a;color:white;font-size:18px;}}" \
                   f"button.main{{width:100%;padding:18px;border-radius:10px;border:0;font-weight:bold;cursor:pointer;color:white;margin-top:10px;}}" \
                   f"table{{width:100%;margin-top:20px;border-collapse:collapse;}}</style></head>" \
                   f"<body><div class='container'><h2 style='text-align:center;color:#38bdf8;'>ZouPlayer Web Panel</h2>" \
                   f"<form method='post' enctype='multipart/form-data'><p>Subir M3U desde PC:</p>" \
                   f"<input type='file' name='f'><button class='main' style='background:#22c55e;'>SUBIR ARCHIVO</button></form>" \
                   f"<hr style='border:0;border-top:1px solid #334155;margin:30px 0;'>" \
                   f"<form method='post' action='/download'><p>Descargar URL Directa en el Deco:</p>" \
                   f"<input type='text' name='u' placeholder='http://...' required>" \
                   f"<input type='text' name='n' placeholder='Nombre de la lista' required>" \
                   f"<button class='main' style='background:#3b82f6;'>DESCARGAR AHORA</button></form><table>{rows}</table></div></body></html>"
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            print("ZouPlayer Web GET Error:", str(e))

    def do_POST(self):
        global NEED_REFRESH, NEW_FILE_PATH
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            
            if b"/download" in self.path.encode():
                params = parse_qs(body.decode('utf-8', errors='ignore'))
                url = params.get('u', [''])[0].strip()
                name = params.get('n', ['lista'])[0].strip().replace(" ", "_") + ".m3u"
                if url:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        full_path = os.path.join(M3U_FOLDER, name)
                        with open(full_path, "wb") as f:
                            f.write(resp.read())
                        NEW_FILE_PATH = name
                        NEED_REFRESH = True
            else:
                content_type = self.headers.get('Content-Type', '')
                if 'boundary=' in content_type:
                    boundary = content_type.split('boundary=')[1].strip().encode()
                    if boundary.startswith(b'"') and boundary.endswith(b'"'):
                        boundary = boundary[1:-1]
                    
                    parts = body.split(boundary)
                    for part in parts:
                        if b'filename="' in part:
                            try:
                                if b'\r\n\r\n' in part:
                                    header_part, file_content = part.split(b'\r\n\r\n', 1)
                                elif b'\n\n' in part:
                                    header_part, file_content = part.split(b'\n\n', 1)
                                else:
                                    continue
                                
                                file_content = file_content.rstrip(b'\r\n')
                                if file_content.endswith(b'--'):
                                    file_content = file_content[:-2]
                                file_content = file_content.rstrip(b'\r\n')
                                file_content = file_content.rstrip(b'\n')
                                
                                filename = header_part.split(b'filename="')[1].split(b'"')[0].decode('utf-8', errors='ignore')
                                if filename:
                                    filename = os.path.basename(filename)
                                    full_path = os.path.join(M3U_FOLDER, filename)
                                    with open(full_path, "wb") as f:
                                        f.write(file_content)
                                    NEW_FILE_PATH = filename
                                    NEED_REFRESH = True
                                    break
                            except Exception as sub_e:
                                print("ZouPlayer Subpart Error:", str(sub_e))
        except Exception as e:
            print("ZouPlayer Web POST Error:", str(e))

        self.send_response(301)
        self.send_header("Location", "/")
        self.end_headers()

class WebServer(Thread):
    def __init__(self): 
        Thread.__init__(self)
        self.daemon = True
        self.httpd = None

    def run(self):
        try:
            self.httpd = HTTPServer(("", 2804), UploadHandler)
            print("ZouPlayer WebServer started on port 2804")
            self.httpd.serve_forever()
        except Exception as e:
            print("ZouPlayer WebServer start error:", str(e))

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except: pass

server_instance = None

# ---------------- NAVEGADOR DE CARPETAS SEGURO (CUSTOM BROWSER) ----------------
class FolderBrowserScreen(Screen):
    skin = """
    <screen position="center,center" size="700,500" title="Seleccionar archivo M3U / M3U8">
        <widget name="list" position="20,20" size="660,400" font="Regular;22" itemHeight="35" scrollbarMode="showOnDemand" />
        <eLabel text="OK: Entrar / Seleccionar  |  EXIT: Volver" position="20,440" size="660,30" font="Regular;18" halign="center" foregroundColor="#38bdf8" transparent="1" />
    </screen>"""

    def __init__(self, session, currDir="/media/"):
        Screen.__init__(self, session)
        self.current_dir = currDir
        if not os.path.exists(self.current_dir):
            self.current_dir = "/"
        
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions"], {
            "ok": self.okClicked,
            "cancel": self.cancelClicked
        }, -1)
        
        self.onLayoutFinish.append(self.loadDirectory)

    def loadDirectory(self):
        content = []
        if self.current_dir != "/":
            content.append(("[..  (Directorio Superior)]", os.path.dirname(self.current_dir), True))
        
        try:
            items = sorted(os.listdir(self.current_dir))
            for item in items:
                if item.startswith("."): continue
                full_path = os.path.join(self.current_dir, item)
                if os.path.isdir(full_path):
                    content.append(("[%s]" % item, full_path, True))
                elif item.lower().endswith((".m3u", ".m3u8")):
                    content.append((item, full_path, False))
        except:
            pass

        self.directory_items = content
        self["list"].setList([x[0] for x in content])

    def okClicked(self):
        idx = self["list"].getSelectionIndex()
        if idx < 0 or idx >= len(self.directory_items): return
        
        name, path, is_dir = self.directory_items[idx]
        if is_dir:
            self.current_dir = path
            self.loadDirectory()
        else:
            self.close(path)

    def cancelClicked(self):
        self.close(None)


# ---------------- IPTVSCREEN (PRO SKIN) ----------------
class IPTVScreen(Screen):
    skin = """
<screen position="center,center" size="1100,700" title="ZouPlayer IPTV Pro v1.5">
    <!-- Fondo principal moderno y elegante -->
    <eLabel position="0,0" size="1100,700" backgroundColor="#090d16" zPosition="-5" />
    
    <!-- Barra superior de navegación / acciones (Estilo Pro Dashboard) -->
    <eLabel position="20,15" size="1060,55" backgroundColor="#131c2e" zPosition="-1" />
    <widget name="btn_red" position="30,22" size="240,40" font="Regular;18" halign="center" valign="center" backgroundColor="#dc2626" foregroundColor="white" />
    <widget name="btn_green" position="285,22" size="240,40" font="Regular;18" halign="center" valign="center" backgroundColor="#16a34a" foregroundColor="white" />
    <widget name="btn_yellow" position="540,22" size="240,40" font="Regular;18" halign="center" valign="center" backgroundColor="#ca8a04" foregroundColor="white" />
    <widget name="btn_blue" position="795,22" size="275,40" font="Regular;18" halign="center" valign="center" backgroundColor="#2563eb" foregroundColor="white" />

    <!-- Panel Izquierdo: Lista de Listas / Categorías / Canales -->
    <eLabel position="20,85" size="735,490" backgroundColor="#131c2e" zPosition="-1" />
    <widget name="list" position="35,100" size="705,460" font="Regular;22" itemHeight="42" backgroundColor="#0b111d" foregroundColor="#f8fafc" scrollbarMode="showOnDemand" />

    <!-- Panel Derecho: Tarjeta de Estado, QR e Información -->
    <eLabel position="770,85" size="310,490" backgroundColor="#131c2e" zPosition="-1" />
    <widget name="qrcode" position="800,105" size="250,250" alphatest="blend" />
    <eLabel text="Panel Web &amp; Soporte IPTV" position="780,370" size="290,25" font="Regular;18;bold" halign="center" foregroundColor="#38bdf8" transparent="1" />
    <widget name="ipdisplay" position="785,405" size="280,50" font="Regular;16" halign="center" foregroundColor="#e2e8f0" transparent="1" />
    <eLabel text="MENU: Ajustes | 1: Borrar M3U" position="780,480" size="290,65" font="Regular;15" halign="center" foregroundColor="#94a3b8" transparent="1" />

    <!-- Barra inferior: Progreso y Estado del Sistema -->
    <eLabel position="20,590" size="1060,90" backgroundColor="#131c2e" zPosition="-1" />
    <widget name="progress" position="40,605" size="1020,8" backgroundColor="#0b111d" foregroundColor="#38bdf8" />
    <widget name="status" position="40,622" size="1020,45" font="Regular;20" foregroundColor="#cbd5e1" transparent="1" />
</screen>
""" 

    def __init__(self, session):
        Screen.__init__(self, session)
        global server_instance

        # Botones y lista
        self["btn_red"] = Button("Servidor: ON")
        self["btn_green"] = Button("Exportar Cat.")
        self["btn_yellow"] = Button("Buscar")
        self["btn_blue"] = Button("Subir del Deco")
        self["list"] = MenuList([])
        self["ipdisplay"] = Label("http://%s:2804" % get_ip())
        self["status"] = Label("Selecciona una lista M3U para comenzar.")
        self["progress"] = Slider(0,100)
        self["qrcode"] = Pixmap()

        # Variables internas
        self.view = "files"
        self.history = []
        self.sections = {}
        self.current_sec = None
        self.categories = []
        self.channels = []
        self.chunk = 1000
        self.current_m3u_name = ""

        # Timers
        self.check_timer = eTimer()
        self.check_timer.callback.append(self.auto_check)
        self.check_timer.start(1500)

        self.timer_parse = eTimer()
        self.timer_parse.callback.append(self.parse_step)

        # Mapeo de acciones
        self["actions"] = ActionMap(["OkCancelActions","ColorActions","MenuActions","NumberActions"], {
            "ok": self.ok,
            "cancel": self.back,
            "red": self.toggle_server,
            "green": self.export_logic,
            "yellow": self.search_logic,
            "blue": self.import_from_deco,
            "menu": self.open_player_settings,
            "1": self.confirm_delete_m3u
        }, -1)

        # Iniciar servidor web
        if server_instance is None:
            server_instance = WebServer()
            server_instance.start()

        self.onLayoutFinish.append(self.load_initial)

    # ---------------- IMPORTAR DESDE EL DECO (BOTÓN AZUL) ----------------
    def import_from_deco(self):
        self.session.openWithCallback(self.import_selected_file, FolderBrowserScreen, currDir="/media/")

    def import_selected_file(self, chosen_path):
        if chosen_path and os.path.isfile(chosen_path):
            if chosen_path.lower().endswith((".m3u", ".m3u8")):
                try:
                    filename = os.path.basename(chosen_path)
                    dest_path = os.path.join(M3U_FOLDER, filename)
                    if os.path.abspath(chosen_path) != os.path.abspath(dest_path):
                        shutil.copyfile(chosen_path, dest_path)
                    
                    self.session.open(MessageBox, "¡Lista importada con éxito:\n%s" % filename, MessageBox.TYPE_INFO)
                    self.refresh_files()
                    self.start_parse(filename)
                except Exception as e:
                    self.session.open(MessageBox, "Error al importar: %s" % str(e), MessageBox.TYPE_ERROR)

    # ---------------- BORRAR M3U CON CONFIRMACIÓN ----------------
    def confirm_delete_m3u(self):
        if self.view != "files":
            self.session.open(MessageBox,"Solo puedes borrar archivos M3U desde la vista de archivos.",MessageBox.TYPE_INFO)
            return
        idx = self["list"].getSelectionIndex()
        if idx < 0: return
        filename = self.m3us[idx]
        self.session.openWithCallback(lambda confirmed: self.delete_selected_m3u(filename) if confirmed else None,
                                      MessageBox,"¿Seguro que quieres borrar: %s?" % filename,MessageBox.TYPE_YESNO)

    def delete_selected_m3u(self, filename):
        try:
            os.remove(os.path.join(M3U_FOLDER,filename))
            self.session.open(MessageBox,"Archivo borrado: %s" % filename,MessageBox.TYPE_INFO)
            self.refresh_files()
        except Exception as e:
            self.session.open(MessageBox,"Error al borrar: %s" % str(e),MessageBox.TYPE_ERROR)

    # ---------------- FUNCIONES DE UI ----------------
    def open_player_settings(self):
        self.session.open(ZouPlayerSettings)

    def auto_check(self):
        global NEED_REFRESH, NEW_FILE_PATH
        if NEED_REFRESH:
            NEED_REFRESH = False
            if NEW_FILE_PATH:
                fname = NEW_FILE_PATH
                NEW_FILE_PATH = None
                self.start_parse(fname)
            else:
                self.refresh_files()

    def load_initial(self):
        if os.path.exists(QR_PATH): self["qrcode"].instance.setPixmapFromFile(QR_PATH)
        self.refresh_files()

    def refresh_files(self):
        if not os.path.exists(M3U_FOLDER): return
        self.m3us = sorted([f for f in os.listdir(M3U_FOLDER) if f.endswith(".m3u") or f.endswith(".m3u8")])
        self["list"].setList(self.m3us)
        self.view = "files"
        self.history = []

    def toggle_server(self):
        global server_instance
        if server_instance:
            server_instance.stop()
            server_instance = None
        else:
            server_instance = WebServer()
            server_instance.start()
        self["btn_red"].setText("Servidor: %s" % ("ON" if server_instance else "OFF"))

    # ---------------- PARSEO DE LISTAS ----------------
    def start_parse(self, filename):
        path = os.path.join(M3U_FOLDER,filename)
        self.current_m3u_name = filename.replace(".m3u","").replace(".m3u8","")
        self.sections = {"LIVE":{},"VOD":{},"SERIES":{}}
        try:
            with open(path,"r",encoding="utf-8",errors="ignore") as f:
                self.parse_lines = f.readlines()
        except:
            self.parse_lines = []
        self.total_lines = len(self.parse_lines)
        self.parse_idx = 0
        if self.total_lines > 0:
            self["status"].setText("Categorizando lista...")
            self.timer_parse.start(5)

    def parse_step(self):
        end = min(self.parse_idx+self.chunk,self.total_lines)
        t_name = None
        t_group = "General"
        for i in range(self.parse_idx,end):
            line = self.parse_lines[i].strip()
            if line.startswith("#EXTINF"):
                if "," in line: t_name = line.split(",",1)[1]
                if 'group-title="' in line: t_group = line.split('group-title="')[1].split('"')[0]
            elif line.startswith("http") and t_name:
                low = line.lower()
                mode = "LIVE"
                if "/series/" in low: mode = "SERIES"
                elif "/movie/" in low or any(x in low for x in [".mp4",".mkv",".avi"]): mode = "VOD"
                self.sections[mode].setdefault(t_group,[]).append({"name":t_name,"url":line})
                t_name = None
        self.parse_idx = end
        if self.total_lines>0: self["progress"].setValue(int((self.parse_idx/self.total_lines)*100))
        if self.parse_idx >= self.total_lines:
            self.timer_parse.stop()
            self["progress"].setValue(0)
            self.view = "sections"
            self["list"].setList(["LIVE","VOD","SERIES"])
            self["status"].setText("Lista lista. Selecciona grupo.")

    # ---------------- EXPORTAR BOUQUETS ----------------
    def export_logic(self):
        idx = self["list"].getSelectionIndex()
        if idx < 0: return
        target_cat = None
        target_channels = []
        if self.view=="cats":
            if idx >= len(self.categories): return
            target_cat = self.categories[idx]
            target_channels = self.sections[self.current_sec].get(target_cat, [])
        elif self.view=="channels":
            if not self.history: return
            cat_idx = self.history[-1][1]
            if cat_idx >= len(self.categories): return
            target_cat = self.categories[cat_idx]
            target_channels = self.channels
        else:
            self.session.open(MessageBox,"Entra en LIVE, VOD o SERIES para elegir la categoría a exportar.",MessageBox.TYPE_INFO)
            return
        if target_cat and target_channels:
            try:
                p_id = get_saved_player()
                safe_name = "".join(c if c.isalnum() else "_" for c in target_cat)
                bouquet_path = "/etc/enigma2/userbouquet.%s.tv"%safe_name
                with open(bouquet_path,"w") as f:
                    f.write("#NAME %s\n"%target_cat)
                    for ch in target_channels:
                        encoded_url = quote(ch["url"],safe='')
                        f.write("#SERVICE %s:0:1:0:0:0:0:0:0:0:%s:%s\n"%(p_id,encoded_url,ch["name"]))
                        f.write("#DESCRIPTION %s\n"%ch["name"])
                entry_service='#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.%s.tv" ORDER BY bouquet\n'%safe_name
                lines=[]
                if os.path.exists(BOUQUETS_FILE):
                    with open(BOUQUETS_FILE,"r") as f: lines=f.readlines()
                if entry_service not in lines:
                    with open(BOUQUETS_FILE,"a") as f: f.write(entry_service)
                eDVBDB.getInstance().reloadBouquets()
                self.session.open(MessageBox,"Exportada categoría: %s con player %s"%(target_cat,p_id),MessageBox.TYPE_INFO)
            except Exception as e:
                self.session.open(MessageBox,"Error: "+str(e),MessageBox.TYPE_ERROR)

    # ---------------- SELECCIÓN Y REPRODUCCIÓN ----------------
    def ok(self):
        idx = self["list"].getSelectionIndex()
        if idx < 0: return
        if self.view=="files":
            self.history.append(("files",idx))
            self.start_parse(self.m3us[idx])
        elif self.view=="sections":
            self.history.append(("sections",idx))
            self.current_sec = ["LIVE","VOD","SERIES"][idx]
            self.categories = sorted(self.sections.get(self.current_sec,{}).keys())
            self.view = "cats"
            if not self.categories:
                self.session.open(MessageBox, "Esta sección está vacía.", MessageBox.TYPE_INFO)
                self.back()
                return
            self["list"].setList(["%s (%d)"%(c,len(self.sections[self.current_sec][c])) for c in self.categories])
        elif self.view=="cats":
            if idx >= len(self.categories): return
            self.history.append(("cats",idx))
            cat = self.categories[idx]
            self.channels = self.sections[self.current_sec].get(cat, [])
            if not self.channels:
                self.session.open(MessageBox, "No hay canales en esta categoría.", MessageBox.TYPE_INFO)
                self.history.pop()
                return
            self.view = "channels"
            self["list"].setList([c["name"] for c in self.channels])
        elif self.view=="channels":
            if idx >= len(self.channels): return
            p_id = int(get_saved_player())
            ch = self.channels[idx]
            ref = eServiceReference(p_id,0,ch["url"])
            ref.setName(ch["name"])
            self.session.nav.playService(ref)

    # ---------------- HISTORIAL Y BACK ----------------
    def back(self):
        if not self.history:
            self.close()
            return
        v,i = self.history.pop()
        if self.view=="channels":
            self.view="cats"
            if self.categories:
                self["list"].setList(["%s (%d)"%(c,len(self.sections[self.current_sec][c])) for c in self.categories])
            else:
                self["list"].setList([])
        elif self.view=="cats":
            self.view="sections"
            self["list"].setList(["LIVE","VOD","SERIES"])
        elif self.view=="sections":
            self.view="files"
            self.refresh_files()
        try:
            self["list"].moveToIndex(i)
        except:
            pass

    # ---------------- BÚSQUEDA ----------------
    def search_logic(self):
        self.session.openWithCallback(self.search_cb,VirtualKeyBoard,title="Buscar:")

    def search_cb(self,text):
        if text:
            res=[]
            for m in self.sections:
                for cat in self.sections[m]:
                    for ch in self.sections[m][cat]:
                        if text.lower() in ch["name"].lower():
                            res.append(ch)
            if res:
                self.history.append((self.view,self["list"].getSelectionIndex()))
                self.channels = res
                self.view = "channels"
                self["list"].setList([c["name"] for c in self.channels])

# ---------------- MAIN ----------------
def main(session, **kwargs):
    session.open(IPTVScreen)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="ZouPlayer iptvPro v%s" % VERSION,
            description="Play M3U and link URL (v%s)" % VERSION,
            where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU],
            fnc=main,
            icon="plugin.png"
        )
    ]
