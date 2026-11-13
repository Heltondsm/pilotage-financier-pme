-- Chaque facture avec son paiement : payée, à échoir, en retard ou douteuse, et de combien de jours
with paye as (   -- seulement les paiements déjà reçus à la date de référence
    select p.numero_facture, max(p.date_paiement) as date_paiement, sum(p.montant_ttc) as paye_ttc
    from {{ ref('stg_paiements') }} p
    cross join {{ ref('int_date_reference') }} r
    where p.date_paiement <= r.date_reference
    group by p.numero_facture
)

select
    f.numero_facture,
    f.date_facture,
    f.date_echeance,
    f.code_client,
    f.montant_ht,
    f.marge_brute_ht,
    f.montant_ttc,
    p.date_paiement,
    round(f.montant_ttc - coalesce(p.paye_ttc, 0), 2)                        as reste_du_ttc,
    case
        when p.date_paiement is not null then 'payée'
        -- impayée et client en procédure, ou plus d'un an de retard : le comptable la provisionne
        when cp.code_client is not null or {{ jours_entre('f.date_echeance', 'r.date_reference') }} > 365 then 'douteuse'
        when f.date_echeance >= r.date_reference then 'à échoir'
        else 'en retard'
    end                                                                      as statut,
    {{ jours_entre('f.date_facture', 'p.date_paiement') }}                   as delai_paiement_jours,
    case
        when p.date_paiement is not null then greatest(0, {{ jours_entre('f.date_echeance', 'p.date_paiement') }})
        else greatest(0, {{ jours_entre('f.date_echeance', 'r.date_reference') }})
    end                                                                      as jours_retard
from {{ ref('stg_factures') }} f
cross join {{ ref('int_date_reference') }} r
left join paye p on p.numero_facture = f.numero_facture
left join {{ ref('int_clients_procedure') }} cp on cp.code_client = f.code_client
where f.date_facture <= r.date_reference
