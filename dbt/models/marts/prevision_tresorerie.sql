-- Question 3 : combien d'argent aurons-nous en banque chaque jour des 90 prochains jours ?
-- La méthode, la même pour les clients et pour les fournisseurs : une facture encore ouverte à l'âge de
-- N jours sera payée comme l'ont été, sur les 12 derniers mois, les factures encore ouvertes à N jours.
-- Une facture déjà très en retard hérite donc d'un paiement lointain, ou d'aucun paiement dans les 90 jours.
-- Entrées : les factures émises + les ventes à venir (budget, sinon même mois l'an dernier + 5 %).
-- Sorties : les factures fournisseurs + les achats liés aux ventes à venir, les charges fixes, la TVA.
with ref_date as (
    select date_reference,
           cast({{ dbt.dateadd('day', 1, 'date_reference') }} as date)                      as premier_jour,
           cast({{ dbt.dateadd('day', var('jours_prevision'), 'date_reference') }} as date) as dernier_jour
    from {{ ref('int_date_reference') }}
),

calendrier as (   -- les 90 prochains jours
    select cast(jour as date) as jour from ref_date r, {{ suite_de_jours('r.premier_jour', 'r.dernier_jour') }}
),

-- ---------------------------------------------------------------- 1) les calendriers de paiement observés
profil_clients as (   -- sur 12 mois : combien d'euros ont été payés N jours après la facture
    select f.delai_paiement_jours as delai, sum(f.montant_ttc) as montant
    from {{ ref('int_factures_statut') }} f cross join ref_date r
    where f.statut = 'payée' and f.date_paiement > {{ dbt.dateadd('day', -365, 'r.date_reference') }}
    group by 1
),

profil_fournisseurs as (
    select {{ jours_entre('a.date_achat', 'a.date_paiement') }} as delai, sum(a.montant_ttc) as montant
    from {{ ref('stg_achats') }} a cross join ref_date r
    where a.date_paiement <= r.date_reference
      and a.date_paiement > {{ dbt.dateadd('day', -365, 'r.date_reference') }}
    group by 1
),

-- ---------------------------------------------------------------- 2) ce qui est déjà facturé
ouvertes_clients as (   -- les factures attendues (les créances douteuses ne sont pas attendues)
    select f.date_facture, {{ jours_entre('f.date_facture', 'r.date_reference') }} as age, f.reste_du_ttc as montant
    from {{ ref('int_factures_statut') }} f cross join ref_date r
    where f.statut in ('à échoir', 'en retard')
),

ouvertes_fournisseurs as (
    select a.date_achat as date_facture, {{ jours_entre('a.date_achat', 'r.date_reference') }} as age, a.montant_ttc as montant
    from {{ ref('stg_achats') }} a cross join ref_date r
    where a.date_achat <= r.date_reference
      and (a.date_paiement is null or a.date_paiement > r.date_reference)
),

survie_clients as (   -- pour chaque âge : les euros du passé encore impayés à cet âge (ce qui reste à répartir)
    select o.age, sum(p.montant) as reste
    from (select distinct age from ouvertes_clients) o join profil_clients p on p.delai > o.age
    group by o.age
),

survie_fournisseurs as (
    select o.age, sum(p.montant) as reste
    from (select distinct age from ouvertes_fournisseurs) o join profil_fournisseurs p on p.delai > o.age
    group by o.age
),

entrees_emises as (
    select {{ dbt.dateadd('day', 'p.delai', 'o.date_facture') }} as jour, o.montant * p.montant / s.reste as montant
    from ouvertes_clients o
    join survie_clients s on s.age = o.age
    join profil_clients p on p.delai > o.age
),

sorties_emises as (
    select {{ dbt.dateadd('day', 'p.delai', 'o.date_facture') }} as jour, o.montant * p.montant / s.reste as montant
    from ouvertes_fournisseurs o
    join survie_fournisseurs s on s.age = o.age
    join profil_fournisseurs p on p.delai > o.age
),

-- ---------------------------------------------------------------- 3) l'activité à venir
moyennes as (
    select
        (select sum(f.marge_brute_ht) / sum(f.montant_ht) from {{ ref('stg_factures') }} f cross join ref_date r
          where f.date_facture > {{ dbt.dateadd('day', -365, 'r.date_reference') }}
            and f.date_facture <= r.date_reference)                                                     as taux_marge,
        (select max(taux_tva) from {{ ref('parametres') }})                                             as tva,
        (select sum(montant) from profil_clients)                                                       as total_clients,
        (select sum(montant) from profil_fournisseurs)                                                  as total_fournisseurs
),

ventes_mois as (   -- les ventes HT de chaque mois passé, pour le « même mois l'an dernier »
    select cast({{ dbt.date_trunc('month', 'date_facture') }} as date) as mois, sum(montant_ht) as ca_ht
    from {{ ref('stg_factures') }} f cross join ref_date r
    where f.date_facture <= r.date_reference
    group by 1
),

budget_mois as (
    select cast(concat(mois, '-01') as date) as mois, sum(budget_ht) as budget_ht
    from {{ ref('budget') }} group by 1
),

