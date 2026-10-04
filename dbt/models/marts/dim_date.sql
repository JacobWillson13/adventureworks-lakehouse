-- One row per calendar day. date_key (yyyymmdd) is what the facts join on.
with days as (
    select explode(sequence(
        to_date('{{ var("calendar_start_date") }}'),
        to_date('{{ var("calendar_end_date") }}'),
        interval 1 day
    )) as date_day
)

select
    cast(date_format(date_day, 'yyyyMMdd') as int)        as date_key,
    date_day,
    year(date_day)                                        as year,
    quarter(date_day)                                     as quarter,
    month(date_day)                                       as month,
    date_format(date_day, 'MMMM')                         as month_name,
    date_format(date_day, 'yyyy-MM')                      as year_month,
    cast(date_trunc('MONTH', date_day) as date)           as month_start_date,
    day(date_day)                                         as day_of_month,
    weekday(date_day) + 1                                 as day_of_week,      -- 1 = Monday ... 7 = Sunday
    date_format(date_day, 'EEEE')                         as day_name,
    weekday(date_day) >= 5                                as is_weekend,
    date_day <= to_date('{{ var("analysis_end_date") }}') as is_in_analysis_window
from days
