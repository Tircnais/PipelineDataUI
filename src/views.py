import flet as ft
import os

class PipelineView:
    """
    Capa de Vista (MVC): Interfaz gráfica con scroll interno en archivos y scroll general en la ventana.
    """
    def __init__(self, page: ft.Page, controller):
        self.page = page
        self.controller = controller
        self._init_page_config()
        self._build_ui()

    def _init_page_config(self):
        self.lblTitulo = "Pipeline de Datos Excel"
        self.lblSubtitulo = "Consolida múltiples archivos Excel en uno solo."
        self.page.title = self.lblTitulo
        self.page.theme_mode = ft.ThemeMode.LIGHT
        
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.page.window.icon = icon_path

        self.page.padding = 20
        self.page.scroll = ft.ScrollMode.AUTO  # Scroll general de la ventana
        self.page.vertical_alignment = ft.CrossAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    def _build_ui(self):
        COLOR_PRIMARIO = ft.Colors.BLUE_700
        COLOR_INFO = ft.Colors.GREY_600
        COLOR_CARGA = ft.Colors.BLUE_600
        COLOR_TRANSPARENTE = ft.Colors.TRANSPARENT
        COLOR_LISTA = ft.Colors.GREY_300
        COLOR_SUBTITULO = ft.Colors.GREY_700
        COLOR_FONDO_BOX = ft.Colors.BLUE_50
        COLOR_FONDO_ARCH = ft.Colors.SECONDARY_CONTAINER

        # ListView con scroll interno exclusivo para la lista de archivos
        self.lv_archivos = ft.ListView(
            spacing=4,
            padding=ft.Padding.symmetric(horizontal=2),
            scroll=ft.ScrollMode.AUTO,
        )

        self.progress_bar = ft.ProgressBar(value=0.0, color=COLOR_CARGA, bgcolor=ft.Colors.BLUE_100, visible=False)
        self.progress_text = ft.Text("", size=12, weight=ft.FontWeight.W_500, color=COLOR_PRIMARIO, visible=False)
        
        self.resultado_texto = ft.Text("", size=14, selectable=True, expand=False)
        self.resultado_card = ft.Card(
            content=ft.Container(content=self.resultado_texto, padding=16),
            visible=False,
        )
        
        self.contador_text = ft.Text(
            "0 archivo(s) seleccionado(s)", size=12, color=COLOR_INFO
        )
        
        self.btn_procesar = ft.FilledButton(
            "Iniciar Consolidación", icon=ft.Icons.PLAY_ARROW, disabled=True,
        )

        self.btn_abrir_carpeta = ft.OutlinedButton(
            "Abrir carpeta", icon=ft.Icons.FOLDER_OPEN, visible=False,
        )

        def refrescar_lista():
            self.lv_archivos.controls.clear()
            for item in self.controller.lista_archivos:
                nombre = item["nombre"]
                subtitulo = item["ruta"] if item["ruta"] else "📦 cargado desde navegador"
                self.lv_archivos.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.INSERT_DRIVE_FILE, color=COLOR_PRIMARIO),
                        title=ft.Text(nombre, weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(subtitulo, size=10, color=COLOR_INFO),
                        trailing=ft.IconButton(
                            ft.Icons.CLOSE,
                            tooltip="Quitar archivo",
                            data=item["nombre"],
                            on_click=lambda e: self.controller.quitar_archivo(e, refrescar_lista),
                        ),
                        bgcolor=COLOR_FONDO_ARCH,
                    )
                )
            self.contador_text.value = f"{len(self.controller.lista_archivos)} archivo(s) seleccionado(s)"
            self.btn_procesar.disabled = len(self.controller.lista_archivos) == 0
            self.page.update()

        self.btn_procesar.on_click = lambda e: self.controller.procesar_consolida_datos(
            (self.resultado_texto, self.resultado_card, self.progress_bar, self.progress_text, self.btn_procesar, self.btn_abrir_carpeta),
            refrescar_lista
        )
        self.btn_abrir_carpeta.on_click = lambda e: self.controller.abrir_carpeta_resultado()

        zona_drop = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=48, color=COLOR_PRIMARIO),
                    ft.Text("Haz clic para seleccionar archivos Excel", size=16, weight=ft.FontWeight.W_500, color=COLOR_PRIMARIO),
                    ft.Text("Formatos admitidos: .xlsx  •  .xls", size=12, color=COLOR_INFO),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8
            ),
            on_click=lambda e: self.controller.abrir_selector(refrescar_lista),
            bgcolor=COLOR_FONDO_BOX,
            border=ft.Border.all(2, COLOR_PRIMARIO),
            border_radius=12,
            padding=ft.Padding.symmetric(vertical=16, horizontal=20),
            alignment=ft.Alignment.CENTER,
            ink=True,
            tooltip="Haz clic para seleccionar archivos Excel",
        )

        contenedor_lista = ft.Container(
            content=self.lv_archivos,
            border=ft.Border.all(1, COLOR_LISTA),
            border_radius=12,
            height=220,
            padding=4,
        )

        titulo = ft.Text(self.lblTitulo, size=28, weight=ft.FontWeight.BOLD, text_align=ft.Alignment.CENTER)
        subtitulo = ft.Text(self.lblSubtitulo, size=14, color=COLOR_SUBTITULO, text_align=ft.Alignment.CENTER)

        self.page.add(
            ft.ResponsiveRow(
                controls=[
                    ft.Container(content=titulo, padding=2, col={ft.ResponsiveRowBreakpoint.XS: 12}),
                    ft.Container(content=subtitulo, padding=2, col={ft.ResponsiveRowBreakpoint.XS: 12}),
                    ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                    ft.Container(content=zona_drop, padding=2, col={ft.ResponsiveRowBreakpoint.XS: 12}),
                    ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("Archivos seleccionados", weight=ft.FontWeight.BOLD, size=15),
                                self.contador_text,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        padding=2,
                        col={ft.ResponsiveRowBreakpoint.XS: 12},
                    ),
                    ft.Container(content=contenedor_lista, padding=2, col={ft.ResponsiveRowBreakpoint.XS: 12}),
                    ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                    ft.Container(
                        content=ft.Column(
                            [
                                self.btn_procesar,
                                self.progress_bar,
                                self.progress_text,
                                self.btn_abrir_carpeta,
                            ],
                            spacing=8,
                        ),
                        padding=2,
                        col={ft.ResponsiveRowBreakpoint.XS: 12},
                    ),
                    ft.Divider(height=16, color=COLOR_TRANSPARENTE),
                    ft.Container(content=self.resultado_card, padding=2, col={ft.ResponsiveRowBreakpoint.XS: 12}),
                ],
            ),
        )
        self.page.update()
