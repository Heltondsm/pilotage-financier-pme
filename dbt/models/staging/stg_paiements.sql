-- Les paiements des clients, sans ceux qui ne correspondent à aucune facture (voir qualite_rejets)
select
    numero_paiement,
    numero_facture,
    cast(date_paiement as date)                             as date_paiement,
    montant_ttc
from {{ source('brut', 'paiements') }}
where numero_facture in (select numero_facture from {{ ref('stg_factures') }})
