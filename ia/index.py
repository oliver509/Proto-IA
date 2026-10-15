import customtkinter as ctk
import sqlite3
import re
import unicodedata
from difflib import SequenceMatcher

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

DEFAULT_RESPONSES = {
    "bonjour": "Bonjour ! Comment puis-je t'aider aujourd'hui ?",
    "salut": "Salut ! Que puis-je faire pour toi ?",
    "merci": "Avec plaisir !",
    "au revoir": "Au revoir ! À bientôt.",
    "bye": "Au revoir ! À bientôt.",
    "ca va": "Je vais très bien, merci. Et toi ?",
    "comment ca va": "Je vais très bien, merci. Comment puis-je t'aider ?",
    "qui es tu": "Je suis ton assistant personnel, capable d'apprendre et de répondre à tes questions.",
    "quel est ton nom": "Je m'appelle Jarvis.",
    "help": "Tu peux me poser des questions, m'apprendre de nouvelles réponses ou utiliser /reset pour réinitialiser la mémoire.",
}


def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Initialisation de la base
def init_database():
    conn = sqlite3.connect("knowledge.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()


# Ajouter une nouvelle connaissance
def add_knowledge(question, answer):
    normalized_question = normalize_text(question)
    clean_answer = answer.strip()

    if not normalized_question or not clean_answer:
        return False

    conn = sqlite3.connect("knowledge.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO knowledge (question, answer) VALUES (?, ?)",
        (normalized_question, clean_answer),
    )
    conn.commit()
    conn.close()
    return True


# Rechercher une réponse dans la base
def get_answer(question):
    normalized_question = normalize_text(question)
    conn = sqlite3.connect("knowledge.db")
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM knowledge WHERE question = ?", (normalized_question,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def find_best_match(question):
    normalized_question = normalize_text(question)
    if not normalized_question:
        return None, 0.0

    conn = sqlite3.connect("knowledge.db")
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer FROM knowledge")
    rows = cursor.fetchall()
    conn.close()

    best_answer = None
    best_score = 0.0

    for stored_question, stored_answer in rows:
        score = SequenceMatcher(None, normalized_question, normalize_text(stored_question)).ratio()
        if score > best_score:
            best_score = score
            best_answer = stored_answer

    return best_answer, best_score


# Mode d'apprentissage
learning_mode = False
current_question = ""


def save_conversation(user_message, jarvis_response):
    with open("conversation_history.txt", "a") as file:
        file.write(f"Vous : {user_message}\nJarvis : {jarvis_response}\n\n")


# Variable pour suivre le nombre de messages échangés
message_count = 0


def speak_text(text):
    if pyttsx3 is None:
        return

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


def listen_microphone():
    if sr is None:
        if "chat_area" in globals():
            chat_area.configure(state='normal')
            chat_area.insert(ctk.END, "Jarvis : Le support vocal n'est pas installé. Installe speech_recognition et pyaudio.\n")
            chat_area.configure(state='disabled')
            chat_area.see(ctk.END)
        return

    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            if "chat_area" in globals():
                chat_area.configure(state='normal')
                chat_area.insert(ctk.END, "Jarvis : J'écoute...\n")
                chat_area.configure(state='disabled')
                chat_area.see(ctk.END)
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=8)

        text = recognizer.recognize_google(audio, language="fr-FR")
        user_entry.delete(0, ctk.END)
        user_entry.insert(0, text)
        send_message()
    except sr.UnknownValueError:
        if "chat_area" in globals():
            chat_area.configure(state='normal')
            chat_area.insert(ctk.END, "Jarvis : Je n'ai pas compris ce que tu as dit.\n")
            chat_area.configure(state='disabled')
            chat_area.see(ctk.END)
    except sr.RequestError:
        if "chat_area" in globals():
            chat_area.configure(state='normal')
            chat_area.insert(ctk.END, "Jarvis : Le service vocal est indisponible pour le moment.\n")
            chat_area.configure(state='disabled')
            chat_area.see(ctk.END)
    except Exception:
        if "chat_area" in globals():
            chat_area.configure(state='normal')
            chat_area.insert(ctk.END, "Jarvis : Le microphone n'est pas disponible.\n")
            chat_area.configure(state='disabled')
            chat_area.see(ctk.END)


# Fonction pour envoyer un message
def send_message():
    global learning_mode, current_question, message_count

    user_input = user_entry.get()
    if not user_input.strip():
        return
    chat_area.configure(state='normal')
    chat_area.insert(ctk.END, "Vous : " + user_input + "\n")
    user_entry.delete(0, ctk.END)

    # Mode d'apprentissage
    if learning_mode:
        if add_knowledge(current_question, user_input):
            response = "Merci, j'ai appris cela !"
            chat_area.insert(ctk.END, "Jarvis : " + response + "\n")
            speak_text(response)
        else:
            response = "Je n'ai pas pu enregistrer cette réponse."
            chat_area.insert(ctk.END, "Jarvis : " + response + "\n")
            speak_text(response)
        learning_mode = False
        current_question = ""
    else:
        response = get_response(user_input)
        if "Pouvez-vous m'apprendre" in response:
            learning_mode = True
            current_question = user_input
        chat_area.insert(ctk.END, "Jarvis : " + response + "\n")
        speak_text(response)

    # Augmenter le compteur de messages
    message_count += 1

    # Rafraîchir l'écran tous les 6 messages
    if message_count >= 7:
        chat_area.configure(state='normal')
        chat_area.delete(1.0, ctk.END)  # Effacer les anciens messages
        message_count = 0  # Réinitialiser le compteur de messages

    chat_area.configure(state='disabled')
    chat_area.see(ctk.END)


# Fonction pour obtenir une réponse
def get_response(text):
    normalized_text = normalize_text(text)
    if not normalized_text:
        return "Je n'ai pas bien compris votre message."

    for keyword, response in DEFAULT_RESPONSES.items():
        if normalized_text == keyword or normalized_text.startswith(keyword) or keyword in normalized_text:
            return response

    answer = get_answer(text)
    if answer:
        return answer

    best_answer, score = find_best_match(text)
    if best_answer and score >= 0.55:
        return best_answer

    # Si la réponse est inconnue, demander à l'utilisateur
    return "Je ne sais pas encore répondre à cela. Pouvez-vous m'apprendre ?"


def build_app():
    global root, chat_area, user_entry, send_button

    # Configuration de l'apparence de l'application
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Création de la fenêtre principale
    root = ctk.CTk()
    root.title("Jarvis 1.0.0")
    root.geometry("650x400")

    # Zone de texte pour afficher la conversation
    chat_area = ctk.CTkTextbox(root, wrap="word", state='disabled', width=520, height=250)
    chat_area.grid(row=0, column=0, columnspan=3, padx=10, pady=10)

    # Champ de saisie pour l'utilisateur
    user_entry = ctk.CTkEntry(root, width=300, placeholder_text="Tapez votre message ici...")
    user_entry.grid(row=1, column=0, padx=10, pady=10)

    # Boutons d'action
    send_button = ctk.CTkButton(root, text="Envoyer", command=send_message)
    send_button.grid(row=1, column=1, padx=10, pady=10)

    voice_button = ctk.CTkButton(root, text="🎤 Micro", command=listen_microphone)
    voice_button.grid(row=1, column=2, padx=10, pady=10)

    init_database()


if __name__ == "__main__":
    build_app()
    root.mainloop()