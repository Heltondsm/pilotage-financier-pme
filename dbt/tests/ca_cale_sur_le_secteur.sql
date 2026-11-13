-- Chaque année complète, le chiffre d'affaires de Distrimat doit retomber à 1 % près sur la médiane du
-- secteur (avec la croissance prévue) : c'est la garantie que les données de test sont réalistes
with annees as (
    select extract(year from date_facture) as annee, sum(montant_ht) as ca
    from {{ ref('stg_factures') }}
    group by 1
)
select a.annee, a.ca, p.ca_secteur
from annees a cross join {{ ref('parametres') }} p
cross join {{ ref('int_date_reference') }} r
where a.annee < extract(year from r.date_reference)                 -- seulement les années terminées
  and abs(a.ca / (p.ca_secteur * power(1 + p.croissance, a.annee - 2024)) - 1) > 0.01
