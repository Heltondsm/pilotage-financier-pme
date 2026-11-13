-- Le pont entre les deux étages : Distrimat (12 derniers mois, données de test) face aux vrais
-- grossistes en matériaux de sa taille (dernier bilan publié). Une ligne par indicateur.
with ref_date as (select date_reference from {{ ref('int_date_reference') }}),

ventes as (   -- les ventes et la marge brute des 12 derniers mois, et des 12 mois d'avant
    select
        sum(case when f.date_facture > {{ dbt.dateadd('day', -365, 'r.date_reference') }} then f.montant_ht end)      as ca_12_mois,
        sum(case when f.date_facture > {{ dbt.dateadd('day', -365, 'r.date_reference') }} then f.marge_brute_ht end)  as marge_12_mois,
        sum(case when f.date_facture <= {{ dbt.dateadd('day', -365, 'r.date_reference') }}
                  and f.date_facture > {{ dbt.dateadd('day', -730, 'r.date_reference') }} then f.montant_ht end)      as ca_12_mois_avant
    from {{ ref('stg_factures') }} f cross join ref_date r
),

charges as (
    select sum(c.montant) as charges_12_mois
    from {{ ref('stg_charges') }} c cross join ref_date r
    where c.date_paiement > {{ dbt.dateadd('day', -365, 'r.date_reference') }} and c.date_paiement <= r.date_reference
),

dso as (   -- le DSO moyen des 12 derniers mois (un seul mois varie trop avec les saisons)
    select avg(dso_jours) as dso_jours
    from (select dso_jours from {{ ref('kpi_mensuels') }} order by mois desc limit 12) derniers
),

dpo as (   -- le délai moyen de paiement des fournisseurs, sur les achats payés dans l'année
    select avg({{ jours_entre('a.date_achat', 'a.date_paiement') }}) as dpo_jours
    from {{ ref('stg_achats') }} a cross join ref_date r
    where a.date_paiement > {{ dbt.dateadd('day', -365, 'r.date_reference') }} and a.date_paiement <= r.date_reference
),

distrimat as (
    select 1 as ordre, 'Croissance des ventes' as indicateur, '%' as unite,
           100 * (v.ca_12_mois - v.ca_12_mois_avant) / v.ca_12_mois_avant as valeur, true as plus_haut_mieux
    from ventes v
    union all
    select 2, 'Marge (EBE / ventes)', '%', 100 * (v.marge_12_mois - c.charges_12_mois) / v.ca_12_mois, true
    from ventes v cross join charges c
    union all
    select 3, 'Délai de paiement des clients', 'jours', d.dso_jours, false from dso d
    union all
    select 4, 'Délai de paiement des fournisseurs', 'jours', p.dpo_jours, cast(null as boolean) from dpo p
),

secteur as (   -- les concurrents : même activité (46.73A), même classe de taille
    select
        max(groupe) as groupe, max(nb_concurrents) + 1 as nb_entreprises,
        max(croissance_pct_q1) as q1_1, max(croissance_pct_mediane) as med_1, max(croissance_pct_q3) as q3_1,
        max(marge_ebe_pct_q1) as q1_2, max(marge_ebe_pct_mediane) as med_2, max(marge_ebe_pct_q3) as q3_2,
        max(delai_clients_jours_q1) as q1_3, max(delai_clients_jours_mediane) as med_3, max(delai_clients_jours_q3) as q3_3,
        max(delai_fournisseurs_jours_q1) as q1_4, max(delai_fournisseurs_jours_mediane) as med_4, max(delai_fournisseurs_jours_q3) as q3_4
    from {{ ref('benchmark_entreprises') }}
    where naf = '46.73A' and classe_taille = '3 - 50 à 249 salariés'
),

comparee as (
    select d.*, s.*,
           case d.ordre when 1 then s.med_1 when 2 then s.med_2 when 3 then s.med_3 else s.med_4 end as med,
           case when d.unite = '%' then 0.5 else 2 end as tolerance     -- en dessous, l'écart ne veut rien dire
    from distrimat d cross join secteur s
)

select
    ordre,
    indicateur,
    unite,
    round(valeur, 1)                                                                    as distrimat,
    round(case ordre when 1 then q1_1 when 2 then q1_2 when 3 then q1_3 else q1_4 end, 1)    as q1,
    round(med, 1)                                                                       as mediane,
    round(case ordre when 1 then q3_1 when 2 then q3_2 when 3 then q3_3 else q3_4 end, 1)    as q3,
    case
        when abs(valeur - med) <= tolerance then 'au niveau du secteur'
        when plus_haut_mieux is null then
            case when valeur > med then 'plus lent que le secteur' else 'plus rapide que le secteur' end
        when (plus_haut_mieux and valeur > med) or (not plus_haut_mieux and valeur < med) then 'meilleur que le secteur'
        else 'moins bon que le secteur'
    end                                                                                 as lecture,
    groupe,
    nb_entreprises
from comparee
