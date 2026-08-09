INSERT INTO public.positions_daily (
    position_date,
    instrument_id,
    isin,
    currency,
    quantity,
    book_value
)
SELECT
    t.trade_date                        AS position_date,
    t.instrument_id,
    im.isin,
    im.currency,
    SUM(t.quantity)                     AS quantity,
    SUM(t.quantity * t.price)           AS book_value
FROM raw.trades t
JOIN raw.instrument_master im
    ON t.instrument_id = im.instrument_id
LEFT JOIN public.settlement_breaks sb
    ON  t.instrument_id = sb.instrument_id
    AND t.trade_date    = sb.break_date - INTERVAL '1 day'
GROUP BY
    t.trade_date,
    t.instrument_id,
    im.isin,
    im.currency
ON CONFLICT (position_date, instrument_id) DO UPDATE
    SET quantity   = EXCLUDED.quantity,
        book_value = EXCLUDED.book_value,
        updated_at = NOW();
