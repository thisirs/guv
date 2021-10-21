Installation
============

Il faut d'abord télécharger l'archive du projet sur Gitlab et
l'installer avec ``pip`` :

.. code:: bash

   pip install .

On peut également cloner le projet si ``git`` est installé comme suit :

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

   guv createsemester A2021 --uv SY02 SY09
   cd A2021

Les variables ont été renseignées dans le fichier ``config.py`` du
semestre.

On renseigne ensuite dans le fichier ``config.py`` du dossier
``A2021``, le chemin relatif du fichier pdf de la liste officielle des
créneaux du semestre. Si on le place dans le sous-dossier
``documents``, on écrit alors :

.. code:: python

   CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"

On peut maintenant exécuter ``guv cal_uv`` dans le dossier ``A2021``
pour générer les calendriers hebdomadaires des UV.
