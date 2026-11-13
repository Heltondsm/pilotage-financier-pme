-- L'annuaire allégé : l'activité et la classe de taille de chaque entreprise
select
    siren,
    nom,
    naf,
    substr(naf, 1, 2)                                       as division_naf,      -- ex. « 46 » : le commerce de gros
    tranche_effectif,
    {{ classe_taille('tranche_effectif') }}                 as classe_taille,
    categorie
from {{ source('brut', 'entreprises') }}
where naf is not null
