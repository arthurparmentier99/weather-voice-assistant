import datetime as dt
import os
import re
import warnings

import dotenv  # Pour lire nos variables environnements avec nos APIs
import json
# On importe quelques librairies de manipulation de données
import numpy as np
import pandas as pd
# On importe les modules nécessaires de LangChain
from langchain.chains import LLMChain, RetrievalQA
# from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub
from langchain.llms import HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
# from langchain.vectorstores import Chroma
from langchain_community.vectorstores import Chroma

import pyttsx3
import requests
import speech_recognition as sr
import streamlit as st

warnings.filterwarnings('ignore')

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    # Configuration des propriétés de la voix
    # engine.setProperty('rate', 150)  # Vitesse de la parole (mots par minute)
    # engine.setProperty('volume', 1)   # Volume de la voix (0.0 à 1.0)
    # engine.setProperty('pitch', 50)  # Hauteur de la voix
    # engine.setProperty('gender', 'female')  # Voix féminine
    engine.runAndWait()


# Fonction principale
def main():
    st.title("Assistant Météo Streamlit")
    st.write("Appuyez sur le bouton pour parler et écouter la réponse")

    ###### Reconnaissance vocale ######
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
            
            ###### Traitement de la requête ######
            st.write("Traitement de la requête en cours...")
            # On lit nos variables environnments avec nos clés APIs
            from dotenv import load_dotenv, find_dotenv
            _ = load_dotenv(find_dotenv())
            # On récupère notre llm
            repo_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"
            llm = HuggingFaceHub(repo_id=repo_id, model_kwargs={"temperature": 0.1, "max_new_tokens":500})

            # Création du template
            template = """[INST]
        Tu dois extraire des informations de la phrase données. N'invente pas, et extrais dans un JSON le lieu et la date.
        Aujourd'hui, nous sommes le 13/03/2024.
        Renvoit un JSON de la forme avec le "lieu" et la "date", ainsi que les informations additionnelles dans une liste
        ----- 

        Voici la requête :
            {query}

            [/INST]
        JSON:
"""

            query = text

            # On instancie notre template de prompt où l'on indique que nos deux variables entrantes sont le contexte (documents) et la requête (question)
            promp_rag = PromptTemplate(input_variables=["query"], template=template)
            chain = LLMChain(prompt=promp_rag, llm=llm,verbose=False)
            response = chain.invoke({"query": query})
            answer = response["text"].split("JSON:")[1]

            # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
            data = json.loads(answer)
            lieu = data["lieu"]
            date = data["date"]

            ###### Requête API à OpenWheaterMap ######
            BASE_URL = "https://api.openweathermap.org/data/2.5/weather?"
            API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY")
            CITY = lieu

            url = f"{BASE_URL}&q={CITY}&appid={API_KEY}&lang=fr&units=metric"
            response = requests.get(url).json()

            temp_celcius = response['main']['temp']
            temp_celcius = round(temp_celcius, 0)
            feels_like_celcius = response['main']['feels_like']
            feels_like_celcius = round(feels_like_celcius, 0)
            humidity = response['main']['humidity']
            wind_speed = response['wind']['speed']
            sunrise = response['sys']['sunrise'] + response['timezone']
            sunrise = dt.datetime.utcfromtimestamp(sunrise).strftime('%H:%M:%S')
            sunset = response['sys']['sunset'] + response['timezone']
            sunset = dt.datetime.utcfromtimestamp(sunset).strftime('%H:%M:%S')
            description = response['weather'][0]['description']

            ###### Réponse vocale ######
            texte = f"Il fait {description} à {CITY}. La température est de {temp_celcius} degrés. Le ressenti est de {feels_like_celcius} degrés. L'humidité est de {humidity} pourcent. La vitesse du vent est de {wind_speed} mètres par seconde. Le soleil se lève à {sunrise} et se couche à {sunset}."

            st.write("Traitement audio en cours...")
            speak(texte)
            st.write("Réponse audio générée avec succès")
        except Exception as e:
            st.write("Erreur : " + str(e))

if __name__ == "__main__":
    main()
