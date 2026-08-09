INSERT INTO raw.trades (
    trade_id,
    trade_date,
    settle_date,
    instrument_id,
    quantity,
    price,
    currency,
    trader_id
)
SELECT
    src.trade_id,
    src.trade_date,
    src.settle_date,
    src.instrument_id,
    src.quantity,
    src.price,
    src.currency,
    src.trader_id
FROM staging.trades_staging src
ON CONFLICT (trade_id) DO UPDATE
    SET quantity   = EXCLUDED.quantity,
        price      = EXCLUDED.price,
        updated_at = NOW();
