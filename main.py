import pandas as pd
from bs4 import BeautifulSoup
import json
from datetime import datetime

# ---------------------------
# PARSEAR FECHA DEL HTML
# ---------------------------
def parse_html_datetime(date_str, time_str):
    # Asegúrate de que el formato coincida (ej: "14 July 2025 17:54")
    full_str = f"{date_str} {time_str}"
    return datetime.strptime(full_str, "%d %B %Y %H:%M")


# ---------------------------
# EXTRAER MENSAJES DEL HTML
# ---------------------------
def extract_messages(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    messages = []
    current_date = ""
    last_user = "Sistema/Desconocido" 

    history = soup.find("div", class_="history")

    for div in history.find_all("div", recursive=False):
        clases = div.get("class", [])

        if "service" in clases:
            text_service = div.get_text(strip=True)
            if len(text_service) < 25: 
                current_date = text_service
            continue

        if "default" in clases:
            # 1. Extracción de nombre con persistencia
            from_name_div = div.find("div", class_="from_name")
            if from_name_div:
                user = from_name_div.get_text(strip=True)
                last_user = user 
            else:
                user = last_user

            # 2. Extraer Hora
            time_div = div.find("div", class_="date")
            time = time_div.get_text(strip=True) if time_div else ""

            # 3. Extraer Contenido y LIMPIAR espacios/saltos de línea (\n)
            text_div = div.find("div", class_="text")
            if text_div:
                # Obtenemos el texto y usamos split/join para normalizar espacios
                raw_text = text_div.get_text(" ", strip=True)
                content = " ".join(raw_text.split())
            else:
                content = "[Multimedia]"

            try:
                dt = parse_html_datetime(current_date, time)
                messages.append({
                    "datetime": dt,
                    "fecha": current_date,
                    "hora": time,
                    "usuario": user,
                    "contenido": content
                })
            except:
                continue
    
    print("\n==============================")
    print("✅ TOTAL MENSAJES EXTRAIDOS:", len(messages))
    print("==============================\n")
    return messages


# ---------------------------
# CARGAR TICKETS EXCEL
# ---------------------------
def load_tickets(excel_path):
    df = pd.read_excel(excel_path)

    print("\n==============================")
    print("📊 DEBUG EXCEL")
    print("==============================")

    # Convertimos a datetime manejando errores para identificar Pendientes (NaT)
    df["Fecha de creación (Ticket)"] = pd.to_datetime(
        df["Fecha de creación (Ticket)"],
        dayfirst=True,
        errors="coerce"
    )

    df["Fecha de Resolución"] = pd.to_datetime(
        df["Fecha de Resolución"],
        dayfirst=True,
        errors="coerce"
    )

    return df


# ---------------------------
# MATCH TICKETS Y MENSAJES
# ---------------------------
def build_ticket_documents(messages, tickets_df):
    documents = []
    
    # Ordenar por fecha para que la lógica de "siguiente ticket" funcione
    tickets_df = tickets_df.sort_values(by="Fecha de creación (Ticket)").reset_index(drop=True)

    print("\n==============================")
    print("🔗 MATCH TICKETS (MODO VECINDAD)")
    print("==============================")

    for i, row in tickets_df.iterrows():
        start = row["Fecha de creación (Ticket)"]
        end = row["Fecha de Resolución"]
        ticket_id = row["ID de Ticket"]

        # Lógica para tickets sin resolución o etiquetas de texto
        if pd.isna(end):
            # Si no hay fecha de resolución, el límite es el inicio del siguiente ticket
            if i + 1 < len(tickets_df):
                next_ticket_start = tickets_df.iloc[i + 1]["Fecha de creación (Ticket)"]
                # Un segundo antes para no solapar
                end = next_ticket_start - pd.Timedelta(seconds=1)
                print(f"🎫 Ticket {ticket_id} (Pendiente) -> Limitado hasta: {end}")
            else:
                # Si es el último, usamos la hora actual
                end = datetime.now()
                print(f"🎫 Ticket {ticket_id} (Último Pendiente) -> Usando fecha actual")

        # Filtrar mensajes
        mensajes_ticket = []
        for m in messages:
            # Colchón de 1 min al inicio por si el reporte fue segundos después del mensaje
            if (start - pd.Timedelta(minutes=1)) <= m["datetime"] <= end:
                mensajes_ticket.append({
                    "fecha": m["fecha"],
                    "hora": m["hora"],
                    "usuario": m["usuario"],
                    "contenido": m["contenido"]
                })

        doc = {
            "ticket_id": int(ticket_id) if not pd.isna(ticket_id) else None,
            "categoria": row.get("Categoría (Ticket)", "N/A"),
            "subcategoria": row.get("Subcategoría", "N/A"),
            "producto": row.get("Nombre del Producto", "N/A"),
            "prioridad": row.get("Prioridad", "N/A"),
            "estado": row.get("Estado (Ticket)", "N/A"),
            "creado": str(start),
            "resuelto": str(row["Fecha de Resolución"]) if not pd.isna(row["Fecha de Resolución"]) else "Pendiente",
            "mensajes": mensajes_ticket
        }
        documents.append(doc)

    return documents

# ---------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------

html_file = "messages.html"
excel_file = "tickets.xlsx"

print("\n🚀 INICIANDO PROCESO\n")

# 1. Extraer y limpiar mensajes
messages = extract_messages(html_file)

# 2. Cargar tickets
tickets_df = load_tickets(excel_file)

# 3. Vincular con lógica de vecindad
ticket_docs = build_ticket_documents(messages, tickets_df)

print("\n==============================")
print("📦 RESUMEN FINAL")
print("==============================")
print("Total mensajes HTML:", len(messages))
print("Total tickets Excel:", len(tickets_df))

# Guardar JSON
output_file = "tickets_con_mensajes.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(ticket_docs, f, indent=2, ensure_ascii=False)

print(f"\n✅ JSON generado exitosamente: {output_file}")