-- Les charges fixes de chaque mois (salaires, loyers…), payées le dernier jour du mois
select
    mois,
    {{ dbt.last_day("cast(concat(mois, '-01') as date)", "month") }} as date_paiement,
    montant
from {{ source('brut', 'charges') }}
