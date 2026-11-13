{# Lire un texte comme une date ou un nombre : une case vide ou mal écrite donne une case vide, pas une erreur #}
{% macro en_date(colonne) %}{{ dbt.safe_cast("nullif(" ~ colonne ~ ", '')", api.Column.translate_type("date")) }}{% endmacro %}
{% macro en_nombre(colonne) %}{{ dbt.safe_cast("nullif(" ~ colonne ~ ", '')", dbt.type_float()) }}{% endmacro %}

{# La date du jour, écrite comme chaque entrepôt l'attend #}
{% macro aujourd_hui() %}{{ 'current_date()' if target.type == 'bigquery' else 'current_date' }}{% endmacro %}

{# Test générique : un SIREN a 9 chiffres et respecte la clé de Luhn (le dernier chiffre est un contrôle) #}
{% test siren_valide(model, column_name) %}
with chiffres as (
    select {{ column_name }} as siren,
    {% for i in range(1, 10) %}
        {% set c = dbt.safe_cast("substr(" ~ column_name ~ ", " ~ i ~ ", 1)", dbt.type_int()) %}
        {% if i % 2 == 0 %}
            case when {{ c }} * 2 > 9 then {{ c }} * 2 - 9 else {{ c }} * 2 end
        {% else %}
            {{ c }}
        {% endif %} as c{{ i }}{{ "," if not loop.last }}
    {% endfor %}
    from {{ model }}
    where {{ column_name }} is not null
)
select siren from chiffres
where length(siren) != 9
   or c1 is null or c2 is null or c3 is null or c4 is null or c5 is null or c6 is null or c7 is null or c8 is null or c9 is null
   or mod(c1 + c2 + c3 + c4 + c5 + c6 + c7 + c8 + c9, 10) != 0
{% endtest %}

{# Test générique : une combinaison de colonnes ne doit apparaître qu'une fois (un bilan par exercice) #}
{% test combinaison_unique(model, colonnes) %}
select {{ colonnes | join(', ') }}, count(*) as nb
from {{ model }}
group by {{ colonnes | join(', ') }}
having count(*) > 1
{% endtest %}
