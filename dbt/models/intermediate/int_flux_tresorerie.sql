-- Tous les mouvements de la banque, jour par jour : encaissements des clients, paiements des
-- fournisseurs, charges fixes et TVA reversée à l'État (payée le 20 du mois suivant)
with tva as (
    select
        {{ dbt.date_trunc('month', 'date_facture') }}                       as mois,
        sum(montant_ttc - montant_ht)                                       as tva_collectee
    from {{ ref('stg_factures') }} group by 1
),

tva_deductible as (
    select {{ dbt.date_trunc('month', 'date_achat') }} as mois, sum(montant_ttc - montant_ht) as tva_achats
    from {{ ref('stg_achats') }} group by 1
),

mouvements as (
    select date_paiement as jour, 'encaissement client' as nature, montant_ttc as montant
    from {{ ref('stg_paiements') }}
    union all
    select date_paiement, 'paiement fournisseur', -montant_ttc
    from {{ ref('stg_achats') }} where date_paiement is not null
    union all
    select date_paiement, 'charges fixes', -montant
    from {{ ref('stg_charges') }}
    union all
    select {{ dbt.dateadd('day', 19, dbt.dateadd('month', 1, 't.mois')) }}, 'TVA reversée',
           -(t.tva_collectee - coalesce(d.tva_achats, 0))
    from tva t left join tva_deductible d on d.mois = t.mois
)

select m.jour, m.nature, round(sum(m.montant), 2) as montant
from mouvements m
cross join {{ ref('int_date_reference') }} r
where m.jour <= r.date_reference                                   -- seulement ce qui s'est déjà passé
group by m.jour, m.nature
