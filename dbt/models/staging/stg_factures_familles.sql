-- Les ventes par jour et par famille de produits (pour comparer au budget), sans doublons ni clients inconnus
with lignes as (
    select
        *,
        row_number() over (
            partition by numero_facture, code_produit, quantite, cast(prix_unitaire_ht as {{ dbt.type_string() }}), code_client   -- BigQuery refuse de grouper sur un nombre à virgule
            order by numero_facture
        ) as copie
    from {{ source('brut', 'factures') }}
)

select
    cast(l.date_facture as date)                            as date_facture,
    p.famille,
    round(sum(l.quantite * l.prix_unitaire_ht), 2)          as montant_ht,
    round(sum(l.quantite * l.prix_unitaire_ht * p.taux_marge), 2) as marge_brute_ht
from lignes l
join {{ ref('produits') }} p on p.code_produit = l.code_produit
where l.copie = 1
  and l.code_client in (select code_client from {{ ref('clients') }})
group by 1, 2
