import flet as ft
import asyncio
from models import PipelineModel

class PipelineController:
    """
    Capa de Controlador (MVC): Coordina la vista con las tareas asíncronas del modelo.
    """
    def __init__(self, page: ft.Page, logs_path: str):
        self.page = page
        self.model = PipelineModel(logs_path)
        self.lista_archivos = []
        self.ultima_ruta_archivo = {"valor": ""}
        self.model.logger.info("🚀 Aplicación iniciada y Controlador MVC cargado.")

    def quitar_archivo(self, e, refrescar_callback):
        nombre = e.control.data
        self.lista_archivos[:] = [x for x in self.lista_archivos if x["nombre"] != nombre]
        self.model.logger.info(f"🗑️ Archivo removido por el usuario: {nombre}")
        refrescar_callback()

    def abrir_selector(self, refrescar_callback):
        async def tarea_picker():
            await self.abrir_picker_async(refrescar_callback)
        self.page.run_task(tarea_picker)

    async def abrir_picker_async(self, refrescar_callback):
        await asyncio.sleep(0)
        picker = ft.FilePicker()
        self.page.services.append(picker)
        self.page.update()
        
        self.model.logger.info("📂 Apertura del explorador de archivos.")
        try:
            files = await picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["xlsx", "xls"],
                dialog_title="Seleccionar archivos Excel",
                with_data=self.page.web
            )
            if not files:
                self.model.logger.info("ℹ️ El usuario canceló la selección de archivos.")
                return
            
            nombres_existentes = {x["nombre"] for x in self.lista_archivos}
            for f in files:
                if f.name in nombres_existentes:
                    self.model.logger.warning(f"⚠️ Archivo duplicado omitido: {f.name}")
                    continue
                if f.path:
                    self.lista_archivos.append({"nombre": f.name, "ruta": f.path, "datos": None})
                    self.model.logger.info(f"➕ Archivo añadido (Local): {f.name} -> {f.path}")
                elif f.data:
                    self.lista_archivos.append({"nombre": f.name, "ruta": None, "datos": bytes(f.data)})
                    self.model.logger.info(f"➕ Archivo añadido (Web/Bytes): {f.name}")
            
            refrescar_callback()
        except Exception as ex:
            self.model.logger.error(f"❌ Error en FilePicker: {str(ex)}")

    async def procesar_async(self, view_elements, refrescar_callback):
        (resultado_texto, resultado_card, progress_bar, progress_text, btn_procesar, btn_abrir_carpeta) = view_elements

        if not self.lista_archivos:
            self.model.logger.warning("⚠️ Intento de consolidación sin archivos seleccionados.")
            snack_bar = ft.SnackBar(content=ft.Text("No hay archivos seleccionados"))
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()
            return

        self.model.logger.info(f"⏳ Iniciando consolidación de {len(self.lista_archivos)} archivo(s)...")

        snack_bar = ft.SnackBar(content=ft.Text("Procesando archivos, espere..."))
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

        def actualizar_UI_progreso(valor, mensaje):
            progress_bar.value = valor
            porcentaje_str = f"{int(valor * 100)}%"
            progress_text.value = f"{mensaje} ({porcentaje_str})"
            self.page.update()

        try:
            # Llamada asíncrona fluida
            resultado = await self.model.procesar_archivos_async(self.lista_archivos, progress_callback=actualizar_UI_progreso)

            if resultado["estado"] == "Ok":
                self.ultima_ruta_archivo["valor"] = resultado["ruta"]
                resultado_texto.value = (
                    f"✅  Consolidación exitosa\n\n"
                    f"📄  Archivo:   {resultado['archivo']}\n"
                    f"📁  Ruta:      {resultado['ruta']}\n"
                    f"📊  Filas:     {resultado['filas']}\n"
                    f"🗂️  Columnas:  {resultado['columnas']}\n"
                    f"💾  Tamaño:    {resultado['tamaño']}"  # 🔑 Muestra el tamaño en MB
                )
                self.lista_archivos.clear()
                refrescar_callback()

                resultado_texto.color = ft.Colors.GREEN_700
                btn_abrir_carpeta.visible = True
                
                snack_bar = ft.SnackBar(
                    content=ft.Text(f"✅ Archivo guardado en 'Consolidado Histórico': {resultado['archivo']}"),
                    bgcolor=ft.Colors.GREEN_700,
                )
                self.page.overlay.append(snack_bar)
                snack_bar.open = True
            else:
                resultado_texto.value = resultado["mensaje"]
                resultado_texto.color = ft.Colors.RED_700
                btn_abrir_carpeta.visible = False
                snack_bar = ft.SnackBar(content=ft.Text(resultado["mensaje"]), bgcolor=ft.Colors.RED_700)
                self.page.overlay.append(snack_bar)
                snack_bar.open = True

        except Exception as ex:
            error_mjs = "❌ Error al crear el archivo"
            resultado_texto.value = error_mjs
            resultado_texto.color = ft.Colors.RED_700
            btn_abrir_carpeta.visible = False
            snack_bar = ft.SnackBar(content=ft.Text(error_mjs), bgcolor=ft.Colors.RED_700)
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.model.logger.error(f"❌ Error crítico en procesar_async: {str(ex)}")
        finally:
            progress_bar.visible = False
            progress_text.visible = False
            resultado_card.visible = True
            btn_procesar.disabled = True
            btn_procesar.text = "Iniciar Consolidación"
            btn_procesar.icon = ft.Icons.PLAY_ARROW
            self.page.update()

    def procesar_consolida_datos(self, view_elements, refrescar_callback):
        (resultado_texto, resultado_card, progress_bar, progress_text, btn_procesar, btn_abrir_carpeta) = view_elements
        progress_bar.visible = True
        progress_bar.value = 0.05
        progress_text.visible = True
        progress_text.value = "Iniciando proceso... (5%)"
        btn_abrir_carpeta.visible = False
        resultado_card.visible = False
        btn_procesar.disabled = True
        btn_procesar.text = "Procesando..."
        btn_procesar.icon = ft.Icons.HOURGLASS_TOP
        self.page.update()

        async def tarea_procesar():
            await self.procesar_async(view_elements, refrescar_callback)
        self.page.run_task(tarea_procesar)

    def abrir_carpeta_resultado(self):
        self.model.logger.info("📁 Usuario solicitó abrir la carpeta contenedora del resultado.")
        self.model.abrir_carpeta(self.ultima_ruta_archivo["valor"])
