# Configurations supplémentaires

## Gestion des intervenants

**guv** offre également une gestion des intervenants dans les UV/UE.
Cela permet par exemple de générer des fichiers iCal par intervenant
sur tout un semestre, de générer un fichier récapitulatif des UTP
effectuées.

Pour cela, il faut remplir les fichiers `planning_hebdomadaire.xlsx`
situés dans le sous-dossier `documents` de chaque UV/UE. Ces
fichiers sont automatiquement générés s'ils n'existent pas lorsqu'on
exécute simplement **guv** sans argument dans le dossier de semestre.

Les fichiers `planning_hebdomadaire.xlsx` contiennent toutes les
séances de l'UV/UE concernée d'après le fichier pdf renseigné dans
`CRENEAU_UV`.

Si l'UV/UE n'est pas répertoriée dans le fichier pdf, il s'agit très
probablement d'une UE. Un fichier Excel vide avec en-tête est alors
créé et il faut renseigner manuellement les différents créneaux.

Dès lors, on peut utiliser les tâches suivantes :

- {class}`guv.tasks.instructors.XlsRemplacements`
- {class}`guv.tasks.calendar.CalInst`
- {class}`guv.tasks.ical.IcalInst`
- {class}`guv.tasks.moodle.HtmlInst`
