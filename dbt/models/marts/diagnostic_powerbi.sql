-- La table que lit la page « Le diagnostic » de Power BI : les entreprises de 10 salariés et plus,
-- leurs indicateurs, ceux de leur secteur, les constats et les recommandations, sur une seule ligne
select
    b.siren, b.nom, b.naf, b.classe_taille, b.exercice, b.groupe, b.nb_concurrents, b.chiffre_affaires,
    b.croissance_pct, b.croissance_pct_q1, b.croissance_pct_mediane, b.croissance_pct_q3,
    b.marge_ebe_pct, b.marge_ebe_pct_q1, b.marge_ebe_pct_mediane, b.marge_ebe_pct_q3,
    b.delai_clients_jours, b.delai_clients_jours_q1, b.delai_clients_jours_mediane, b.delai_clients_jours_q3,
    b.delai_fournisseurs_jours, b.delai_fournisseurs_jours_q1, b.delai_fournisseurs_jours_mediane, b.delai_fournisseurs_jours_q3,
    b.endettement_pct, b.endettement_pct_q1, b.endettement_pct_mediane, b.endettement_pct_q3,
    d.constat_croissance, d.constat_marge, d.constat_clients, d.constat_fournisseurs,
    d.recommandation_1, d.recommandation_2, d.rien_a_corriger
from {{ ref('benchmark_entreprises') }} b
join {{ ref('diagnostic_entreprises') }} d on d.siren = b.siren
where b.classe_taille in ('2 - 10 à 49 salariés', '3 - 50 à 249 salariés', '4 - 250 salariés et plus')
