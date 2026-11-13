-- Question 5 (étape 1) : chaque entreprise face à ses concurrents (même activité, même taille),
-- sur son dernier bilan complet. Données réelles (INPI / BCE et Sirene).
with bilans as (
    select *,
           row_number() over (partition by siren order by date_cloture desc) as rang,
           lead(chiffre_affaires) over (partition by siren order by date_cloture desc) as ca_precedent,
           lead(date_cloture) over (partition by siren order by date_cloture desc)     as cloture_precedente
    from {{ ref('stg_bilans') }}
    where not confidentiel and chiffre_affaires > 0
),

dernier as (
    select
        b.siren, b.exercice, b.chiffre_affaires, b.marge_ebe_pct, b.delai_clients_jours,
        b.delai_fournisseurs_jours, b.endettement_pct,
        -- la croissance n'a de sens que si l'exercice précédent dure environ un an
        case when b.ca_precedent > 0 and {{ jours_entre('b.cloture_precedente', 'b.date_cloture') }} between 300 and 430
             then round(100 * (b.chiffre_affaires - b.ca_precedent) / b.ca_precedent, 1) end as croissance_pct,
        e.nom, e.naf, e.division_naf, e.classe_taille, e.categorie
    from bilans b
    join {{ ref('stg_entreprises') }} e on e.siren = b.siren
    where b.rang = 1 and b.exercice >= 2023
),

tailles_groupes as (
    select naf, classe_taille, count(*) as nb from dernier group by naf, classe_taille
),

groupes as (   -- même activité et même taille ; s'il y a trop peu de concurrents, toute la division d'activité
    select d.*,
           case when t.nb >= {{ var('min_pairs') }} then concat(d.naf, ' · ', d.classe_taille)
                else concat(d.division_naf, ' (division) · ', d.classe_taille) end as groupe
    from dernier d join tailles_groupes t on t.naf = d.naf and t.classe_taille = d.classe_taille
)

select
    siren, nom, naf, classe_taille, categorie, exercice, groupe,
    count(*) over (partition by groupe) - 1                                   as nb_concurrents,
    chiffre_affaires, croissance_pct, marge_ebe_pct, delai_clients_jours, delai_fournisseurs_jours, endettement_pct,
    {% for col in ['croissance_pct', 'marge_ebe_pct', 'delai_clients_jours', 'delai_fournisseurs_jours', 'endettement_pct'] %}
    {{ quantile_groupe(col, 0.5, 'groupe') }}  as {{ col }}_mediane,
    {{ quantile_groupe(col, 0.25, 'groupe') }} as {{ col }}_q1,
    {{ quantile_groupe(col, 0.75, 'groupe') }} as {{ col }}_q3{{ "," if not loop.last }}
    {% endfor %}
from groupes
