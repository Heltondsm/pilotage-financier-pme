-- Question 4 : les clients à surveiller tout de suite, du plus gros montant en jeu au plus petit
--   - procédure au Bodacc (vraie annonce) avec de l'argent encore dû ;
--   - ou plus de 5 000 € en retard de plus de 60 jours (hors créances douteuses, déjà provisionnées).
select
    code_client,
    activite,
    metier,
    departement,
    encours_ttc,
    round(retard_61_90 + retard_plus_90, 2) as retard_plus_60_ttc,
    douteux,
    retard_max_jours,
    procedure_bodacc,
    date_procedure,
    case
        when procedure_bodacc is not null then 'procédure collective : déclarer la créance au mandataire et bloquer les livraisons'
        else 'retard important : relancer par téléphone et suspendre les nouvelles commandes'
    end as action
from {{ ref('balance_agee') }}
where (procedure_bodacc is not null and encours_ttc > 0)
   or (retard_61_90 + retard_plus_90 > 5000)
