-- Question 1 : chaque mois, les ventes et la marge face au budget et à l'an dernier, et le délai
-- moyen de paiement des clients (DSO)
with ventes as (
    select
        cast({{ dbt.date_trunc('month', 'date_facture') }} as date)            as mois,
        sum(montant_ht)                                                     as ca_ht,
        sum(marge_brute_ht)                                                 as marge_brute_ht,
        sum(montant_ttc)                                                    as ca_ttc,
        count(*)                                                            as nb_factures
    from {{ ref('stg_factures') }}
    -- seulement les mois terminés : le mois en cours, incomplet, fausserait « le dernier mois »
    where cast({{ dbt.date_trunc('month', 'date_facture') }} as date) < cast({{ dbt.date_trunc('month', 'current_date') }} as date)
    group by 1
),

budget as (
    select cast(concat(mois, '-01') as date) as mois, sum(budget_ht) as budget_ht
    from {{ ref('budget') }}
    group by 1
),

fin_de_mois as (
    select mois, {{ dbt.last_day('mois', 'month') }} as dernier_jour from ventes
),

hors_procedure as (   -- les factures des clients qui ne sont pas en procédure au Bodacc
    select f.*
    from {{ ref('int_factures_statut') }} f
    left join {{ ref('int_clients_procedure') }} cp on cp.code_client = f.code_client
    where cp.code_client is null
),

encours as (   -- ce que les clients doivent encore le dernier jour du mois, hors créances douteuses
    select m.mois, sum(f.montant_ttc) as encours_ttc
    from fin_de_mois m
    join hors_procedure f
      on f.date_facture <= m.dernier_jour
     and (f.date_paiement is null or f.date_paiement > m.dernier_jour)
     and {{ jours_entre('f.date_echeance', 'm.dernier_jour') }} <= 365                 -- pas plus d'un an de retard
    group by m.mois
)

select
    v.mois,
    round(v.ca_ht, 2)                                                       as ca_ht,
    round(v.marge_brute_ht, 2)                                              as marge_brute_ht,
    round(100 * v.marge_brute_ht / v.ca_ht, 1)                              as taux_marge_pct,
    round(b.budget_ht, 2)                                                   as budget_ht,
    round(100 * (v.ca_ht - b.budget_ht) / b.budget_ht, 1)                   as ecart_budget_pct,
    round(n1.ca_ht, 2)                                                      as ca_ht_n_1,
    round(100 * (v.ca_ht - n1.ca_ht) / n1.ca_ht, 1)                         as croissance_pct,
    v.nb_factures,
    round(e.encours_ttc, 2)                                                 as encours_clients_ttc,
    -- DSO : l'encours de fin de mois rapporté aux ventes TTC des 3 derniers mois (91 jours)
    -- (seulement quand 3 mois de ventes existent : sinon le premier mois donnerait un DSO faux)
    case when count(*) over (order by v.mois rows between 2 preceding and current row) = 3
         then round(91 * e.encours_ttc / sum(v.ca_ttc) over (order by v.mois rows between 2 preceding and current row), 0)
    end                                                                     as dso_jours
from ventes v
left join budget b on b.mois = v.mois
left join ventes n1 on n1.mois = cast({{ dbt.dateadd('month', -12, 'v.mois') }} as date)   -- BigQuery renvoie une date avec heure
left join encours e on e.mois = v.mois
