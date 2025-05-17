Envoie de courriel à chaque étudiant.

Le seul argument à fournir est un chemin vers un fichier servant de modèle pour
les courriels. Si le fichier n'existe pas, un modèle par défaut est créé. Le
modèle est au format Jinja2 et les variables de remplacement disponibles pour
chaque étudiant sont les noms de colonnes dans le fichier ``effectif.xlsx``.

Pour permettre l'envoi des courriels, il faut renseigner les variables ``LOGIN``
(login de connexion au serveur SMTP), ``FROM_EMAIL`` l'adresse courriel d'envoi
dans le fichier ``config.py``. Les variables ``SMTP_SERVER`` et ``PORT`` (par
défaut smtps.utc.fr et 587).

{options}

Exemples
--------

.. code:: bash

   guv send_email documents/email_body

avec ``documents/email_body`` qui contient :

.. code:: text

   Subject: Note

   Bonjour {{ Prénom }},

   Vous faites partie du groupe {{ group_projet }}.

   Cordialement,

   guv

