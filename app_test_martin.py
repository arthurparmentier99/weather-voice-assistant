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
from langchain_community.llms import HuggingFaceHub, HuggingFaceEndpoint
from langchain.prompts import PromptTemplate
# from langchain.vectorstores import Chroma
from langchain_community.vectorstores import Chroma

import pyttsx3
import requests
import speech_recognition as sr
import streamlit as st
import streamlit.components.v1 as components

warnings.filterwarnings('ignore')

def remove_after_last_brace(text):
    # Index de la dernière accolade fermante
    last_brace_index = -1

    for i, char in enumerate(text):
        if char == '}':
            last_brace_index = i
    json_str = text[:last_brace_index+1]
    return json.loads(json_str)

# Clean le JSON
def clean_json(json_object,date,hour):
    tod_h = hour.strftime('%H')
    new_json = json_object
    if list(json_object.values()) == ['None','None','None']:
        return "Need to re-ask"
    if json_object["ville"] == 'None':
        new_json["ville"] = "Lyon"
    
    day_plus_five = date + dt.timedelta(days=5)
    if json_object["heure"] < tod_h : 
        json_object["heure"] = tod_h + 1
    if (json_object["date"] > day_plus_five.strftime('%Y/%m/%d')) & (json_object["date"] != 'None'):        
        new_json["date"] = day_plus_five.strftime('%Y/%m/%d')
    return new_json

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    # Configuration des propriétés de la voix
    # engine.setProperty('rate', 150)  # Vitesse de la parole (mots par minute)
    # engine.setProperty('volume', 1)   # Volume de la voix (0.0 à 1.0)
    # engine.setProperty('pitch', 50)  # Hauteur de la voix
    # engine.setProperty('gender', 'female')  # Voix féminine
    engine.runAndWait()

tod_date = dt.date.today()
tod_hour = dt.datetime.now()

# Fonction principale
def main():
    st.set_page_config(page_title="Assistant Météo Streamlit", page_icon=":partly_sunny:")

    st.title("Assistant Météo Streamlit")

    st.write("Appuyez sur le bouton pour parler et écouter la réponse")

    ###### Reconnaissance vocale ######
    recognizer = sr.Recognizer()

    if st.button("Parler"):
        try:
            text= 'quel temps fait il à berlin à 18h dans 2 jours'
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
            temp1 = """[INST]
        Tu dois extraire des informations de la phrase données.

        N'invente pas, et extrais dans un JSON valide la VILLE et la DATE et l'HEURE. Si tu ne sait pas, met 'None'.
        l'HEURE doit etre une heure valide.
        Aujourd'hui, nous sommes le {0} à {1}h.

        Le JSON doit avoir ce format:
        (
        "ville":"ville",
        "date":"YYYY/MM/DD",
        "heure":"HH"
        )

        ----- 
        """.format(tod_date.strftime('%Y/%m/%d'),tod_hour.strftime('%H'))
            temp2 = """
        Voici la requête :
            {query}

            [/INST]
        JSON:
"""

            templ = temp1 + temp2

            query = text

            # On instancie notre template de prompt où l'on indique que nos deux variables entrantes sont le contexte (documents) et la requête (question)
            promp_rag = PromptTemplate(input_variables=["query"], template=templ)
            chain = LLMChain(prompt=promp_rag, llm=llm,verbose=False)
            response = chain.invoke({"query": query})
            answer = response["text"].split("JSON:")[1]
            print(answer)
            data = remove_after_last_brace(answer)
            print(data)

            # On clean le JSON
            data = clean_json(data,tod_date,tod_hour)
            print(data)

            # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
            # data = json.loads(answer)
            lieu = data["ville"]
            date = data["date"]

            ###### Requête API à OpenWheaterMap ######
            st.write("Récupération de la météo en cours...")

            BASE_URL = "https://api.openweathermap.org/data/2.5/weather?"
            API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY")
            CITY = lieu

            # Si pas de date on récupère la météo actuelle
            if date == "None":
                url = f"{BASE_URL}&q={CITY}&appid={API_KEY}&lang=fr&units=metric"
            else:
                url = f"{BASE_URL}&q={CITY}&appid={API_KEY}&lang=fr&units=metric&dt={date}"
            response = requests.get(url).json()

            temp_celcius = response['main']['temp']
            temp_celcius = round(temp_celcius, 0)
            feels_like_celcius = response['main']['feels_like']
            feels_like_celcius = round(feels_like_celcius, 0)
            humidity = response['main']['humidity']
            wind_speed = response['wind']['speed']
            description = response['weather'][0]['description']
            icon = response['weather'][0]['icon']

            # Essayer d'extraire les informations sur le lever et le coucher du soleil
            try:
                sunrise = dt.datetime.utcfromtimestamp(response['sys']['sunrise'] + response['timezone']).strftime('%H:%M:%S')
                sunset = dt.datetime.utcfromtimestamp(response['sys']['sunset'] + response['timezone']).strftime('%H:%M:%S')
            except KeyError:
                # Si les informations ne sont pas disponibles, définir sunrise et sunset à None
                sunrise = None
                sunset = None

            # URL de l'icône météo
            image_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"

            # Afficher les informations dans Streamlit avec un cadre visuel
            st.title(f"Météo pour {lieu} le {date} ")

            # Utiliser un conteneur de colonnes pour organiser les informations
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🌡️ Température")
                st.write(f"{temp_celcius}°C")

                st.subheader("❄️ Ressenti")
                st.write(f"{feels_like_celcius}°C")

                st.subheader("💧 Humidité")
                st.write(f"{humidity}%")

            with col2:
                st.subheader("💨 Vitesse du vent")
                st.write(f"{wind_speed} m/s")

                if sunrise:
                    st.subheader("🌅 Levé du soleil")
                    st.write(sunrise)
                
                if sunset:
                    st.subheader("🌇 Couché du soleil")
                    st.write(sunset)

            # Afficher l'icône météo avec la description en dessous
            st.image(image_url, caption=description)

            ###### Nouveau prompt pour le retriever ######
            st.write("Préparation de Miss Météo...")
            template = """[INST]
        Présente moi les informations météorologiques comme si tu était un présentateur météo
        ----- 

        Voici la requête :
            {query}

            [/INST]
        JSON:
"""

            query = f"température en degré celcius:{temp_celcius},température ressenti:{feels_like_celcius},humidity:{humidity},wind speed:{wind_speed},sunrise:{sunrise},sunset:{sunset},description:{description}"

            # On instancie notre template de prompt où l'on indique que nos deux variables entrantes sont le contexte (documents) et la requête (question)
            promp_rag = PromptTemplate(input_variables=["query"], template=template)
            chain = LLMChain(prompt=promp_rag, llm=llm,verbose=False)
            response = chain.invoke({"query": query})
            answer = response["text"].split("JSON:")[1]

            # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
            reponse_a_lire = answer.split("}")[-1]
            reponse_a_lire = reponse_a_lire.replace("\n", "")
            reponse_a_lire = reponse_a_lire.strip()

            ###### Réponse vocale ######
            # texte = f"Il fait {description} à {CITY}. La température est de {temp_celcius} degrés. Le ressenti est de {feels_like_celcius} degrés. L'humidité est de {humidity} pourcent. La vitesse du vent est de {wind_speed} mètres par seconde. Le soleil se lève à {sunrise} et se couche à {sunset}."

            st.write("Traitement audio en cours...")
            speak(reponse_a_lire)
            st.write("Réponse audio générée avec succès")
        except Exception as e:
            st.write("Erreur : " + str(e))

if __name__ == "__main__":
    main()
