import os
import sys
import logging
from datetime import datetime
import pandas as pd
import io
import asyncio

class PipelineModel:
    """
    Capa de Modelo (MVC): Gestiona logs, validación de esquemas, transacciones atómicas y mapeo de columnas.
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

    def analizar_columnas_archivos(self, lista_archivos):
        """
        Analiza si los archivos tienen estructuras de columnas diferentes.
        Retorna (necesita_mapeo: bool, columnas_por_archivo: dict, todas_columnas_unicas: list)
        """
        columnas_por_archivo = {}
        conjuntos_columnas = []

        for item in lista_archivos:
            directorio = item["ruta"] if item["ruta"] else io.BytesIO(item["datos"])
            try:
                df_temp = pd.read_excel(directorio, nrows=0, dtype=str) # Solo lee la cabecera
                cols = [str(c).strip() for c in df_temp.columns]
                columnas_por_archivo[item["nombre"]] = cols
                conjuntos_columnas.append(set(cols))
            except Exception as ex:
                self.logger.error(f"❌ Error leyendo cabecera de {item['nombre']}: {str(ex)}")
                raise ValueError(f"No se pudo leer el archivo: {item['nombre']}")

        # Verificar si todos los archivos tienen exactamente el mismo conjunto de columnas
        primer_set = conjuntos_columnas[0]
        columnas_iguales = all(s == primer_set for s in conjuntos_columnas)

        # Recopilar todas las columnas únicas existentes entre los archivos
        todas_unicas = sorted(list(set(col for cols in columnas_por_archivo.values() for col in cols)))

        return not columnas_iguales, columnas_por_archivo, todas_unicas

    async def procesar_archivos_async(self, lista_archivos, mapeo_columnas=None, progress_callback=None):
        dataframes = []
        total = len(lista_archivos)
        
        for idx, item in enumerate(lista_archivos):
            nombre_corto = item['nombre']
            base_progreso = idx / total
            ancho_archivo = 1.0 / total
            
            if progress_callback:
                progress_callback(base_progreso + (ancho_archivo * 0.1), f"Leyendo {nombre_corto}")
                await asyncio.sleep(0.02)

            self.logger.info(f"📖 Leyendo archivo ({idx + 1}/{total}): {nombre_corto}...")
            directorio = item["ruta"] if item["ruta"] else io.BytesIO(item["datos"])
            
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

            df_temp.columns = [str(col).strip() for col in df_temp.columns]

            # Aplicar mapeo personalizado si el usuario lo proporcionó para este archivo
            if mapeo_columnas and nombre_corto in mapeo_columnas:
                mapa_archivo = mapeo_columnas[nombre_corto] # ej: {"Identificador": "ID", "id_registro": "ID"}
                df_temp.rename(columns=mapa_archivo, inplace=True)

            dataframes.append(df_temp)
            
            if progress_callback:
                progress_callback(base_progreso + ancho_archivo, f"Procesado {nombre_corto}")
                await asyncio.sleep(0.02)

        if progress_callback:
            progress_callback(0.78, "⚡ Unificando y concatenando DataFrames...")
            await asyncio.sleep(0.05)

        self.logger.info("⚡ Unificando y concatenando DataFrames...")
        df = await asyncio.to_thread(pd.concat, dataframes, ignore_index=True, join='outer')
        
        if progress_callback:
            progress_callback(0.86, "🧹 Eliminando registros duplicados...")
            await asyncio.sleep(0.05)

        df.drop_duplicates(inplace=True)

        columnas_fecha = [c for c in df.columns if 'fecha' in c.lower() or 'gestion' in c.lower() or 'date' in c.lower()]
        if columnas_fecha:
            try:
                df.sort_values(columnas_fecha[0], inplace=True)
            except Exception:
                pass

        if progress_callback:
            progress_callback(0.93, "💾 Guardando archivo (Transacción Atómica)...")
            await asyncio.sleep(0.05)

        carpeta_salida = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Consolidado Histórico"))
        if not os.path.exists(carpeta_salida):
            os.makedirs(carpeta_salida, exist_ok=True)

        fecha_act = datetime.now().strftime("%Y%m%d%H%M%S")
        nombre_archivo = f"ReporteConsolidado_{fecha_act}.xlsx"
        ruta_completa = os.path.join(carpeta_salida, nombre_archivo)
        
        # 🔑 Usamos una extensión .xlsx válida para el archivo temporal
        ruta_temporal = os.path.join(carpeta_salida, f"temp_{nombre_archivo}")
        
        self.logger.info(f"💾 Escribiendo archivo temporal en: {ruta_temporal}...")
        
        def escribir_excel():
            with pd.ExcelWriter(ruta_temporal, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Consolidado")

        await asyncio.to_thread(escribir_excel)
        
        # Transacción Atómica: Reemplazar el final si el temporal existe y es válido
        if os.path.exists(ruta_temporal):
            if os.path.exists(ruta_completa):
                os.remove(ruta_completa)
            os.rename(ruta_temporal, ruta_completa)
        else:
            raise IOError("El archivo temporal de consolidación no pudo ser generado.")

        if progress_callback:
            progress_callback(1.0, "✅ ¡Consolidación completada con éxito!")
            await asyncio.sleep(0.05)

        if os.path.exists(ruta_completa):
            tamArch_bytes = os.path.getsize(ruta_completa)
            tamArch_mb = tamArch_bytes / (1024 * 1024)
            
            self.logger.info(f"✅ Proceso completado con éxito. {len(df)} filas procesadas.")
            self.logger.info(f"📁 Ubicación: {ruta_completa}")
            self.logger.info(f"📊 Tamaño: {tamArch_mb:.2f} MB")
            
            return {
                "estado": "Ok",
                "mensaje": "Archivo creado exitosamente",
                "archivo": nombre_archivo,
                "ruta": ruta_completa,
                "tamaño": f"{tamArch_mb:.2f} MB",
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
