import datetime as dt
import os
import warnings

import json
# On importe les modules nécessaires de LangChain
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFaceHub
from langchain.prompts import PromptTemplate

import matplotlib.pyplot as plt
import pycountry
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

def clean_json2(json_object,date,hour):
    json_object["date"] = json_object["date"].replace('/', '-') # on remplace

    tod_h = hour.strftime('%H')
    new_json = json_object

    if all(value == 'None' for value in json_object.values()):
        return "Need to re-ask"
    
    if json_object["ville"] == 'None':
        new_json["ville"] = "Lyon"

    day_plus_five = date + dt.timedelta(days=5) # check +5 jours

    # Check de l'heure
    if json_object["heure"] != 'None' and json_object["heure"] < tod_h: 
        new_json["heure"] = str(int(tod_h) + 1).zfill(2)
    elif json_object["heure"] == 'None':
        new_json["heure"] = tod_h

    # Check si l'heure est au bon format    
    nouvelle_heure = heure_precedente(new_json["heure"])
    print(nouvelle_heure)
    print(type(nouvelle_heure))
    new_json["heure"] = nouvelle_heure

    # Check de la date
    if json_object["date"] != 'None':
        date_from_json = dt.datetime.strptime(json_object["date"], '%Y-%m-%d').date()
        if (date_from_json > day_plus_five) or (date_from_json < date):
            new_json["date"] = day_plus_five.strftime('%Y-%m-%d')
            new_json["date"] = day_plus_five.strftime('%Y-%m-%d')
    else:
        new_json["date"] = date.strftime('%Y-%m-%d')
    print(new_json)
    print("sortie")
    return new_json


def premier_json(chaine):
    debut_json = chaine.find('{')  # Trouver le début du premier JSON
    fin_json = chaine.find('}', debut_json) + 1  # Trouver la fin du premier JSON
    json_str = chaine[debut_json:fin_json]  # Extraire le JSON
    try:
        premier_json = json.loads(json_str)  # Charger le JSON
        return premier_json
    except json.JSONDecodeError:
        return None

def heure_precedente(heure):
    horaire_liste = [0, 3, 6, 9, 12, 15, 18, 21]

    heure_int = int(heure)
    # Si l'heure donnée est dans la liste, la retourner
    if heure_int in horaire_liste:
        return heure
    
    # Trouver l'heure précédente dans la liste
    heure_precedente = max((h for h in horaire_liste if h < heure_int), default=horaire_liste[-1])

    # Formater l'heure précédente avec un zéro devant si nécessaire
    if heure_precedente < 10:
        return "0" + str(heure_precedente)
    else:
        return heure_precedente

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

def code_pays_vers_nom(code_pays):
    try:
        pays = pycountry.countries.get(alpha_2=code_pays.upper())
        if pays:
            return pays.name
        else:
            return "Pays non trouvé"
    except Exception as e:
        return str(e)


def speak(text, rate, volume):
    engine = pyttsx3.init()
    # rate = engine.getProperty('rate')
    # volume = engine.getProperty('volume')
    # pitch = engine.getProperty('pitch')
    engine.setProperty('rate', rate)  # Vitesse de la parole (mots par minute)
    engine.setProperty('volume', volume)   # Volume de la voix (0.0 à 1.0)
    engine.say(text)
    # Configuration des propriétés de la voix
    # engine.setProperty('pitch', 50)  # Hauteur de la voix
    engine.runAndWait()

weekday = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
tod_date = dt.date.today()
tod_hour = dt.datetime.now()
week_day = weekday[dt.date.today().weekday()]

