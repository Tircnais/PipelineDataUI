import flet as ft
import os
import sys
import io
import pandas as pd
import logging
import warnings
from datetime import datetime
import asyncio

# Configuración de limpieza y logs
# Oculta advertencias lectura, ocasionados por "No tener formatos visuales"
warnings.filterwarnings("ignore", category=UserWarning)
# Crear el objeto logger que usarás en todo el script
logger = logging.getLogger(__name__)

# Configuración básica para consola y archivo
def configurar_logging(ruta_logs):
    if not os.path.exists(ruta_logs):
        os.makedirs(ruta_logs)
    archivo_log = os.path.join(
        ruta_logs, f"registro_{datetime.now().strftime('%Y%m%d')}.log"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(archivo_log), # Guarda en archivo
            logging.StreamHandler(sys.stdout), # Muestra en consola
        ],
    )

# 1. CAMBIO A ASYNC: La función principal debe ser asíncrona
def main(page: ft.Page):
    lblTitulo = "Pipeline de Datos Excel"
    lblSubtitulo = "Consolida múltiples archivos Excel en uno solo."
    page.title = lblTitulo
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.icon = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
    page.padding = 20
    # Scroll en la pagina
    page.scroll = ft.ScrollMode.AUTO
    # Centrar pantalla
    page.vertical_alignment = ft.CrossAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    configurar_logging("logs")
    
    # Variable global del estado de archivos
    lista_archivos = []
    # Ruta del último archivo generado
    ultima_ruta_archivo = {"valor": ""}
    
    # ── ColoreS de tema ──────────────────────────────────────────────────────
    COLOR_PRIMARIO  = ft.Colors.BLUE_700
    COLOR_EXITO     = ft.Colors.GREEN_700
    COLOR_ERROR     = ft.Colors.RED_700
    COLOR_FONDO_BOX = ft.Colors.BLUE_50
    COLOR_FONDO_ARCH = ft.Colors.SECONDARY_CONTAINER
    COLOR_INFO = ft.Colors.GREY_600
    COLOR_CARGA = ft.Colors.LIGHT_GREEN_ACCENT_400
    COLOR_TRANSPARENTE = ft.Colors.TRANSPARENT
    COLOR_LISTA = ft.Colors.GREY_300
    COLOR_SUBTITULO = ft.Colors.GREY_700
    COLOR_FONDO_MJS = ft.Colors.GREEN_ACCENT_100

    # ── Normalización de columnas ────────────────────────────────────────────
    def normalizar_columnas(df):
        mapa = {
            "id": "id",
            "ID": "id",
            "identificador": "id",
            "nombre": "nombres",
            "nombres": "nombres",
            "apellido": "apellidos",
            "apellidos": "apellidos",
            "telefono": "telefono",
            "telef": "telefono",
            "teléfono": "telefono",
            "dirección": "direccion",
            "direc": "direccion",
            "fecha gestion": "fecha_gestion"
        }
        logger.debug(f"Fin de normalizado de columnas")
        return df.rename(columns=mapa)
    
    # ── Widgets que se actualizan dinámicamente ──────────────────────────────
    lv_archivos = ft.ListView(
        spacing=4,
        padding=ft.Padding.symmetric(horizontal=2),
    )
    loading = ft.ProgressRing(width=25, height=25, stroke_width=5, color=COLOR_CARGA, visible=False)
        
    resultado_texto = ft.Text("", size=14, selectable=True, expand=False,)
    resultado_card = ft.Card(
        content=ft.Container(content=resultado_texto, padding=16),
        visible=False,
    )
    
    contador_text = ft.Text(
        "0 archivo(s) seleccionado(s)", size=12, color=COLOR_INFO
    )
    
    btn_procesar = ft.FilledButton(
        "Iniciar Consolidación", icon=ft.Icons.PLAY_ARROW, disabled=True,
    )

    btn_abrir_carpeta = ft.OutlinedButton(
        "Abrir carpeta", icon=ft.Icons.FOLDER_OPEN, visible=False,
    )
    
    msj_text = ft.Text(
        "", size=24, color=COLOR_INFO, visible=False, bgcolor = COLOR_FONDO_MJS
    )
    
    # 2. REFRESCAR LISTA ASYNC
    # ── Actualizar lista visual ──────────────────────────────────────────────
    def refrescar_lista():
        print("Refrescando lista de archivos")
        lv_archivos.controls.clear()
        for item in lista_archivos:
            nombre = item["nombre"]
            subtitulo = item["ruta"] if item["ruta"] else "📦 cargado desde navegador"
            lv_archivos.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=COLOR_PRIMARIO),
                    title=ft.Text(nombre, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(subtitulo, size=10, color=COLOR_INFO),
                    trailing=ft.IconButton(
                        ft.Icons.CLOSE,
                        tooltip="Quitar archivo",
                        data=item["nombre"],
                        on_click=quitar_archivo,
                    ),
                    bgcolor=COLOR_FONDO_ARCH,
                )
            )
        contador_text.value = f"{len(lista_archivos)} archivo(s) seleccionado(s)"
        btn_procesar.disabled = len(lista_archivos) == 0
        msj_text.visible = len(lista_archivos) >= 1
        page.update()
    
    def quitar_archivo(e):
        nombre = e.control.data
        lista_archivos[:] = [x for x in lista_archivos if x["nombre"] != nombre]
        refrescar_lista()    
    
    # ── FilePicker ───────────────────────────────────────────────────────────
    # ORDEN CORRECTO en Flet 0.84:
    # 1. Crear FilePicker
    # 2. Agregar a services
    # 3. page.update()  ← registra el control en el cliente JS
    # 1. crear
    # file_picker = ft.FilePicker()        # ✔ sin argumentos
    # 2. registrar
    # page.services.append(file_picker)    # ✔ registrar service
    # 3. renderizar
    # page.update()
    
    # 4. MANEJADOR DE CLIC ASYNC (Aquí se resuelve el RuntimeWarning)
    def abrir_selector(e):
        page.run_task(abrir_picker_async)

    async def abrir_picker_async():
        await asyncio.sleep(0)  # 🔑 da tiempo a registrar
        picker = ft.FilePicker()
        page.services.append(picker)
        page.update()
    
        # es obligatorio aquí para Flet 0.84.0
        print("🟢 Explorador de archivos")
        try:
            files = await picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["xlsx", "xls"],
                dialog_title="Seleccionar archivos Excel",
                with_data=page.web
            )
            print("Seleccionando archivos")
            if not files:
                return
            nombres_existentes = {x["nombre"] for x in lista_archivos}
            for f in files:
                if f.name in nombres_existentes:
                    continue
                if f.path:
                    # Desktop: tenemos ruta en disco
                    lista_archivos.append({"nombre": f.name, "ruta": f.path, "datos": None})
                elif f.data:
                    # Web: no hay path, usamos bytes
                    lista_archivos.append({"nombre": f.name, "ruta": None, "datos": bytes(f.data)})
            refrescar_lista()
        except Exception as e:
            print("Error picker:", e)
            msj_text.value = str(e)
            return
    
    
    async def procesar_async():
        if not lista_archivos:
            snack_bar = ft.SnackBar(content=ft.Text("No hay archivos seleccionados"))
            page.overlay.append(snack_bar)
            snack_bar.open = True
            page.update()
            return
        
        snack_bar = ft.SnackBar(content=ft.Text("Procesando archivos espere..."))
        page.overlay.append(snack_bar)
        snack_bar.open = True
        page.update()
        
        salida = {}
        try:
            # Transformación
            dataframes = []
            for item in lista_archivos:
                directorio = item["ruta"] if item["ruta"] else io.BytesIO(item["datos"])
                df_temp = pd.read_excel(directorio, engine="calamine", dtype=str)
                df_temp = normalizar_columnas(df_temp)
                dataframes.append(df_temp)

            # Concatenar primero
            df = pd.concat(dataframes, ignore_index=True)
            # Optimización de memoria: Eliminar duplicados ANTES de ordenar 
            df.drop_duplicates(inplace=True)
            if "fecha_gestion" in df.columns:
                # Convertir a datetime solo para ordenar si es necesario, 
                # o asegurar que el sort_values no sea sobre strings pesados
                df.sort_values("fecha_gestion", inplace=True)
            # Carga (Escritura)
            fecha_act = datetime.now().strftime("%Y%m%d%H%M%S")
            nombre_archivo = f"ReporteConsolidado_{fecha_act}.xlsx"
            logger.info(f"✅ {len(lista_archivos)} archivos. {len(df)} filas únicas.")
            # Creación del archivo "xlsxwriter" procesa los datos mas rápido
            with pd.ExcelWriter(nombre_archivo, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Consolidado")
            
            # Verificar si realmente existe
            if os.path.exists(nombre_archivo):
                ubicacionArch = os.path.abspath(nombre_archivo)
                tamArch = os.path.getsize(nombre_archivo)
                
                logger.info(f"✅ {len(lista_archivos)} archivos. {len(df)} filas únicas.")
                logger.info(f"✅ Archivo: {nombre_archivo} creado con éxito.")
                logger.info(f"📁 Ubicación: {ubicacionArch}")
                logger.info(f"📊 Tamaño: {tamArch} bytes")
                ultima_ruta_archivo["valor"] = ubicacionArch
                
                salida.update({
                    "estado": "Ok",
                    "mensaje": 'Archivo creado exitosamente',
                    "archivo": nombre_archivo,
                    "ruta": ubicacionArch,
                    "tamaño_bytes": tamArch,
                    "filas": len(df),
                    "columnas": len(df.columns),
                })
                
                resultado_texto.value = (
                    f"✅  Consolidación exitosa\n\n"
                    f"📄  Archivo:   {nombre_archivo}\n"
                    f"📁  Ruta:      {ubicacionArch}\n"
                    f"📊  Filas:     {len(df)}\n"
                    f"🗂️  Columnas:  {len(df.columns)}\n"
                    f"💾  Tamaño:   {tamArch:,} bytes"
                )
                # Se limpia la lista de archivos, con los que va a trabajar
                lista_archivos.clear()
                # Se limpia la lista de archivos, a nivel de pantalla
                refrescar_lista()
                
                resultado_texto.color = COLOR_EXITO
                btn_abrir_carpeta.visible = True
                msj_text.value = "🔽 Haga scroll o deslice 🔽"
                snack_bar = ft.SnackBar(
                    content=ft.Text(f"✅ Archivo creado: {nombre_archivo}"),
                    bgcolor=COLOR_EXITO,
                )
                page.overlay.append(snack_bar)
                snack_bar.open = True
                page.update()
            else:
                salida['estado'] = 'Error'
                salida['mensaje'] = '❌ El archivo no se encontró tras guardar.'
                # Simulación de éxito para el ejemplo:
                resultado_texto.value = salida['mensaje']
                resultado_texto.color = COLOR_ERROR
                btn_abrir_carpeta.visible = False
                msj_text.value = "🔽 Haga scroll o deslice 🔽"
                logger.error(f"{salida['estado']} {salida['mensaje']}")
                snack_bar = ft.SnackBar(content=ft.Text(salida['mensaje']))
                page.overlay.append(snack_bar)
                snack_bar.open = True
                # raise FileNotFoundError("El archivo no se encontró tras guardar.")
                page.update()
        except Exception as ex:
            errorMjs = f"❌ Error al crear el archivo"
            salida.update({"estado": "Error", "mensaje": errorMjs})
            resultado_texto.value = errorMjs
            resultado_texto.color = COLOR_ERROR
            btn_abrir_carpeta.visible = False
            msj_text.value = "🔽 Haga scroll o deslice 🔽"
            snack_bar = ft.SnackBar(content=ft.Text(errorMjs), bgcolor=COLOR_ERROR)
            page.overlay.append(snack_bar)
            snack_bar.open = True
            logger.error(f"❌ Error al procesar: {str(ex)}")
            page.update()
        finally:
            loading.visible = False
            msj_text.visible = True
            resultado_card.visible = True
            btn_procesar.disabled = True
            btn_procesar.text = "Iniciar Consolidación"
            btn_procesar.icon = ft.Icons.PLAY_ARROW
            page.update()
        
            
    # Lógica de procesamiento simplificada
    def procesar_consolida_datos(e):
        # revisar elementos
        loading.visible = True
        btn_abrir_carpeta.visible = False
        msj_text.visible = True
        resultado_card.visible = False
        btn_procesar.disabled = True
        # Cambios a elementos antes de renderizar
        msj_text.value = "🟢 Procesando..."
        btn_procesar.text = "Espere..."
        btn_procesar.icon = ft.Icons.HOURGLASS_TOP
        
        page.update()  # 🔑 FORZAR RENDER
        page.run_task(procesar_async)
    
    def abrir_carpeta(e):
        ruta = ultima_ruta_archivo["valor"]
        if ruta:
            carpeta = os.path.dirname(ruta)
            if sys.platform == "win32":
                os.startfile(carpeta)
            elif sys.platform == "darwin":
                os.system(f'open "{carpeta}"')
            else:
                os.system(f'xdg-open "{carpeta}"')
        page.update()
    
    # Acciones de click
    btn_procesar.on_click = procesar_consolida_datos
    btn_abrir_carpeta.on_click = abrir_carpeta
    
    
    # ── Layout ───────────────────────────────────────────────────────────────
    zona_drop = ft.Container(
        content= ft.Column(
            [
                ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=48, color=COLOR_PRIMARIO),
                ft.Text("Haz clic para seleccionar archivos Excel", size=16, weight=ft.FontWeight.W_500, color=COLOR_PRIMARIO),
                ft.Text("Formatos admitidos: .xlsx  •  .xls", size=12, color=COLOR_INFO),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8
        ),
        on_click=abrir_selector,
        bgcolor=COLOR_FONDO_BOX,
        border=ft.Border.all(2, COLOR_PRIMARIO),
        border_radius=12,
        padding=ft.Padding.symmetric(vertical=16, horizontal=20),
        alignment=ft.Alignment.CENTER,
        ink=True,
        tooltip="Haz clic para seleccionar archivos Excel",
    )
    
    # Se usa height fijo para el contenedor de la lista, o se omite para que crezca solo
    contenedor_lista = ft.Container(
        content=lv_archivos,
        border=ft.Border.all(1, COLOR_LISTA),
        border_radius=12,
        height=200,
        padding=4,
    )
    
    titulo = ft.Text(lblTitulo, size=28, weight=ft.FontWeight.BOLD, text_align=ft.Alignment.CENTER)
    subtitulo = ft.Text(lblSubtitulo, size=14, color=COLOR_SUBTITULO, text_align=ft.Alignment.CENTER),
    # Pantalla principal
    page.add(
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    content=titulo,
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                ft.Container(
                    content=subtitulo,
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                ft.Container(
                    # Zona de selección
                    content=zona_drop,
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                # Label para salidas
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text("Archivos seleccionados", weight=ft.FontWeight.BOLD, size=15),
                            contador_text,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                # Salidas visuales para el usuario
                ft.Container(
                    content=contenedor_lista,
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                ft.Container(
                    # Botón de búsqueda
                    content=ft.Column(
                        [
                            ft.Row([btn_procesar, loading]),
                            ft.Row([btn_abrir_carpeta, msj_text]),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
                ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                ft.Container(
                    # Salida de la compilación
                    content=resultado_card,
                    padding=2,
                    col={
                        ft.ResponsiveRowBreakpoint.XS: 12,
                        ft.ResponsiveRowBreakpoint.MD: 12,
                        ft.ResponsiveRowBreakpoint.LG: 12,
                    },
                ),
            ],
        ),
    )
    page.update()


if __name__ == "__main__":
    # En Flet 0.80+, ft.run recibe la función directamente como argumento posicional
    # Forzar la vista web si el modo escritorio nativo da problemas de registro
    ft.run(main)