jours_ouvres as (   -- le nombre de jours de facturation de chaque mois touché par la prévision
    select cast({{ dbt.date_trunc('month', 'jour') }} as date) as mois, count(*) as nb
    from ref_date r,
         {{ suite_de_jours(dbt.date_trunc('month', 'r.premier_jour'), dbt.last_day('r.dernier_jour', 'month')) }}
    where {{ est_jour_ouvre('jour') }}
    group by 1
),

ventes_a_venir as (   -- chaque jour ouvré : la part du mois prévue (budget, sinon même mois l'an dernier + 5 %)
    select c.jour,
           coalesce(b.budget_ht, v.ca_ht * 1.05) / j.nb as ca_ht
    from calendrier c
    join jours_ouvres j on j.mois = cast({{ dbt.date_trunc('month', 'c.jour') }} as date)
    left join budget_mois b on b.mois = j.mois
    left join ventes_mois v on v.mois = cast({{ dbt.dateadd('month', -12, 'j.mois') }} as date)
    where {{ est_jour_ouvre('c.jour') }}
),

entrees_a_venir as (   -- chaque vente à venir est encaissée selon le calendrier observé
    select {{ dbt.dateadd('day', 'p.delai', 'v.jour') }} as jour,
           v.ca_ht * (1 + m.tva) * p.montant / m.total_clients as montant
    from ventes_a_venir v cross join profil_clients p cross join moyennes m
),

sorties_a_venir as (   -- les marchandises à racheter pour ces ventes, payées selon le calendrier des fournisseurs
    select {{ dbt.dateadd('day', 'p.delai', 'v.jour') }} as jour,
           v.ca_ht * (1 - m.taux_marge) * (1 + m.tva) * p.montant / m.total_fournisseurs as montant
    from ventes_a_venir v cross join profil_fournisseurs p cross join moyennes m
),

-- ---------------------------------------------------------------- 4) les charges fixes et la TVA
charges as (   -- la moyenne mensuelle des 3 derniers mois, payée le dernier jour du mois
    select sum(-montant) / 3 as charges_mois
    from {{ ref('int_flux_tresorerie') }} cross join ref_date r
    where nature = 'charges fixes' and jour > {{ dbt.dateadd('month', -3, 'r.date_reference') }}
),

tva_par_mois as (   -- TVA collectée - TVA déductible, mois par mois : connue pour le passé, prévue ensuite
    select mois, sum(tva) as tva
    from (
        select cast({{ dbt.date_trunc('month', 'f.date_facture') }} as date) as mois, f.montant_ttc - f.montant_ht as tva
        from {{ ref('stg_factures') }} f cross join ref_date r where f.date_facture <= r.date_reference
        union all
        select cast({{ dbt.date_trunc('month', 'a.date_achat') }} as date), -(a.montant_ttc - a.montant_ht)
        from {{ ref('stg_achats') }} a cross join ref_date r where a.date_achat <= r.date_reference
        union all
        select cast({{ dbt.date_trunc('month', 'v.jour') }} as date), v.ca_ht * m.tva * m.taux_marge   -- collectée - déductible
        from ventes_a_venir v cross join moyennes m
    ) t
    group by mois
),

sorties_tva as (   -- la TVA d'un mois est reversée le 20 du mois suivant
    select {{ dbt.dateadd('day', 19, dbt.dateadd('month', 1, 'mois')) }} as jour, tva as montant from tva_par_mois
),

-- ---------------------------------------------------------------- 5) jour par jour
par_jour as (
    select
        c.jour,
        coalesce((select sum(montant) from entrees_emises e where cast(e.jour as date) = c.jour), 0)  as entrees_factures_emises,
        coalesce((select sum(montant) from entrees_a_venir e where cast(e.jour as date) = c.jour), 0) as entrees_ventes_a_venir,
        coalesce((select sum(montant) from sorties_emises s where cast(s.jour as date) = c.jour), 0)
          + coalesce((select sum(montant) from sorties_a_venir s where cast(s.jour as date) = c.jour), 0) as sorties_fournisseurs,
        case when c.jour = {{ dbt.last_day('c.jour', 'month') }} then (select charges_mois from charges) else 0 end
          + coalesce((select sum(montant) from sorties_tva t where cast(t.jour as date) = c.jour), 0)    as sorties_charges_tva
    from calendrier c
),

depart as (select solde from {{ ref('tresorerie_jour') }} order by jour desc limit 1)

select
    p.jour,
    round(p.entrees_factures_emises, 2)                                       as entrees_factures_emises,
    round(p.entrees_ventes_a_venir, 2)                                        as entrees_ventes_a_venir,
    round(p.sorties_fournisseurs, 2)                                          as sorties_fournisseurs,
    round(p.sorties_charges_tva, 2)                                           as sorties_charges_tva,
    round(p.entrees_factures_emises + p.entrees_ventes_a_venir, 2)            as entrees_attendues,
    round(p.sorties_fournisseurs + p.sorties_charges_tva, 2)                  as sorties_attendues,
    round(d.solde + sum(p.entrees_factures_emises + p.entrees_ventes_a_venir
                        - p.sorties_fournisseurs - p.sorties_charges_tva) over (order by p.jour), 2)
                                                                              as solde_prevu
from par_jour p cross join depart d
