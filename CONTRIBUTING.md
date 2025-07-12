 # Guide de contribution - Équipe Lumina

Bienvenue dans le dépôt de l’équipe **Lumina** pour le Hackathon CODE2CARE !  
Nous sommes heureux de collaborer avec vous tous pour créer ensemble des solutions innovantes qui auront un impact réel.


## Organisation du dépôt et branches

Pour faciliter notre travail en équipe, le projet est organisé avec plusieurs branches correspondant aux trois pistes (tracks) du hackathon :

- **track1** : Patient Feedback & Reminder System  
- **track2** : Chatbot LLM pour l’éducation et le support patient  
- **track3** : Suivi et prévision des stocks de sang  

Chacun·e travaille sur la branche liée à sa piste sans gêner les autres. Cela permet de garder le code clair et organisé.  

Vous pouvez aussi créer d’autres branches si besoin (fonctionnalité, correction) et proposer des Pull Requests.


## Comment contribuer ?

1.  **Récupérer le projet** Clonez ce dépôt puis choisissez la branche correspondant à votre travail :  
    ```bash
    git checkout track1
    ```
    (ou track2, track3 selon votre projet)

2.  **Créer votre branche de travail** Pour une nouvelle fonctionnalité ou correction, créez une branche spécifique à partir de la branche de votre track :
    ```bash
    git checkout -b ma-fonctionnalite
    ```

3.  **Faire vos modifications** Commitez régulièrement avec des messages clairs, par exemple :
    ```bash
    git commit -m "Ajout de la gestion des rappels multilingues"
    ```

4.  **Pousser votre branche** ```bash
    git push origin ma-fonctionnalite
    ```

5.  **Proposer une Pull Request (PR)** Sur GitHub, ouvrez une PR vers la branche `trackX` correspondante ou vers `main` si le travail est prêt à être intégré.
    Décrivez bien vos changements et attendez les retours.

