-- One record per randomized visitor, with zero realized outcomes for nonbuyers.
CREATE VIEW visitor_outcomes AS
SELECT visitor_id, variant, channel, price, converted, retained,
       paid_months, revenue_cents - cost_cents AS contribution_cents
FROM visitors;

-- Sufficient statistics for visitor-level rates and mean differences.
CREATE VIEW experiment_summary AS
SELECT variant, channel, COUNT(*) AS visitors,
       SUM(converted) AS conversions, SUM(retained) AS retained,
       SUM(contribution_cents) AS total_cents,
       SUM(contribution_cents * contribution_cents) AS squared_cents
FROM visitor_outcomes
GROUP BY variant, channel;
