-- Question 1, le détail : chaque mois et chaque famille de produits, les ventes face au budget
with ventes as (
    select cast({{ dbt.date_trunc('month', 'date_facture') }} as date) as mois, famille,
           sum(montant_ht) as ca_ht, sum(marge_brute_ht) as marge_brute_ht
    from {{ ref('stg_factures_familles') }}
    -- seulement les mois terminés : le mois en cours, incomplet, fausserait « le dernier mois »
    where cast({{ dbt.date_trunc('month', 'date_facture') }} as date) < cast({{ dbt.date_trunc('month', 'current_date') }} as date)
    group by 1, 2
)

select
    v.mois,
    v.famille,
    round(v.ca_ht, 2)                                               as ca_ht,
    round(v.marge_brute_ht, 2)                                      as marge_brute_ht,
    round(b.budget_ht, 2)                                           as budget_ht
from ventes v
left join {{ ref('budget') }} b
       on cast(concat(b.mois, '-01') as date) = v.mois and b.famille = v.famille
