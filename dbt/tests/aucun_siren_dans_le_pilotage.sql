-- Les tables de pilotage de Distrimat ne doivent jamais exposer un vrai SIREN (protection des clients) :
-- on vérifie qu'aucun code client ne ressemble à un numéro à 9 chiffres
select code_client from {{ ref('balance_agee') }}
where length(code_client) = 9 and {{ dbt.safe_cast('code_client', dbt.type_bigint()) }} is not null
