INSERT INTO public.pnl_daily (
    position_date,
    instrument_id,
    realized_pnl,
    unrealized_pnl,
    total_pnl
)
SELECT
    curr.position_date,
    curr.instrument_id,
    COALESCE(prev.book_value_usd, 0) - curr.book_value_usd  AS realized_pnl,
    curr.book_value_usd - COALESCE(prev.book_value_usd, 0)  AS unrealized_pnl,
    curr.book_value_usd - COALESCE(prev.book_value_usd, 0)  AS total_pnl
FROM public.positions_usd curr
LEFT JOIN public.positions_usd prev
    ON  curr.instrument_id = prev.instrument_id
    AND prev.position_date = curr.position_date - INTERVAL '1 day'
ON CONFLICT (position_date, instrument_id) DO UPDATE
    SET realized_pnl   = EXCLUDED.realized_pnl,
        unrealized_pnl = EXCLUDED.unrealized_pnl,
        total_pnl      = EXCLUDED.total_pnl,
        updated_at     = NOW();
