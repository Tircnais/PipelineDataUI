import os
import sys
import logging
from datetime import datetime
import pandas as pd
import io
import asyncio

class PipelineModel:
    """
    Capa de Modelo (MVC): Gestiona logs en PipelineDataUI\logs y reporta progreso fluido paso a paso.
    """
    def __init__(self, logs_dir: str):
        self.logs_dir = logs_dir
        self._configurar_logging(self.logs_dir)

    def _configurar_logging(self, ruta_logs):
        if not os.path.exists(ruta_logs):
            os.makedirs(ruta_logs, exist_ok=True)
        
        archivo_log = os.path.join(
            ruta_logs, f"registro_{datetime.now().strftime('%Y%m%d')}.log"
        )
        
        logger = logging.getLogger("PipelineLogger")
        logger.setLevel(logging.INFO)

        if logger.hasHandlers():
            logger.handlers.clear()

        file_handler = logging.FileHandler(archivo_log, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

        self.logger = logger
        self.logger.info(f"📌 Sistema de logs inicializado en: {archivo_log}")

    async def procesar_archivos_async(self, lista_archivos, progress_callback=None):
        dataframes = []
        total = len(lista_archivos)
        
        for idx, item in enumerate(lista_archivos):
            nombre_corto = item['nombre']
            
            # Paso 1: Iniciando lectura del archivo
            base_progreso = idx / total
            ancho_archivo = 1.0 / total
            
            if progress_callback:
                progress_callback(base_progreso + (ancho_archivo * 0.1), f"Preparando archivo {idx + 1} de {total}: {nombre_corto}")
                await asyncio.sleep(0.05)

            self.logger.info(f"📖 Leyendo archivo ({idx + 1}/{total}): {nombre_corto}...")
            directorio = item["ruta"] if item["ruta"] else io.BytesIO(item["datos"])
            
            if progress_callback:
                progress_callback(base_progreso + (ancho_archivo * 0.3), f"Leyendo estructura de {nombre_corto}")
                await asyncio.sleep(0.05)

            def leer_excel():
                for engine_opt in [None, "openpyxl", "calamine"]:
                    try:
                        if engine_opt:
                            df = pd.read_excel(directorio, engine=engine_opt, dtype=str)
                        else:
                            df = pd.read_excel(directorio, dtype=str)
                        return df
                    except Exception:
                        continue
                return None

            df_temp = await asyncio.to_thread(leer_excel)
            
            if df_temp is None:
                raise ValueError(f"No se pudo leer el formato del archivo: {nombre_corto}")

            if progress_callback:
                progress_callback(base_progreso + (ancho_archivo * 0.7), f"Normalizando columnas de {nombre_corto}")
                await asyncio.sleep(0.05)

            df_temp.columns = [str(col).strip() for col in df_temp.columns]
            dataframes.append(df_temp)
            
            if progress_callback:
                progress_callback(base_progreso + ancho_archivo, f"Completado archivo {idx + 1} de {total}")
                await asyncio.sleep(0.05)

        if progress_callback:
            progress_callback(0.78, "⚡ Unificando y concatenando DataFrames...")
            await asyncio.sleep(0.08)

        self.logger.info("⚡ Unificando y concatenando DataFrames...")
        df = await asyncio.to_thread(pd.concat, dataframes, ignore_index=True, join='outer')
        
        if progress_callback:
            progress_callback(0.86, "🧹 Eliminando registros duplicados...")
            await asyncio.sleep(0.08)

        df.drop_duplicates(inplace=True)

        columnas_fecha = [c for c in df.columns if 'fecha' in c.lower() or 'gestion' in c.lower() or 'date' in c.lower()]
        if columnas_fecha:
            try:
                df.sort_values(columnas_fecha[0], inplace=True)
            except Exception:
                pass

        if progress_callback:
            progress_callback(0.93, "💾 Guardando archivo en 'Consolidado Histórico'...")
            await asyncio.sleep(0.08)

        # Ruta hacia la carpeta 'Consolidado Histórico' en la raíz del proyecto
        carpeta_salida = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Consolidado Histórico"))
        if not os.path.exists(carpeta_salida):
            os.makedirs(carpeta_salida, exist_ok=True)

        fecha_act = datetime.now().strftime("%Y%m%d%H%M%S")
        nombre_archivo = f"ReporteConsolidado_{fecha_act}.xlsx"
        ruta_completa = os.path.join(carpeta_salida, nombre_archivo)
        
        self.logger.info(f"💾 Escribiendo archivo Excel final en: {ruta_completa}...")
        
        def escribir_excel():
            with pd.ExcelWriter(ruta_completa, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Consolidado")

        await asyncio.to_thread(escribir_excel)

        if progress_callback:
            progress_callback(1.0, "✅ ¡Consolidación completada con éxito!")
            await asyncio.sleep(0.1)

        if os.path.exists(ruta_completa):
            tamArch_bytes = os.path.getsize(ruta_completa)
            tamArch_mb = tamArch_bytes / (1024 * 1024)  # 🔑 Conversión a MB
            
            self.logger.info(f"✅ Proceso completado con éxito. {len(df)} filas procesadas.")
            self.logger.info(f"📁 Ubicación: {ruta_completa}")
            self.logger.info(f"📊 Tamaño: {tamArch_mb:.2f} MB")
            
            return {
                "estado": "Ok",
                "mensaje": "Archivo creado exitosamente",
                "archivo": nombre_archivo,
                "ruta": ruta_completa,
                "tamaño": f"{tamArch_mb:.2f} MB",  # 🔑 Formato en MB
                "filas": len(df),
                "columnas": len(df.columns),
            }
        else:
            self.logger.error("❌ El archivo no se encontró tras guardar.")
            return {
                "estado": "Error",
                "mensaje": "❌ El archivo no se encontró tras guardar."
            }

    def abrir_carpeta(self, ruta: str):
        if ruta:
            carpeta = os.path.dirname(ruta) if os.path.isfile(ruta) else ruta
            if sys.platform == "win32":
                os.startfile(carpeta)
            elif sys.platform == "darwin":
                os.system(f'open "{carpeta}"')
            else:
                os.system(f'xdg-open "{carpeta}"')
