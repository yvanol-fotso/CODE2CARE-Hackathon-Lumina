 
# Track 1 – Patient Feedback and Reminder System

## Objectif
Développer un système intégré capable de :
- Collecter les retours des patients (textes, étoiles, émojis, voix)
- Analyser les sentiments et thématiques exprimés
- Envoyer des rappels de rendez-vous et médicaments
- Gérer plusieurs langues locales : 🇫🇷 Français, 🇬🇧 Anglais, 🇨🇲 Douala, Bassa, Ewondo
- Fonctionner même en connexion faible (low-bandwidth)

## Technologies envisagées
- Frontend : Next js/ Sveltkit
- Backend : FastApi / Flask
- NLP : spaCy, Transformers, Hugging Face
- Sentiment Analysis :Llama 3 ,  Deepseek, fine-tuned BERT
- Multilingue : Google Translate API, TTS/STT (Coqui, Whisper)

## TODO
- [ ] Design de l’interface (UX adapté au terrain)
- [ ] Collecte et preprocessing des données de feedback
- [ ] Classification des sentiments
- [ ] Envoi intelligent des rappels
- [ ] Intégration multilingue

 