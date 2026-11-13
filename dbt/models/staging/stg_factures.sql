-- Une ligne par facture de Distrimat (TEST), nettoyée :
-- les lignes en double sont retirées, et les lignes d'un client inconnu sont écartées (voir qualite_rejets)
with lignes as (
    select
        *,
        -- deux lignes identiques en tout point = un doublon d'export : on n'en garde qu'une
        row_number() over (
            partition by numero_facture, code_produit, quantite, cast(prix_unitaire_ht as {{ dbt.type_string() }}), code_client   -- BigQuery refuse de grouper sur un nombre à virgule
            order by numero_facture
        ) as copie
    from {{ source('brut', 'factures') }}
)

select
    l.numero_facture,
    min(cast(l.date_facture as date))                       as date_facture,
    min(cast(l.date_echeance as date))                      as date_echeance,
    min(l.code_client)                                      as code_client,
    round(sum(l.quantite * l.prix_unitaire_ht), 2)          as montant_ht,
    round(sum(l.quantite * l.prix_unitaire_ht * p.taux_marge), 2) as marge_brute_ht,
    round(sum(l.quantite * l.prix_unitaire_ht) * (1 + max(prm.taux_tva)), 2) as montant_ttc
from lignes l
join {{ ref('produits') }} p on p.code_produit = l.code_produit
cross join {{ ref('parametres') }} prm
where l.copie = 1
  and l.code_client in (select code_client from {{ ref('clients') }})   -- client inconnu : écarté
group by l.numero_facture
