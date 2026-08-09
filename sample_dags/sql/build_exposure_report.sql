INSERT INTO public.exposure_report (
    report_date,
    instrument_id,
    isin,
    sector,
    total_pnl,
    pct_of_portfolio
)
SELECT
    pnl.position_date                                               AS report_date,
    pnl.instrument_id,
    im.isin,
    im.sector,
    SUM(pnl.total_pnl)                                             AS total_pnl,
    SUM(pnl.total_pnl) / NULLIF(SUM(SUM(pnl.total_pnl)) OVER (), 0) AS pct_of_portfolio
FROM public.pnl_daily pnl
JOIN raw.instrument_master im
    ON pnl.instrument_id = im.instrument_id
GROUP BY
    pnl.position_date,
    pnl.instrument_id,
    im.isin,
    im.sector
ON CONFLICT (report_date, instrument_id) DO UPDATE
    SET total_pnl        = EXCLUDED.total_pnl,
        pct_of_portfolio = EXCLUDED.pct_of_portfolio,
        updated_at       = NOW();
