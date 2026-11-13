-- Un délai de paiement des clients (DSO) doit rester entre 0 et 180 jours
select mois, dso_jours from {{ ref('kpi_mensuels') }}
where dso_jours < 0 or dso_jours > 180
