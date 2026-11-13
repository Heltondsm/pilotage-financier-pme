-- Les clients touchés par une procédure grave au Bodacc (vraies annonces) : la plus grave, une ligne par client
select code as code_client, evenement as procedure_bodacc, date_evenement as date_procedure
from (
    select
        code, evenement, date_evenement,
        row_number() over (
            partition by code
            order by case evenement when 'liquidation judiciaire' then 1 when 'radiation' then 1
                                    when 'redressement judiciaire' then 2 else 3 end,
                     date_evenement desc
        ) as rang
    from {{ ref('stg_annonces') }}
    where evenement in ('liquidation judiciaire', 'redressement judiciaire', 'sauvegarde', 'radiation')
      and code like 'C%'                                   -- les clients (les fournisseurs commencent par F)
) classees
where rang = 1
