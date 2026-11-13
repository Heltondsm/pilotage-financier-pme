-- Les vrais bilans : un par entreprise et par exercice, sans date impossible ;
-- les comptes de résultat confidentiels (CA et EBE à 0) et les ratios aberrants sont vidés
with source as (
    select
        *,
        row_number() over (
            partition by siren, date_cloture_exercice
            order by case type_bilan when 'C' then 1 when 'S' then 2 else 3 end
        ) as copie
    from {{ source('brut', 'bilans') }}
),

typees as (
    select
        siren,
        cast(date_cloture_exercice as date)                 as date_cloture,
        type_bilan,
        chiffre_d_affaires = 0 and ebe = 0                  as confidentiel,
        chiffre_d_affaires,
        ebe,
        resultat_net,
        marge_ebe,
        taux_d_endettement,
        ratio_de_liquidite,
        credit_clients_jours,
        credit_fournisseurs_jours
    from source
    where copie = 1
      and cast(date_cloture_exercice as date) <= {{ aujourd_hui() }}    -- un bilan daté dans le futur est une erreur
)

select
    siren,
    date_cloture,
    extract(year from date_cloture)                         as exercice,
    confidentiel,
    case when not confidentiel then chiffre_d_affaires end  as chiffre_affaires,
    case when not confidentiel then ebe end                 as ebe,
    resultat_net,
    case when not confidentiel and marge_ebe between -100 and 100 then marge_ebe end      as marge_ebe_pct,
    case when taux_d_endettement between -1000 and 1000 then taux_d_endettement end      as endettement_pct,
    case when ratio_de_liquidite between 0 and 2000 then ratio_de_liquidite end           as liquidite_pct,
    case when credit_clients_jours between 0 and 365 then credit_clients_jours end        as delai_clients_jours,
    case when credit_fournisseurs_jours between 0 and 365 then credit_fournisseurs_jours end as delai_fournisseurs_jours
from typees
