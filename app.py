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
    # TODO: Vérifier si "heure" est un multiple de 3
    if (json_object["date"] > day_plus_five.strftime('%Y/%m/%d')) & (json_object["date"] != 'None'):        
        new_json["date"] = day_plus_five.strftime('%Y/%m/%d')
    return new_json

# Catégorisation de la qualité de l'air
def categorize_pm25(value):
    if value < 20:
        return 'Bonne'
    elif 20 <= value < 50:
        return 'Correct'
    elif 50 <= value < 100:
        return 'Modérée'
    elif 100 <= value < 200:
        return 'Faible'
    else:
        return 'Mauvaise'


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
            temp1 = f"""[INST]
        Tu dois extraire des informations de la phrase données.

        N'invente pas, et extrais dans un JSON valide la VILLE et la DATE et l'HEURE. Si tu ne sait pas, met 'None'.
        l'HEURE doit etre une heure valide.
        Aujourd'hui, nous sommes le {tod_date.strftime('%Y/%m/%d')} à {tod_hour.strftime('%H')}h.

        Le JSON doit avoir ce format et YYYY vaudra toujours 2024:
        (
        "ville":"ville",
        "date":"YYYY-MM-DD",
        "heure":"HH"
        )

        ----- 
        """
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
            heure = data["heure"]

            ###### Requête API à OpenWheaterMap ######
            st.write("Récupération de la météo en cours...")

            BASE_URL = "https://api.openweathermap.org/data/2.5/weather?"
            API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY")
            CITY = lieu

            # Si pas de date on récupère la météo actuelle
            if date == "None":
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
                icon = response['weather'][0]['icon']
            else:
                url = f"https://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}&lang=fr&units=metric"
                response = requests.get(url).json()
                
                if heure == "None" or heure is None:
                    for dictionnaire in response['list']:
                        # Récupérer la date et l'heure du dictionnaire actuel
                        dt_txt = dictionnaire['dt_txt']
                        # Vérifier si la date et l'heure correspondent
                        if dt_txt.startswith(date) and "18" in dt_txt:
                            # Afficher le dictionnaire correspondant
                            print("Dictionnaire correspondant trouvé :")
                            print(dictionnaire)
                            temp_celcius = dictionnaire['main']['temp']
                            temp_celcius = round(temp_celcius, 0)
                            feels_like_celcius = dictionnaire['main']['feels_like']
                            feels_like_celcius = round(feels_like_celcius, 0)
                            humidity = dictionnaire['main']['humidity']
                            wind_speed = dictionnaire['wind']['speed']
                            description = dictionnaire['weather'][0]['description']
                            icon = dictionnaire['weather'][0]['icon']
                            break
                else:
                    print("else")
                    print(date)
                    print(type(date))
                    print(heure)
                    print(type(heure))
                    for dictionnaire in response['list']:
                        # Récupérer la date et l'heure du dictionnaire actuel
                        dt_txt = dictionnaire['dt_txt']
                        print(dt_txt)
                        # Vérifier si la date et l'heure correspondent
                        if date in dt_txt and heure in dt_txt:
                            # Afficher le dictionnaire correspondant
                            print("Dictionnaire correspondant trouvé :")
                            print(dictionnaire)
                            temp_celcius = dictionnaire['main']['temp']
                            temp_celcius = round(temp_celcius, 0)
                            feels_like_celcius = dictionnaire['main']['feels_like']
                            feels_like_celcius = round(feels_like_celcius, 0)
                            humidity = dictionnaire['main']['humidity']
                            wind_speed = dictionnaire['wind']['speed']
                            description = dictionnaire['weather'][0]['description']
                            icon = dictionnaire['weather'][0]['icon']
                            break

            image_url = f"https://openweathermap.org/img/wn/{icon}@2x.png"
            # Afficher l'image dans Streamlit
            st.image(image_url, caption=f"{description}")

            # On cherche les coordonnées et le Pays de la ville
            coord_url = f"http://api.openweathermap.org/geo/1.0/direct?q={CITY}&limit=1&appid={API_KEY}"
            coord_json = requests.get(coord_url).json()
            latitude = coord_json[0]['lat']
            longitude = coord_json[0]['lon']
            country = coord_json[0]['country']

            # On appelle l'API pour avoir la qualité de l'air
            pollution_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={latitude}&lon={longitude}&appid={API_KEY}"
            air_pollution = requests.get(pollution_url).json()
            pm25_value = air_pollution['list'][0]['components']['pm2_5']
            pm25_category = categorize_pm25(pm25_value)

            st.write(f"Qualité de l'air: {pm25_category}")

            if temp_celcius > 15:
                delta_temp = "+chaud"
            else:
                delta_temp = "-frais"

            st.metric(label="Temperature", value=temp_celcius, delta=delta_temp)

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
            print(sunrise)
            print(sunset)
            if sunrise and sunset:
                query = f"température en degré celcius:{temp_celcius},température ressenti:{feels_like_celcius},humidity:{humidity},wind speed:{wind_speed},sunrise:{sunrise},sunset:{sunset},description:{description}"
            else:
                query = f"température en degré celcius:{temp_celcius},température ressenti:{feels_like_celcius},humidity:{humidity},wind speed:{wind_speed},description:{description}"

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
