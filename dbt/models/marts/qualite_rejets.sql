-- La qualité des données : ce que le nettoyage a écarté ou corrigé, avec le nombre de lignes concernées
select 'lignes de factures en double (retirées)' as controle,
       (select count(*) from {{ source('brut', 'factures') }})
       - (select count(*) from (select distinct numero_facture, code_produit, quantite, cast(prix_unitaire_ht as {{ dbt.type_string() }}) as prix, code_client
                                from {{ source('brut', 'factures') }}) d) as nb_lignes
union all
select 'lignes de factures d’un client inconnu (écartées)',
       (select count(*) from {{ source('brut', 'factures') }}
        where code_client not in (select code_client from {{ ref('clients') }}))
union all
select 'paiements sans facture correspondante (écartés)',
       (select count(*) from {{ source('brut', 'paiements') }}) - (select count(*) from {{ ref('stg_paiements') }})
union all
select 'bilans avec compte de résultat confidentiel (chiffres vidés)',
       (select count(*) from {{ ref('stg_bilans') }} where confidentiel)
union all
select 'bilans en double ou datés dans le futur (écartés)',
       (select count(*) from {{ source('brut', 'bilans') }}) - (select count(*) from {{ ref('stg_bilans') }})
