import json
import pandas as pd
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Configuración inicial
load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"), 
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """Eres un experto en soporte de Golden Social Suite. Tu tarea es identificar el 'Espacio' afectado en un chat.
    DEFINICIÓN DE ESPACIO:
    Es el usuario, empresa o configuración específica en Alert, Scan, Kuntur o TokinAI (ejemplos: 'Gobierno Hidalgo', 'Macrosegmentación', 'Municipio Quito', etc.).

    REGLAS DE IDENTIFICACIÓN:
    1. CONTEXTO CLAVE: Busca menciones cerca de la palabra 'espacio', 'usuario', 'empresa' o respuestas a preguntas como '¿En qué espacio sucede?', 'al equipo de', 'a que usuario'.
    2. CASOS A IGNORAR: No tomar en cuenta términos o personas cuando se refieran a objetos de consulta (ejemplo: "la consulta Noboa" o "el feed de Noboa" NO es un espacio). Ignorar redes sociales típicas (Youtube, Facebook, etc.).
    3. CASO 1 (CLARO): Si el nombre del espacio se menciona de forma explícita como la cuenta afectada y no hay duda, devuelve solo el NOMBRE.
    4. CASO 2 (DUDA): Si se mencionan varios nombres o el contexto es ambiguo, devuelve 'POR REVISAR'.
    5. CASO 3 (VACÍO): Si no se hace referencia a ninguna cuenta cliente, devuelve 'VACÍO'.

    EJEMPLOS DE LOGICA:
    - Chat: "No cargan las menciones en el espacio de Municipio Quito." -> Resultado: MUNICIPIO QUITO
    - Chat: "El posteo de Noboa trae menos interacciones que el de ayer." -> Resultado: VACÍO (Noboa es el objeto consultado, no el espacio).
    - Chat: "¿En qué usuario reportan el fallo? En el de la Prefectura." -> Resultado: PREFECTURA

    IMPORTANTE: No confundas al técnico de soporte con el espacio. El espacio es el lugar donde ocurre el error técnico (Tampoco confundir con la plataforma Kuntur, Alert, Scan o TokinAI).

    Respuesta corta: Solo el nombre, 'POR REVISAR' o 'VACÍO'."""

def identificar_espacio_robusto(mensajes_list, ticket_id):
    if not mensajes_list:
        return ""

    # Consolidar chat para la IA
    chat_text = "\n".join([f"{m['usuario']}: {m['contenido']}" for m in mensajes_list])
    
    # Limitar contexto para eficiencia
    if len(chat_text) > 5000:
        chat_text = chat_text[:2500] + "\n[...] " + chat_text[-2500:]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Ticket ID {ticket_id}. Analiza este chat:\n\n{chat_text}"}
            ],
            temperature=0
        )
        resultado = response.choices[0].message.content.strip().upper()
        
        # Limpieza de la respuesta
        if "VACÍO" in resultado or "VACIO" in resultado or "N/A" in resultado:
            return ""
        if "REVISAR" in resultado:
            return "POR REVISAR"
        
        return resultado.replace('"', '').replace("'", "") # Limpiar comillas
    except Exception as e:
        return f"ERROR_API"

def procesar_mapeo(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    resultados = []
    stats = {"detectados": 0, "por_revisar": 0, "vacios": 0}

    print("\n" + "="*50)
    print(f"🚀 INICIANDO ANÁLISIS DE ESPACIOS | TOTAL: {total}")
    print("="*50 + "\n")

    for i, ticket in enumerate(data):
        t_id = ticket["ticket_id"]
        mensajes = ticket.get("mensajes", [])
        
        # Log de inicio de ticket
        print(f"[{i+1}/{total}] ID {t_id: <5} | Msg: {len(mensajes): <3}", end=" | ")
        
        espacio_detectado = identificar_espacio_robusto(mensajes, t_id)
        
        # Lógica de resumen y stats
        if espacio_detectado == "POR REVISAR":
            stats["por_revisar"] += 1
            print("⚠️  Dudoso -> POR REVISAR")
        elif espacio_detectado == "":
            stats["vacios"] += 1
            print("🌑 Sin info -> (Vacío)")
        else:
            stats["detectados"] += 1
            print(f"✅ Identificado -> {espacio_detectado}")

        resultados.append({
            "ID de Ticket": t_id,
            "Empresa": espacio_detectado
        })

        # --- GUARDADO INCREMENTAL ---
        # Se guarda el progreso actual en cada iteración
        pd.DataFrame(resultados).to_excel("mapeo_espacios_ia.xlsx", index=False)
        
        # --- LÓGICA DE ESPERA (Cada 30 peticiones) ---
        if (i + 1) % 30 == 0 and (i + 1) < total:
            print(f"\n⏳ Límite de 30 alcanzado. Esperando 60 segundos para evitar sobrecarga...")
            time.sleep(60)
            print("▶️ Reanudando proceso...\n")
        else:
            # Pequeño delay base entre peticiones normales
            time.sleep(0.5)

    print("\n" + "="*50)
    print("📊 RESUMEN DE PROCESAMIENTO FINAL")
    print("="*50)
    print(f"✨ Espacios Claros:  {stats['detectados']}")
    print(f"❓ Por Revisar:      {stats['por_revisar']}")
    print(f"∅  No Mencionados:   {stats['vacios']}")
    print("-" * 50)
    print("✅ Proceso completado. Archivo final actualizado: mapeo_espacios_ia.xlsx\n")

if __name__ == "__main__":
    procesar_mapeo("tickets_con_mensajes.json")