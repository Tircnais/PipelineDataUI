import flet as ft
import asyncio
from models import PipelineModel

class PipelineController:
    """
    Capa de Controlador (MVC): Maneja eventos, validaciones y la ventana de mapeo interactivo de columnas.
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
            result = await picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["xlsx", "xls"],
                dialog_title="Seleccionar archivos Excel",
                with_data=True  # 🔑 Solicitamos que Flet cargue los bytes en memoria de forma segura
            )
            
            files = result if isinstance(result, list) else getattr(result, "files", None)
            
            if not files:
                self.model.logger.info("ℹ️ El usuario canceló la selección de archivos.")
                return
            
            nombres_existentes = {x["nombre"] for x in self.lista_archivos}
            for f in files:
                nombre_archivo = getattr(f, "name", None)
                ruta_archivo = getattr(f, "path", None)
                file_bytes = getattr(f, "bytes", None)
                
                if not nombre_archivo:
                    nombre_archivo = "archivo.xlsx"

                if nombre_archivo in nombres_existentes:
                    self.model.logger.warning(f"⚠️ Archivo duplicado omitido: {nombre_archivo}")
                    continue
                
                # Priorizar ruta local si existe y no está vacía
                if ruta_archivo:
                    self.lista_archivos.append({"nombre": nombre_archivo, "ruta": ruta_archivo, "datos": None})
                    self.model.logger.info(f"➕ Archivo añadido (Local Path): {nombre_archivo} -> {ruta_archivo}")
                elif file_bytes:
                    # Si no hay ruta local pero sí bytes binarios (muy común en Flet moderno), los guardamos
                    self.lista_archivos.append({"nombre": nombre_archivo, "ruta": None, "datos": bytes(file_bytes)})
                    self.model.logger.info(f"➕ Archivo añadido (Bytes en memoria): {nombre_archivo}")
                else:
                    self.model.logger.error(f"❌ El archivo {nombre_archivo} no contiene ruta ni bytes válidos.")
            
            refrescar_callback()
        except Exception as ex:
            self.model.logger.error(f"❌ Error crítico en FilePicker: {str(ex)}")

    def procesar_consolida_datos(self, view_elements, refrescar_callback):
        """Verifica si se requiere mapeo de columnas antes de ejecutar la consolidación"""
        if not self.lista_archivos:
            return

        try:
            necesita_mapeo, columnas_por_archivo, todas_unicas = self.model.analizar_columnas_archivos(self.lista_archivos)
            
            if necesita_mapeo:
                self.model.logger.info("⚠️ Se detectaron estructuras de columnas diferentes. Solicitando mapeo al usuario...")
                self._mostrar_dialogo_mapeo(view_elements, refrescar_callback, columnas_por_archivo, todas_unicas)
            else:
                self.model.logger.info("ℹ️ Las columnas de los archivos son idénticas. Procesando directamente...")
                self._ejecutar_proceso(view_elements, refrescar_callback, mapeo_columnas=None)
        except Exception as ex:
            self.model.logger.error(f"❌ Error al analizar esquemas: {str(ex)}")
            snack = ft.SnackBar(content=ft.Text(f"Error analizando archivos: {str(ex)}"), bgcolor=ft.Colors.RED_700)
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()

    def _mostrar_dialogo_mapeo(self, view_elements, refrescar_callback, columnas_por_archivo, todas_unicas):
        """Crea una ventana flotante (AlertDialog) con altura y ancho adaptados de forma compacta"""
        (resultado_texto, resultado_card, progress_bar, progress_text, btn_procesar, btn_abrir_carpeta) = view_elements

        dropdowns_mapeo = {} # {(nombre_archivo, columna_original): Dropdown}
        columnas_tarjetas = []

        for nombre_arch, cols in columnas_por_archivo.items():
            elementos_archivo = [
                ft.Container(
                    content=ft.Text(f"📄 {nombre_arch}", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.BLUE_700),
                    padding=ft.Padding.only(bottom=8)
                )
            ]
            
            for col in cols:
                dd = ft.Dropdown(
                    label=f"Original: '{col}'",
                    options=[ft.dropdown.Option(estandar) for estandar in todas_unicas],
                    value=col if col in todas_unicas else todas_unicas[0],
                    width=240,
                    text_size=12,
                    dense=True,
                )
                dropdowns_mapeo[(nombre_arch, col)] = dd
                elementos_archivo.append(dd)
            
            tarjeta_archivo = ft.Container(
                content=ft.Column(elementos_archivo, spacing=10, tight=True),
                padding=12,
                bgcolor=ft.Colors.GREY_50,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=8,
                width=270,
            )
            columnas_tarjetas.append(tarjeta_archivo)

        # Contenedor horizontal dinámico
        fila_archivos_lado_a_lado = ft.Row(
            controls=columnas_tarjetas,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=15,
            tight=True,
        )

        def aplicar_mapeo_y_cerrar(e):
            mapeo_final = {}
            for (nombre_arch, col_orig), dd in dropdowns_mapeo.items():
                col_destino = dd.value
                if nombre_arch not in mapeo_final:
                    mapeo_final[nombre_arch] = {}
                mapeo_final[nombre_arch][col_orig] = col_destino

            self.model.logger.info(f"🔄 Mapeo de columnas configurado por el usuario: {mapeo_final}")

            dialogo.open = False
            self.page.update()
            self._ejecutar_proceso(view_elements, refrescar_callback, mapeo_columnas=mapeo_final)

        def cancelar_mapeo(e):
            dialogo.open = False
            self.page.update()
            btn_procesar.disabled = False
            btn_procesar.text = "Iniciar Consolidación"
            btn_procesar.icon = ft.Icons.PLAY_ARROW
            self.page.update()

        # Dimensiones dinámicas basadas estrictamente en la cantidad de archivos
        # 🔑 Cálculo de ancho exacto y ajustado sin espacio sobrante a la derecha
        num_archivos = len(columnas_por_archivo)
        ancho_tarjeta = 270
        espacio_tarjetas = 15
        padding_extra = 20
        ancho_dinamico = (num_archivos * ancho_tarjeta) + ((num_archivos - 1) * espacio_tarjetas) + padding_extra
        
        dialogo = ft.AlertDialog(
            title=ft.Text("Mapeo Inteligente de Columnas", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"Se detectaron {num_archivos} archivo(s) con estructuras diferentes. Asigna el equivalente:", size=13, color=ft.Colors.GREY_700),
                        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                        fila_archivos_lado_a_lado
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=ancho_dinamico,  # 🔑 Ancho exacto calculado a la medida de las tarjetas
                padding=5,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar_mapeo),
                ft.FilledButton("Confirmar y Consolidar", on_click=aplicar_mapeo_y_cerrar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialogo)
        dialogo.open = True
        self.page.update()

    def _ejecutar_proceso(self, view_elements, refrescar_callback, mapeo_columnas):
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
            await self.procesar_async(view_elements, refrescar_callback, mapeo_columnas)
        self.page.run_task(tarea_procesar)

    async def procesar_async(self, view_elements, refrescar_callback, mapeo_columnas):
        (resultado_texto, resultado_card, progress_bar, progress_text, btn_procesar, btn_abrir_carpeta) = view_elements

        self.model.logger.info(f"⏳ Iniciando consolidación de {len(self.lista_archivos)} archivo(s)...")

        snack_bar = ft.SnackBar(content=ft.Text("Procesando archivos y aplicando mapeo..."))
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

        def actualizar_UI_progreso(valor, mensaje):
            progress_bar.value = valor
            porcentaje_str = f"{int(valor * 100)}%"
            progress_text.value = f"{mensaje} ({porcentaje_str})"
            self.page.update()

        try:
            resultado = await self.model.procesar_archivos_async(
                self.lista_archivos, 
                mapeo_columnas=mapeo_columnas, 
                progress_callback=actualizar_UI_progreso
            )

            if resultado["estado"] == "Ok":
                self.ultima_ruta_archivo["valor"] = resultado["ruta"]
                resultado_texto.value = (
                    f"✅  Consolidación exitosa\n\n"
                    f"📄  Archivo:   {resultado['archivo']}\n"
                    f"📁  Ruta:      {resultado['ruta']}\n"
                    f"📊  Filas:     {resultado['filas']}\n"
                    f"🗂️  Columnas:  {resultado['columnas']}\n"
                    f"💾  Tamaño:    {resultado['tamaño']}"
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
            error_mjs = f"❌ Error al procesar: {str(ex)}"
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

    def abrir_carpeta_resultado(self):
        self.model.logger.info("📁 Usuario solicitó abrir la carpeta contenedora del resultado.")
        self.model.abrir_carpeta(self.ultima_ruta_archivo["valor"])
