-- Le solde de la banque, jour par jour, depuis le début (mouvements réels de la simulation)
with jours as (
    select jour, sum(montant) as mouvement_net,
           sum(case when montant > 0 then montant else 0 end) as entrees,
           sum(case when montant < 0 then -montant else 0 end) as sorties
    from {{ ref('int_flux_tresorerie') }}
    group by jour
)

select
    j.jour,
    round(j.entrees, 2)                                                       as entrees,
    round(j.sorties, 2)                                                       as sorties,
    round(p.tresorerie_initiale + sum(j.mouvement_net) over (order by j.jour), 2) as solde
from jours j
cross join {{ ref('parametres') }} p
