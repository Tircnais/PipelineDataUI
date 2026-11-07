import sys
import os

# Esto le indica a Python que añada la raíz del proyecto al path de búsqueda
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import PipelineModel
import pytest
import pandas as pd
import io

@pytest.fixture
def setup_pipeline_env(tmp_path):
    """Fixture para crear un entorno de logs temporal para las pruebas."""
    logs_dir = tmp_path / "logs"
    salida_dir = tmp_path / "Consolidado Histórico"
    model = PipelineModel(logs_dir=str(logs_dir))
    return model, tmp_path

def test_configuracion_logging(setup_pipeline_env):
    """Verifica que el sistema de logs cree el archivo correctamente."""
    model, tmp_path = setup_pipeline_env
    logs_dir = tmp_path / "logs"
    
    # Comprobar que la carpeta de logs existe y hay al menos un archivo .log
    assert os.path.exists(logs_dir)
    archivos_log = os.listdir(logs_dir)
    assert len(archivos_log) > 0
    assert archivos_log[0].endswith(".log")

@pytest.mark.asyncio
async def test_procesar_archivos_exitoso(setup_pipeline_env):
    """Prueba la consolidación exitosa de dos DataFrames simulados en bytes."""
    model, tmp_path = setup_pipeline_env
    
    # Crear dos DataFrames de prueba en memoria (bytes de Excel)
    df1 = pd.DataFrame({"ID": ["1", "2"], "Valor": ["A", "B"], "Fecha": ["2026-01-01", "2026-01-02"]})
    df2 = pd.DataFrame({"ID": ["3", "4"], "Valor": ["C", "D"], "Fecha": ["2026-01-03", "2026-01-04"]})
    
    buffer1 = io.BytesIO()
    buffer2 = io.BytesIO()
    
    with pd.ExcelWriter(buffer1, engine="xlsxwriter") as writer:
        df1.to_excel(writer, index=False, sheet_name="Hoja1")
    with pd.ExcelWriter(buffer2, engine="xlsxwriter") as writer:
        df2.to_excel(writer, index=False, sheet_name="Hoja1")
        
    lista_archivos = [
        {"nombre": "archivo1.xlsx", "ruta": None, "datos": buffer1.getvalue()},
        {"nombre": "archivo2.xlsx", "ruta": None, "datos": buffer2.getvalue()}
    ]
    
    # Callback de progreso simulado
    progresos = []
    def mock_progress(val, msg):
        progresos.append((val, msg))

    # Ejecutar procesamiento asíncrono
    resultado = await model.procesar_archivos_async(lista_archivos, progress_callback=mock_progress)
    
    # Verificaciones
    assert resultado["estado"] == "Ok"
    assert resultado["filas"] == 4
    assert os.path.exists(resultado["ruta"])
    assert len(progresos) > 0
    assert progresos[-1][0] == 1.0  # Asegurar que llegó al 100%

@pytest.mark.asyncio
async def test_procesar_archivo_corrupto(setup_pipeline_env):
    """Verifica que el pipeline lance una excepción si se intenta leer un archivo inválido."""
    model, tmp_path = setup_pipeline_env
    
    # Datos que no son un Excel válido
    archivo_malo = {"nombre": "corrupto.xlsx", "ruta": None, "datos": b"esto_no_es_un_excel"}
    lista_archivos = [archivo_malo]
    
    with pytest.raises(Exception):
        await model.procesar_archivos_async(lista_archivos)