# Fonction principale
def main():
    st.set_page_config(page_title="Miss Météo", page_icon=":partly_sunny:", layout='centered')

    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        st.write("")
    with col2:
        st.title("Miss Météo SISE")

        ###### Paramètres de la voix ######
        st.header("Faites glissez les sliders pour paramétrer la vitesse et le volume de la voix.")
        rate = st.slider("Vitesse de la voix", 150, 250, 200)
        volume = st.slider("Volume de la voix", 0.0, 2.0, 1.0)

        col4, col5 = st.columns(2)
        with col4:
            on_text = st.toggle('Afficher la réponse de Miss Météo')
        with col5:
            on_graph = st.toggle('Afficher le graphique des prédictions')

        ###### Reconnaissance vocale ######
        st.header("Appuyez sur le bouton pour parler et écouter la réponse")
        recognizer = sr.Recognizer()

        if st.button("🎙️"):
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
                temp1 = f'''[INST] Tu dois extraire la Date et l'Heure approximative indiquée dans la query.
                        Estime la date au besoin.
                        Si tu n'es pas sûr de l'heure ou de la date, mets 'None'.
                        Aujourd'hui, nous sommes le {week_day} {tod_date.strftime('%Y/%m/%d')} à {tod_hour.strftime('%H')} h.
                        Le matin commence à 9 h, l'après-midi commence à 15 h et le soir à 19 h. 
                        Le JSON doit avoir ce format:
                        "date":"%Y/%m/%d",
                        "heure":"HH"

                        ----- 
                        '''
                temp2 = """
                        Voici la query :
                            {query}

                            [/INST]
                        Reponse_:
                        """
                templ_1 = temp1 + temp2
                query = text

                # On instancie notre template de prompt où l'on indique que nos deux variables entrantes sont le contexte (documents) et la requête (question)
                promp_rag = PromptTemplate(input_variables=["query"], template=templ_1)
                chain = LLMChain(prompt=promp_rag, llm=llm,verbose=False)
                response = chain.invoke({"query": query})
                answer = response["text"].split("Reponse_:")[1]
                json_fin = remove_after_last_brace(answer)

                template_2 = """[INST]
                                Voici un Json :
                                {json}
                                Extrait l'information de la VILLE de la QUERY et ajoute le à ce JSON. ("ville":). Si tu ne sait pas, met "None".
                                Renvois le JSON avec ce format : {{"date":, "heure":, "ville":}}.
                                Pas besoin d'explication.
                                ----- 
                                Voici la query :
                                {query}

                                [/INST]
                                Reponse_:
                                """

                # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
                promp_rag_2 = PromptTemplate(input_variables=["query"], template=template_2)
                chain_2 = LLMChain(prompt=promp_rag_2, llm=llm,verbose=False)
                response_2 = chain_2.invoke({"query": query,"json":json_fin})
                answer_2 = response_2["text"].split("Reponse_:")[1]
                data = premier_json(answer_2)

                print(data)

                # On clean le JSON
                data = clean_json2(data,tod_date,tod_hour)
                print(data)

                # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
                # data = json.loads(answer)
                lieu = data["ville"]
                date = data["date"]
                heure = data["heure"]
                heure = str(heure)

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
                    print(date)
                    print(type(date))
                    print(heure)
                    print(type(heure))
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
                                sunrise = ""
                                sunset = ""
                                break
                    else:
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
                                sunrise = ""
                                sunset = ""
                                break

                st.header(f"Météo pour {lieu} le {date} à {heure}h00")

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

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("🌡️ Température")
                    st.write(f"{temp_celcius}°C")

                    st.subheader("❄️ Ressenti")
                    st.write(f"{feels_like_celcius}°C")

                    st.subheader("💧 Humidité")
                    st.write(f"{humidity}%")

                    if sunrise != "":
                        st.subheader("🌅 Levé du soleil")
                        st.write(sunrise)

                with col2:
                    st.subheader("💨 Vitesse du vent")
                    st.write(f"{wind_speed} m/s")

                    st.subheader("🍃 Qualité de l'air")
                    st.write(pm25_category)

                    st.subheader("🌍 Pays")
                    country = code_pays_vers_nom(country)
                    st.write(country)
                    
                    if sunset != "":
                        st.subheader("🌇 Couché du soleil")
                        st.write(sunset)

                if on_graph:
                    st.write("Graphique des prévisions sur 5 jours")
                    
                    dates = []
                    temperatures = []
                    for forecast in response['list']:
                        dates.append(forecast['dt_txt'])
                        temperatures.append(forecast['main']['temp'])
                    plt.plot(dates, temperatures, marker='o', linestyle='-')
                    plt.title('Température sur 5 jours')
                    plt.xlabel('Date')
                    plt.ylabel('Température (°C)')
                    plt.xticks(dates[::2], rotation=45)
                    plt.grid(True)
                    plt.tight_layout()
                    # Affichage du graphique
                    st.pyplot(plt)

                ###### Nouveau prompt pour le retriever ######
                st.write("Préparation de Miss Météo...")
                template = """[INST]
            Présente moi les informations météorologiques comme si tu était un présentateur météo.
            ----- 

            Voici la requête :
                {query}

                [/INST]
            JSON:
    """
                if sunrise != "":
                    query = f"température en degré celcius:{temp_celcius},température ressenti:{feels_like_celcius},humidity:{humidity},wind speed:{wind_speed},sunrise:{sunrise},sunset:{sunset},description:{description}"
                else:
                    query = f"température en degré celcius:{temp_celcius},température ressenti:{feels_like_celcius},humidity:{humidity},wind speed:{wind_speed},description:{description}"

                # On instancie notre template de prompt où l'on indique que nos deux variables entrantes sont le contexte (documents) et la requête (question)
                promp_rag = PromptTemplate(input_variables=["query"], template=template)
                chain = LLMChain(prompt=promp_rag, llm=llm,verbose=False)
                response = chain.invoke({"query": query})
                answer = response["text"].split("JSON:")[1]
                print(answer)

                # On le place dans une variable pour indiquer que ce sera le prompt de notre retriever
                reponse_a_lire = answer.split("}")[-1]
                reponse_a_lire = reponse_a_lire.replace("\n", "")
                reponse_a_lire = reponse_a_lire.strip()

                ###### Réponse vocale ######
                # Toggle coché ou non
                if on_text:
                    st.write("Traitement audio en cours...")
                    st.write(reponse_a_lire)

                speak(reponse_a_lire, rate, volume)
                st.write("Réponse audio générée avec succès")
            except Exception as e:
                st.write("Erreur : " + str(e))

    with col3:
        st.write("")

if __name__ == "__main__":
    main()
