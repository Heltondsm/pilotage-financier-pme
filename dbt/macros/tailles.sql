{# La classe de taille d'une entreprise, à partir de la tranche d'effectif de l'INSEE #}
{% macro classe_taille(colonne) %}
    case
        when {{ colonne }} in ('00', '01', '02', '03') then '1 - moins de 10 salariés'
        when {{ colonne }} in ('11', '12') then '2 - 10 à 49 salariés'
        when {{ colonne }} in ('21', '22', '31') then '3 - 50 à 249 salariés'
        when {{ colonne }} in ('32', '41', '42', '51', '52', '53') then '4 - 250 salariés et plus'
        else '0 - effectif inconnu'
    end
{% endmacro %}

{# Le nombre de jours entre deux dates, écrit comme chaque entrepôt l'attend #}
{% macro jours_entre(debut, fin) %}{{ dbt.datediff(debut, fin, 'day') }}{% endmacro %}

{# Un quantile d'une colonne à l'intérieur d'un groupe (fonction de fenêtre) : 0.5 = la médiane,
   0.25 = le premier quart, 0.75 = le dernier quart. Écrit pour chaque entrepôt. #}
{% macro quantile_groupe(colonne, q, groupe) %}
    {%- if target.type == 'bigquery' -%}
        percentile_cont({{ colonne }}, {{ q }}) over (partition by {{ groupe }})
    {%- else -%}
        quantile_cont({{ colonne }}, {{ q }}) over (partition by {{ groupe }})
    {%- endif -%}
{% endmacro %}

{# Un nombre écrit à la française, pour les phrases du diagnostic : 9.63 -> « 9,6 » ; 75.6 avec 0 décimale -> « 76 » #}
{% macro texte_nombre(colonne, decimales=0) %}
    {%- if decimales == 0 -%}
        cast(cast(round({{ colonne }}, 0) as {{ dbt.type_bigint() }}) as {{ dbt.type_string() }})
    {%- else -%}
        replace(cast(round({{ colonne }}, {{ decimales }}) as {{ dbt.type_string() }}), '.', ',')
    {%- endif -%}
{% endmacro %}

{# Vrai du lundi au vendredi (Distrimat ne facture pas le week-end), écrit pour chaque entrepôt #}
{% macro est_jour_ouvre(jour) %}
    {%- if target.type == 'bigquery' -%}
        extract(dayofweek from {{ jour }}) not in (1, 7)
    {%- else -%}
        isodow({{ jour }}) < 6
    {%- endif -%}
{% endmacro %}

{# Une suite de jours, du jour « debut » au jour « fin » compris (deux expressions de date) #}
{% macro suite_de_jours(debut, fin) %}
    {%- if target.type == 'bigquery' -%}
        unnest(generate_date_array(cast({{ debut }} as date), cast({{ fin }} as date))) as jour
    {%- else -%}
        (select cast(generate_series as date) as jour from generate_series(cast({{ debut }} as timestamp), cast({{ fin }} as timestamp), interval 1 day)) jours
    {%- endif -%}
{% endmacro %}
