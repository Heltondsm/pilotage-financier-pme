-- Question 2 : qui nous doit de l'argent, et depuis combien de temps (la « balance âgée »).
-- Les clients sont désignés par leur code : leur vrai nom n'apparaît jamais (données de test).
with ouvertes as (
    select * from {{ ref('int_factures_statut') }} where statut != 'payée'
)

select
    o.code_client,
    c.activite,
    m.metier,
    c.departement,
    count(*)                                                                 as nb_factures_ouvertes,
    round(sum(o.reste_du_ttc), 2)                                            as encours_ttc,
    round(sum(case when o.statut = 'à échoir' then o.reste_du_ttc else 0 end), 2)                         as non_echu,
    round(sum(case when o.statut = 'en retard' and o.jours_retard <= 30 then o.reste_du_ttc else 0 end), 2) as retard_1_30,
    round(sum(case when o.statut = 'en retard' and o.jours_retard between 31 and 60 then o.reste_du_ttc else 0 end), 2) as retard_31_60,
    round(sum(case when o.statut = 'en retard' and o.jours_retard between 61 and 90 then o.reste_du_ttc else 0 end), 2) as retard_61_90,
    round(sum(case when o.statut = 'en retard' and o.jours_retard > 90 then o.reste_du_ttc else 0 end), 2)  as retard_plus_90,
    round(sum(case when o.statut = 'douteuse' then o.reste_du_ttc else 0 end), 2)                         as douteux,
    max(case when o.statut = 'en retard' then o.jours_retard end)                                          as retard_max_jours,
    b.procedure_bodacc,
    b.date_procedure
from ouvertes o
join {{ ref('clients') }} c on c.code_client = o.code_client
left join {{ ref('naf_metiers') }} m on m.code_naf = c.activite
left join {{ ref('int_clients_procedure') }} b on b.code_client = o.code_client
group by o.code_client, c.activite, m.metier, c.departement, b.procedure_bodacc, b.date_procedure
