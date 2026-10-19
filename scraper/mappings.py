"""Codes used in liste.csv.

Source: Notice des données
https://www.hatvp.fr/wordpress/wp-content/uploads/2017/07/notice-open-data.pdf
"""

# type_mandat
MANDATE_TYPES = {
    "senateur": "Sénateur",
    "depute": "Député",
    "gouvernement": "Membre du gouvernement",
    "europe": "Représentant français au Parlement européen",
    "region": "Membre d'un conseil régional",
    "departement": "Membre d'un conseil départemental ou d'une assemblée territoriale",
    "commune": "Membre d'un conseil municipal",
    "epci": "Membre d'un établissement public de coopération intercommunale",
    "ctsp": "Membre d'une collectivité territoriale à statut particulier",
    "president": "Président de la République",
    "autre": "Autre",
}

# type_document
DOCUMENT_TYPES = {
    "dia": "Déclaration d'intérêts et d'activités",
    "diam": "Déclaration de modification substantielle des intérêts et des activités",
    "di": "Déclaration d'intérêts",
    "dim": "Déclaration de modification substantielle des intérêts",
    "dsp": "Déclaration de situation patrimoniale",
    "dspm": "Déclaration de modification substantielle de situation patrimoniale",
    "appreciation": "Appréciation de la HATVP",
    "dspfm": "Déclaration de situation patrimoniale de fin de fonctions",
}
