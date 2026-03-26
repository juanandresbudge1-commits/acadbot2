import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI
import PyPDF2

app = Flask(__name__)

KAPSO_API_KEY = os.environ.get("KAPSO_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def extract_pdf_text(pdf_path):
    text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def find_pdf(message):
    ramos_dir = "ramos"
    if not os.path.exists(ramos_dir):
        return None
    message = message.lower()
    for filename in os.listdir(ramos_dir):
        if not filename.endswith(".pdf"):
            continue
        name = filename.replace(".pdf", "").replace("_", " ")
        parts = name.split(" s")
        if len(parts) == 2:
            ramo = parts[0]
            seccion = parts[1]
            if ramo in message and seccion in message:
                return os.path.join(ramos_dir, filename)
    return None

def send_whatsapp(conversation_id, message):
    url = f"https://api.kapso.ai/v1/conversations/{conversation_id}/messages"
    headers = {
        "Authorization": f"Bearer {KAPSO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"content": message}
    response = requests.post(url, json=payload, headers=headers)
    print("Kapso response:", response.status_code, response.text)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received:", data)

    try:
        message = data.get("message", {}).get("content", "")
        conversation_id = data.get("conversation", {}).get("id", "")

        if not message or not conversation_id:
            return jsonify({"status": "ignored"}), 200

        pdf_path = find_pdf(message)

        if not pdf_path:
            reply = "No encontré el programa de ese ramo. Escríbeme el nombre y sección, por ejemplo: *calculo seccion 3*"
        else:
            pdf_text = extract_pdf_text(pdf_path)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"Eres AcadBot, asistente académico universitario. Responde preguntas sobre el programa del ramo usando solo esta información:\n\n{pdf_text}"},
                    {"role": "user", "content": message}
                ]
            )
            reply = response.choices[0].message.content

        send_whatsapp(conversation_id, reply)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
