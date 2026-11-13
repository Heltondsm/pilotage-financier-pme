-- Question 5 (étape 2) : le diagnostic d'une page de chaque entreprise.
-- Chaque constat est écrit en X-Y-Z (l'impact, le chiffre, la comparaison) ; on garde au plus
-- 2 recommandations, par ordre d'importance ; s'il n'y a rien à corriger, on le dit et on recommande
-- de protéger l'avance.
with b as (select * from {{ ref('benchmark_entreprises') }} where nb_concurrents >= 10),

recommandations as (
    -- 1. les clients paient bien plus lentement que dans le secteur : de la trésorerie bloquée
    select siren, 1 as priorite,
           concat('Raccourcir les délais de paiement de vos clients : ',
                  {{ texte_nombre('delai_clients_jours - delai_clients_jours_mediane') }}, ' jours de plus que vos concurrents, soit environ ',
                  {{ texte_nombre('chiffre_affaires * 1.2 * (delai_clients_jours - delai_clients_jours_mediane) / 365 / 1000') }},
                  ' k€ de trésorerie à récupérer.') as texte
    from b where delai_clients_jours > delai_clients_jours_mediane + 15
    union all
    -- 2. la marge est nettement sous celle du secteur
    select siren, 2,
           concat('Travailler la marge : ', {{ texte_nombre('marge_ebe_pct_mediane - marge_ebe_pct', 1) }},
                  ' points sous vos concurrents ; au niveau du secteur, ce serait environ ',
                  {{ texte_nombre('chiffre_affaires * (marge_ebe_pct_mediane - marge_ebe_pct) / 100 / 1000') }},
                  ' k€ de résultat d’exploitation en plus par an.')
    from b where marge_ebe_pct < marge_ebe_pct_mediane - 3
    union all
    -- 3. les ventes reculent alors que le secteur résiste
    select siren, 3,
           concat('Relancer les ventes : ', {{ texte_nombre('croissance_pct', 1) }}, ' % en un an, contre ',
                  {{ texte_nombre('croissance_pct_mediane', 1) }}, ' % pour vos concurrents.')
    from b where croissance_pct < 0 and croissance_pct < croissance_pct_q1
    union all
    -- 4. l'endettement est dans le quart le plus élevé du secteur
    select siren, 4,
           concat('Surveiller l’endettement : ', {{ texte_nombre('endettement_pct') }}, ' %, contre ',
                  {{ texte_nombre('endettement_pct_mediane') }}, ' % pour vos concurrents.')
    from b where endettement_pct > endettement_pct_q3 and endettement_pct > 100
    union all
    -- 5. l'entreprise paie ses fournisseurs bien plus vite que le secteur : un levier de trésorerie
    select siren, 5,
           concat('Négocier des délais fournisseurs plus proches du secteur : vous payez ',
                  {{ texte_nombre('delai_fournisseurs_jours_mediane - delai_fournisseurs_jours') }}, ' jours plus vite que vos concurrents.')
    from b where delai_fournisseurs_jours < delai_fournisseurs_jours_mediane - 15
),

classees as (
    select siren, texte, row_number() over (partition by siren order by priorite) as rang from recommandations
),

deux_premieres as (
    select siren,
           max(case when rang = 1 then texte end) as recommandation_1,
           max(case when rang = 2 then texte end) as recommandation_2
    from classees group by siren
)

select
    b.siren, b.nom, b.naf, b.classe_taille, b.exercice, b.groupe, b.nb_concurrents,
    -- les constats, en X-Y-Z
    case when b.marge_ebe_pct is not null then concat('Marge (EBE / ventes) : ', {{ texte_nombre('b.marge_ebe_pct', 1) }},
         ' %, contre ', {{ texte_nombre('b.marge_ebe_pct_mediane', 1) }}, ' % pour les ',
         cast(b.nb_concurrents as {{ dbt.type_string() }}), ' entreprises comparables.') end      as constat_marge,
    case when b.delai_clients_jours is not null then concat('Vos clients paient en ', {{ texte_nombre('b.delai_clients_jours') }},
         ' jours, contre ', {{ texte_nombre('b.delai_clients_jours_mediane') }}, ' jours chez vos concurrents.') end as constat_clients,
    case when b.delai_fournisseurs_jours is not null then concat('Vous payez vos fournisseurs en ', {{ texte_nombre('b.delai_fournisseurs_jours') }},
         ' jours, contre ', {{ texte_nombre('b.delai_fournisseurs_jours_mediane') }}, ' jours.') end as constat_fournisseurs,
    case when b.croissance_pct is not null then concat('Ventes : ', {{ texte_nombre('b.croissance_pct', 1) }},
         ' % en un an, contre ', {{ texte_nombre('b.croissance_pct_mediane', 1) }}, ' % pour le secteur.') end as constat_croissance,
    coalesce(r.recommandation_1,
             'Protéger l’avance : vos indicateurs sont au niveau du secteur ou meilleurs. Suivre chaque mois la marge et les délais clients avec vos données internes, pour voir un écart avant qu’il ne coûte.')
                                                                                                    as recommandation_1,
    r.recommandation_2,
    r.recommandation_1 is null                                                                      as rien_a_corriger
from b
left join deux_premieres r on r.siren = b.siren
