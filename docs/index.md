# `guv`

**`guv`** est un outil en ligne de commande destiné à simplifier la gestion de
plusieurs **UV** (Unité de Valeur) ou **UE** (Unité d'Enseignement). Il permet
de centraliser les informations relatives à chaque UV/UE et d'y incorporer
facilement de nouvelles données via des fichiers de configuration. Avec `guv`,
vous pouvez générer des fichiers iCal, des trombinoscopes, des feuilles de
présence, des feuilles de notes, et bien plus encore !

---

## ✨ Fonctionnalités

- Centralisation des informations pour les UVs/UEs
- Génération automatique de fichiers iCal
- Création de trombinoscopes visuels
- Fichier Excel de notes pour le jury d'UV/UE
- Personnalisation facile avec des fichiers de configuration

---

## 🚀 Installation

Installez `guv` directement via `pip` :

```shell
pip install guv --index-url https://gitlab.utc.fr/api/v4/projects/9255/packages/pypi/simple
```

---

## 🏃 Guide rapide

Suivez les étapes ci-dessous pour commencer à utiliser `guv` :

1. **Créer la structure de semestre** :

    ```shell
    guv createsemester A2024 --uv SY02 SY09
    cd A2024
    ```

    Les variables sont initialisées dans le fichier `config.py` du semestre.

2. **Configurer le fichier des créneaux officiels du semestre** :

    Ouvrez le fichier `config.py` et ajoutez le chemin relatif du fichier PDF de
    la liste officielle des créneaux du semestre, disponible
    [ici](https://webapplis.utc.fr/ent/services/services.jsf?sid=578) :

    ```python
    CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"
    ```

3. **Générer les calendriers** :

   Exécutez l'une des commandes suivantes dans le dossier `A2024` :

   - Pour générer les calendriers hebdomadaires des UVs :

     ```shell
     guv cal_uv
     ```

   - Pour créer des fichiers iCal pour tous les créneaux :

     ```shell
     guv ical_uv
     ```

```{toctree}
:hidden:
self
```

```{toctree}
:hidden:
:caption: Tutorial
tutorial/tree.md
tutorial/semester_config.md
tutorial/uv_config.md
tutorial/inst.md
tutorial/docs.md
```

```{toctree}
:hidden:
:caption: Tâches
tasks/attendance.md
tasks/ical.md
tasks/trombi.md
tasks/calendar.md
tasks/students.md
tasks/grades.md
tasks/instructors.md
tasks/moodle.md
tasks/misc.md
```

```{toctree}
:hidden:
:caption: Divers

misc/variables.md
misc/completion.md
misc/path.md
misc/create_task.md
```
