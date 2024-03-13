import streamlit as st
import speech_recognition as sr
import datetime as dt
# import requests
import pyttsx3

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    # Configuration des propriétés de la voix
    # engine.setProperty('rate', 150)  # Vitesse de la parole (mots par minute)
    # engine.setProperty('volume', 1)   # Volume de la voix (0.0 à 1.0)
    # engine.setProperty('pitch', 50)  # Hauteur de la voix
    # engine.setProperty('gender', 'female')  # Voix féminine

    engine.runAndWait()

def main():
    st.title("Assistant Vocal Streamlit")
    st.write("Appuyez sur le bouton pour parler et écouter la réponse")

    recognizer = sr.Recognizer()

    if st.button("Parler"):
        with sr.Microphone() as source:
            st.write("Nettoyage du bruit ambiant... Veuillez patienter!")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            st.write("Dites quelque chose!")
            audio = recognizer.listen(source)
            st.write("Reconnaissance en cours.... ")

        try:
            text = recognizer.recognize_google(audio, language='fr-FR')
            st.write("Vous avez dit: " + text)
            st.write("Traitement audio en cours...")
            speak("Vous avez dit: " + text)
            st.write("Réponse audio générée avec succès")
        except Exception as e:
            st.write("Erreur : " + str(e))

if __name__ == "__main__":
    main()
