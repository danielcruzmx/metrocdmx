import re
import os
import unicodedata
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from swiplserver import PrologMQI
from fastapi.responses import FileResponse


app = FastAPI(title="API Metro CDMX - Prolog")

CARPETA_MAPAS = "iconos"

class SolicitudRuta(BaseModel):
    origen: str
    destino: str

# Función auxiliar para convertir "Pino Suarez" en "pino_suarez"
def normalizar_para_prolog(texto_bonito: str) -> str:
    # 1. Convertir a minúsculas y quitar espacios al inicio/final
    texto = texto_bonito.lower().strip()
    
    # 2. Quitar acentos (ej: "Martín Carrera" -> "martin carrera")
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    
    # 3. Reemplazar espacios intermedios por guiones bajos
    texto = texto.replace(" ", "_")
    return texto    

@app.get("/api/metro/mapa-completo")
def obtener_mapa_completo():
    ruta_mapa = os.path.join(CARPETA_MAPAS, "Mexico_City_metro.png")
    
    # Validamos si la imagen está guardada en el disco
    if not os.path.exists(ruta_mapa):
        raise HTTPException(status_code=404, detail="Archivo mapa_red.png no encontrado.")
        
    # Despachamos el archivo físico configurando el tipo MIME correcto para PNG
    return FileResponse(ruta_mapa, media_type="image/png")

@app.post("/api/metro/ruta")
def obtener_ruta(solicitud: SolicitudRuta):
    with PrologMQI() as mqi:
        with mqi.create_thread() as prolog_thread:
            
            prolog_thread.query("consult('metro.pl').")
            
            origen_atom = normalizar_para_prolog(solicitud.origen)
            destino_atom = normalizar_para_prolog(solicitud.destino)
            
            consulta = f"buscar_todas_las_rutas('{origen_atom}', '{destino_atom}', TextoAlternativa)."
            resultados_prolog = prolog_thread.query(consulta)
            
            if not resultados_prolog:
                raise HTTPException(
                    status_code=404, 
                    detail=f"No se encontró ninguna ruta entre '{solicitud.origen}' y '{solicitud.destino}'"
                )
            
            rutas_limpias = []
            for solucion in resultados_prolog:
                if 'TextoAlternativa' in solucion:
                    texto = solucion['TextoAlternativa'].strip()
                    if texto:
                        rutas_limpias.append(texto)
            
            # =================================================================
            # FUNCIÓN DE ORDENAMIENTO MAGICA EN PYTHON
            # =================================================================
            def extraer_total_estaciones(texto_ruta):
                # Buscamos el patrón "TOTAL ESTACIONES " seguido de uno o más dígitos
                match = re.search(r"TOTAL ESTACIONES\s+(\d+)", texto_ruta)
                if match:
                    return int(match.group(1)) # Devolvemos el número como entero
                
                # Si por alguna razón la regla de "misma línea" no dice "TOTAL ESTACIONES"
                # sino solo ", en X estaciones", buscamos ese número alternativo
                match_alt = re.search(r", en\s+(\d+)\s+estaciones", texto_ruta)
                if match_alt:
                    return int(match_alt.group(1))
                
                return 999 # Valor por defecto muy alto si no encuentra el número

            # Ordenamos la lista 'rutas_limpias' usando como clave el número extraído
            rutas_ordenadas = sorted(rutas_limpias, key=extraer_total_estaciones)
            # =================================================================
            
            return {
                "status": "success",
                "origen": solicitud.origen,
                "destino": solicitud.destino,
                "total_alternativas": len(rutas_ordenadas),
                "opciones": rutas_ordenadas # <-- Ahora viaja ordenado de menor a mayor
            }

# Añade estos dos endpoints al final de tu archivo main.py

@app.get("/api/metro/lineas")
def obtener_lineas():
    """Devuelve la lista de todas las líneas disponibles en el metro sin repetir."""
    with PrologMQI() as mqi:
        with mqi.create_thread() as prolog_thread:
            prolog_thread.query("consult('metro.pl').")
            resultado = prolog_thread.query("setof(L, E^N^linea(L, E, N), ListaLineas).")
            
            if not resultado:
                return {"lineas": []}
            
            # Diccionario para convertir los nombres técnicos de Prolog a nombres reales
            nombres_comerciales = {
                "rosa_1": "Línea 1 (Rosa)",
                "azul_2": "Línea 2 (Azul)",
                "verde_3": "Línea 3 (Verde)",
                "azul_4": "Línea 4 (Cian)",
                "amarilla_5": "Línea 5 (Amarilla)",
                "roja_6": "Línea 6 (Roja)",
                "naranja_7": "Línea 7 (Naranja)",
                "verde_8": "Línea 8 (Verde Oscuro)",
                "cafe_9": "Línea 9 (Café)",
                "morada_A": "Línea A (Morada)",
                "gris_verde_B": "Línea B (Verde/Gris)",
                "dorada_12": "Línea 12 (Dorada)"
            }
            
            # CORRECCIÓN AQUÍ: Accedemos con resultado[0]
            lineas_prolog = resultado[0]["ListaLineas"]
            
            # Convertimos cada línea a su nombre bonito
            lineas_bonitas = []
            for l in lineas_prolog:
                clave = l.lower()
                if clave in nombres_comerciales:
                    lineas_bonitas.append(nombres_comerciales[clave])
                else:
                    # Por si añadiste alguna línea nueva que no esté en el diccionario
                    lineas_bonitas.append(l.replace("_", " ").title())
            
            return {"lineas": lineas_bonitas}

@app.get("/api/metro/estaciones/{nombre_linea}")
def obtener_estaciones(nombre_linea: str):
    """Devuelve las estaciones de una línea específica ordenadas por su secuencia."""
    # Diccionario inverso para entender lo que manda App Inventor
    traductor_inverso = {
        "línea 1 (rosa)": "rosa_1",
        "línea 2 (azul)": "azul_2",
        "línea 3 (verde)": "verde_3",
        "línea 4 (cian)": "azul_4",
        "línea 5 (amarilla)": "amarilla_5",
        "línea 6 (roja)": "roja_6",
        "línea 7 (naranja)": "naranja_7",
        "línea 8 (verde oscuro)": "verde_8",
        "línea 9 (café)": "cafe_9",
        "línea a (morada)": "morada_A",
        "línea b (verde/gris)": "gris_verde_B",
        "línea 12 (dorada)": "dorada_12"
    }
    
    linea_clave = nombre_linea.lower().strip()
    linea_prolog = traductor_inverso.get(linea_clave, linea_clave.replace(" ", "_"))
    
    with PrologMQI() as mqi:
        with mqi.create_thread() as prolog_thread:
            prolog_thread.query("consult('metro.pl').")
            
            consulta = f"linea('{linea_prolog}', Estacion, Orden)."
            resultados = prolog_thread.query(consulta)
            
            if not resultados:
                raise HTTPException(status_code=404, detail="Línea no encontrada o vacía")
            
            # CORRECCIÓN AQUÍ TAMBIÉN: 'resultados' ya es una lista de diccionarios
            # Ordenamos los diccionarios internos por la clave 'Orden'
            resultados_ordenados = sorted(resultados, key=lambda x: x["Orden"])
            
            # Limpiamos los nombres de las estaciones para el usuario
            estaciones = [e["Estacion"].replace("_", " ").title() for e in resultados_ordenados]
            return {"linea": nombre_linea, "estaciones": estaciones}
