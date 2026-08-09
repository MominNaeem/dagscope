INSERT INTO public.positions_usd (
    position_date,
    instrument_id,
    quantity,
    book_value_usd,
    fx_rate
)
SELECT
    p.position_date,
    p.instrument_id,
    p.quantity,
    p.book_value * fx.rate  AS book_value_usd,
    fx.rate                 AS fx_rate
FROM public.positions_daily p
JOIN raw.fx_rates fx
    ON  p.currency      = fx.from_currency
    AND fx.to_currency  = 'USD'
    AND p.position_date = fx.rate_date
ON CONFLICT (position_date, instrument_id) DO UPDATE
    SET book_value_usd = EXCLUDED.book_value_usd,
        fx_rate        = EXCLUDED.fx_rate,
        updated_at     = NOW();
