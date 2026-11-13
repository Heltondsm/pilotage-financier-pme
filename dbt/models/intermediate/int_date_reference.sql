-- La date du jour pour tous les calculs : la dernière journée simulée (stable si on rejoue la chaîne).
-- Pour le backtest, on peut la reculer : dbt run --vars '{date_reference: 2026-04-30}'
{% if var('date_reference', none) %}
select cast('{{ var("date_reference") }}' as date) as date_reference
{% else %}
select max(date_facture) as date_reference from {{ ref('stg_factures') }}
{% endif %}
