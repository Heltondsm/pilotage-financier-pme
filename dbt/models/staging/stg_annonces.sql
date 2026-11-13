-- Les vraies annonces du Bodacc sur les clients et fournisseurs : une seule ligne par annonce,
-- rattachée au CODE du client ou du fournisseur (le SIREN ne sort jamais de cette vue)
with source as (
    select
        *,
        row_number() over (partition by id_annonce order by date_collecte desc) as copie
    from {{ source('brut', 'annonces') }}
)

select
    s.id_annonce,
    c.code,
    {{ en_date('s.date_parution') }}                                 as date_parution,
    coalesce({{ en_date('s.jugement_date') }}, {{ en_date('s.date_parution') }}) as date_evenement,
    case
        when s.famille = 'radiation' then 'radiation'
        when s.famille = 'collective' and lower(s.jugement_nature) like '%rétractation%' then 'suivi de procédure'
        when s.famille = 'collective' and lower(s.jugement_nature) like '%liquidation%'
             and (lower(s.jugement_nature) like '%ouverture%' or lower(s.jugement_nature) like '%conversion%'
                  or lower(s.jugement_nature) like '%prononçant%') then 'liquidation judiciaire'
        when s.famille = 'collective' and lower(s.jugement_nature) like '%ouverture%redressement%' then 'redressement judiciaire'
        when s.famille = 'collective' and lower(s.jugement_nature) like '%ouverture%sauvegarde%' then 'sauvegarde'
        when s.famille = 'collective' then 'suivi de procédure'
        else 'autre annonce'
    end                                                              as evenement
from source s
join {{ source('brut', 'correspondance') }} c on c.siren = s.siren
where s.copie = 1
