Changement des chemins par défaut
---------------------------------

Beaucoup de tâches écrivent des fichiers avec un nom prédéfini dans un
dossier prédéfini. Il est possible de changer ces valeurs par défaut en
utilisant les attributs de classe ``target_name`` et ``target_dir`` de
la tâche correspondante. Par exemple, la tâche ``XlsStudentDataMerge``
est responsable de la création du fichier ``effectifs.xlsx`` dans le
dossier de l'UV.

Pour changer cela, on peut écrire le code suivant dans le fichier
``config.py`` de l'UV :

.. code:: python

   from guv.tasks import XlsStudentDataMerge
   XlsStudentDataMerge.target_name = "info.xlsx"
   XlsStudentDataMerge.target_dir = "documents"

L'effectif sera alors écrit dans le dossier ``documents`` avec le nom
``info.xlsx``.

Création d'une tâche
--------------------

Il est possible de créer ses propres tâches assez facilement. La
variable ``TASKS`` dans les fichiers de configuration est prévue à cet
effet. Il s'agit d'une liste de chemins vers des fichiers Python
définissant des tâches.

On peut distinguer deux types de tâches différentes qui doivent hériter
de deux classes différentes :

-  les tâches non spécifiques à une UV ou un groupe d'UV qui doivent
   hériter de la classe ``TaskBase``. On trouve par exemple :

   -  les tâches "par intervenants": calendrier hebdomadaire
   -  la tâche de création de tous les créneaux de Cours/TP/TD à l'UTC

-  les tâches spécifiques à une UV qui doivent hériter de la classe
   ``UVTask``. Ce sont les plus courantes et les plus utilisées, on
   trouve par exemple :

   -  le trombinoscope de l'effectif de l'UV
   -  les feuilles de présence concernant les TD d'une UV

   Dans les deux cas, deux méthodes doivent ensuite être implémentées :

   -  la méthode ``setup`` qui doit définir les attributs ``target`` et
      ``file_dep`` qui définissent la cible à créer ainsi que les
      dépendances utilisées pour créer cette cible.
   -  la méthode ``run`` qui effectue la tâche proprement dite en créant
      ``target`` avec les fichiers ``file_dep``.

Tâche non spécifique à une UV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pour créer une tâche non spécifique à une UV, il faut hériter de la
classe ``TaskBase``. Les attributs de classe utiles sont :

-  ``target_dir``: le dossier relatif au semestre où le fichier cible
   sera placé.

-  ``target_name``: le nom de la cible créée

-  ``always_make``: la ou les cibles doivent doit être reconstruites
   même si les dépendances n'ont pas changé

   .. code:: python

      from guv.tasks.base import TaskBase

      class MaTache(TaskBase):
          def setup(self):
              super().setup()
              self.target = "result"
              self.file_dep = ["dependance1", "dependance2"]

          def run(self):
              print("Run")

Tâche spécifique à une UV
~~~~~~~~~~~~~~~~~~~~~~~~~

Les tâches spécifiques sont les plus courantes. Pour les créer, il faut
hériter de la classe ``UVTask``. Les attributs de classe utiles sont :

-  ``unique_uv``: la tâche ne peut être exécutée que pour une seule UV à
   la fois

-  ``target_dir``: le dossier relatif à l'UV où les fichiers utiles
   seront placés

-  ``target_name``: le nom du fichier créé

-  ``always_make``: la ou les cibles doivent doit être reconstruites
   même si les dépendances n'ont pas changé

   Comme il s'agit d'une tâche spécifique à une UV, les attributs ``uv``
   et ``planning`` sont disponibles depuis les méthodes ``setup`` et
   ``run``.

   Par exemple :

   .. code:: python

      from guv.tasks.base import UVTask

      class MaTache(UVTask):
          def setup(self):
              super().setup()
              print(f"Création de la tâche {self.name} pour l'UV {self.uv}")
              self.target = "file_result"
              self.file_dep = ["file1", "file2"]

          def run(self):
              print(f"Création de la cible {self.target}")

Autres classes
~~~~~~~~~~~~~~

La classe ``CliArgsMixin`` permet de paramétrer et de rentre
disponible pour les méthodes ``setup`` et ``run`` les arguments
fournis en ligne de commande. Il n'y a pas de méthode à implémenter,
juste une variable de classe ``cli_args`` à spécifier. La variable
``cli_args`` est un tuple contenant les arguments spécifiés avec la
fonction ``argument``.

.. code:: python

   from guv.utils import argument

   class MaTache(CliArgsMixin, UVTask):
       cli_args = (
           argument(
               "-a",
               "--aa",
           ),
       )

       def setup(self):
           super().setup()
           ...
           self.parse_args())
           ...

       def run(self):
           pass

Les spécifications à l'intérieur de la fonction ``argument`` sont les
mêmes que pour ``argparse``.

.. _fichier-de-complétion:

Fichier de complétion
---------------------

Des fichiers de complétion pour ``zsh`` et ``bash`` sont disponibles
dans le sous-dossier ``data``. Pour un système type Unix et le shell
``zsh``, on peut utiliser les commandes suivantes :

.. code:: bash

   mkdir -p ~/.zsh/completions
   cp $(python -c "import guv; print(guv.__path__[0])")/data/_guv_zsh ~/.zsh/completions/_guv

Si des tâches supplémentaires ont été ajoutées avec la variable
``TASKS``, il est possible de mettre à jour les fichiers de complétion.
Il faut d'abord installer la bibliothèque ``shtab`` et exécuter la
commande suivante dans le dossier du semestre.

.. code:: bash

   shtab --shell=zsh guv.runner.get_parser_shtab > ~/.zsh/completions/_guv
