import flet as ft
import os
import asyncio
from controllers import PipelineController
from views import PipelineView

async def main(page: ft.Page):
    # 🔑 Ruta absoluta apuntando a PipelineDataUI\logs (fuera de src)
    ruta_logs = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
    
    controller = PipelineController(page, logs_path=ruta_logs)
    PipelineView(page, controller)

    if page.platform in [ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX, ft.PagePlatform.MACOS]:
        await asyncio.sleep(0.1)
        try:
            await page.window.center()
            page.update()
        except Exception:
            pass

if __name__ == "__main__":
    ft.run(main)
