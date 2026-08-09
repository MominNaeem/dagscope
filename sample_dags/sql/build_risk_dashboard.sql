INSERT INTO public.risk_dashboard_ext (
    report_date,
    instrument_id,
    total_pnl,
    exposure_pct,
    sector
)
SELECT
    er.report_date,
    er.instrument_id,
    pnl.total_pnl,
    er.pct_of_portfolio AS exposure_pct,
    er.sector
FROM public.exposure_report er
JOIN public.pnl_daily pnl
    ON  er.instrument_id = pnl.instrument_id
    AND er.report_date   = pnl.position_date
ON CONFLICT (report_date, instrument_id) DO UPDATE
    SET total_pnl    = EXCLUDED.total_pnl,
        exposure_pct = EXCLUDED.exposure_pct,
        updated_at   = NOW();
