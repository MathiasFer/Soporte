import pandas as pd
from bs4 import BeautifulSoup
import json
from datetime import datetime

# ---------------------------
# PARSEAR FECHA DEL HTML
# ---------------------------
def parse_html_datetime(date_str, time_str):
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
    last_user = "Sistema/Desconocido" # Guardamos el último usuario detectado

    history = soup.find("div", class_="history")

    for div in history.find_all("div", recursive=False):
        clases = div.get("class", [])

        if "service" in clases:
            # Si el service tiene una fecha (ej: 24 January 2026) la guardamos
            text_service = div.get_text(strip=True)
            # Intentamos ver si es una fecha (tiene longitud corta usualmente)
            if len(text_service) < 25: 
                current_date = text_service
            continue

        if "default" in clases:
            # 1. Intentar extraer nombre
            from_name_div = div.find("div", class_="from_name")
            
            if from_name_div:
                # Es un mensaje nuevo con nombre
                user = from_name_div.get_text(strip=True)
                last_user = user # Actualizamos el último usuario
            else:
                # Es un mensaje con clase 'joined', usamos el último nombre guardado
                user = last_user

            # 2. Extraer Hora
            time_div = div.find("div", class_="date")
            time = time_div.get_text(strip=True) if time_div else ""

            # 3. Extraer Contenido
            text_div = div.find("div", class_="text")
            content = text_div.get_text(" ", strip=True) if text_div else "[Multimedia]"

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
    return messages

    print("\n==============================")
    print("✅ TOTAL MENSAJES EXTRAIDOS:", len(messages))
    print("==============================\n")

    if len(messages) > 0:
        print("Primeros 5 mensajes parseados:")
        for m in messages[:5]:
            print(m["datetime"], "-", m["usuario"])

    return messages


# ---------------------------
# CARGAR TICKETS EXCEL
# ---------------------------
def load_tickets(excel_path):

    df = pd.read_excel(excel_path)

    print("\n==============================")
    print("📊 DEBUG EXCEL")
    print("==============================")

    print("\nPrimeras filas del Excel:")
    print(df.head())

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

    print("\nFechas convertidas:")
    print(df[[
        "ID de Ticket",
        "Fecha de creación (Ticket)",
        "Fecha de Resolución"
    ]].head())

    return df


# ---------------------------
# MATCH TICKETS Y MENSAJES
# ---------------------------
def build_ticket_documents(messages, tickets_df):

    documents = []

    print("\n==============================")
    print("🔗 DEBUG MATCH TICKETS")
    print("==============================")

    for _, row in tickets_df.iterrows():

        start = row["Fecha de creación (Ticket)"]
        end = row["Fecha de Resolución"]

        print("\n--------------------------------")
        print("🎫 Ticket:", row["ID de Ticket"])
        print("Inicio:", start)
        print("Fin:", end)

        if pd.isna(end):
            end = datetime.now()
            print("⚠️ Fecha resolución vacía → usando fecha actual")

        mensajes_ticket = []
        count = 0

        for m in messages:

            if start <= m["datetime"] <= end:
                mensajes_ticket.append({
                    "fecha": m["fecha"],
                    "hora": m["hora"],
                    "usuario": m["usuario"],
                    "contenido": m["contenido"]
                })
                count += 1

        print("📩 Mensajes encontrados:", count)

        if count == 0:
            print("⚠️ No hubo match. Primeros mensajes disponibles:")
            for m in messages[:5]:
                print("   →", m["datetime"])

        doc = {
            "ticket_id": row["ID de Ticket"],
            "categoria": row["Categoría (Ticket)"],
            "subcategoria": row["Subcategoría"],
            "producto": row["Nombre del Producto"],
            "prioridad": row["Prioridad"],
            "estado": row["Estado (Ticket)"],
            "creado": str(start),
            "resuelto": str(end),
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

messages = extract_messages(html_file)

tickets_df = load_tickets(excel_file)

ticket_docs = build_ticket_documents(messages, tickets_df)

print("\n==============================")
print("📦 RESUMEN FINAL")
print("==============================")

print("Total mensajes HTML:", len(messages))
print("Total tickets Excel:", len(tickets_df))

# Guardar JSON
with open("tickets_con_mensajes.json", "w", encoding="utf-8") as f:
    json.dump(ticket_docs, f, indent=2, ensure_ascii=False)

print("\n✅ JSON generado: tickets_con_mensajes.json")