Installation
============

**guv** est installable directement via ``pip`` :

.. code:: bash

   pip install guv --extra-index-url https://<identifiant>:<mot_de_passe>@gitlab.utc.fr/api/v4/projects/9255/packages/pypi/simple

Il faut remplacer ``<identifiant>`` par votre identifiant ENT et
``<mot_de_passe>`` par le mot de passe correspondant.

On peut également cloner le projet avec ``git`` et ensuite l'installer
comme suit :

.. code:: bash

   git clone git@gitlab.utc.fr:syrousse/guv.git
   cd guv
   pip install .

Un fichier de complétion de commandes est également disponible (voir
:ref:`fichier-de-complétion`).

Exemple rapide
==============

On commence par créer l'arborescence requise (voir
:ref:`création-de-larborescence` pour plus de détails) :

.. code:: bash

   guv createsemester P2022 --uv SY02 SY09
   cd P2022

Les variables ont été renseignées dans le fichier ``config.py`` du
semestre.

On renseigne ensuite dans le fichier `config.py` du semestre, le
chemin relatif du fichier pdf de la liste officielle des créneaux du
semestre disponible `ici
<https://webapplis.utc.fr/ent/services/services.jsf?sid=578>`__. Si on
le place dans le sous-dossier ``documents``, on écrit :

.. code:: python

   CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"

On peut maintenant exécuter ``guv cal_uv`` dans le dossier ``P2022``
pour générer les calendriers hebdomadaires des UV ou bien ``guv
ical_uv`` pour générer des fichiers iCal de tous les créneaux.
