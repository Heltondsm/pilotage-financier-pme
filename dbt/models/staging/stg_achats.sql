-- Les factures des fournisseurs (montant TTC) et leur paiement
select
    a.numero_achat,
    cast(a.date_achat as date)                              as date_achat,
    a.code_fournisseur,
    a.montant_ht,
    round(a.montant_ht * (1 + prm.taux_tva), 2)             as montant_ttc,
    cast(a.date_paiement as date)                           as date_paiement
from {{ source('brut', 'achats') }} a
cross join {{ ref('parametres') }} prm
