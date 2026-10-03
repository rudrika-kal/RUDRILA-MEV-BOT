#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Edge {
    pub pool: &'static str,
    pub token_in: &'static str,
    pub token_out: &'static str,
    pub numerator: u128,
    pub denominator: u128,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Cycle {
    pub pools: Vec<&'static str>,
    pub amount_in: u128,
    pub amount_out: u128,
    pub net_profit: i128,
}

fn quote(edge: &Edge, amount: u128) -> Option<u128> {
    if edge.denominator == 0 {
        return None;
    }
    amount.checked_mul(edge.numerator)?.checked_div(edge.denominator)
}

pub fn best_cycle(
    edges: &[Edge],
    base: &'static str,
    amount_in: u128,
    max_hops: usize,
    fixed_cost: u128,
    min_net_profit: u128,
) -> Option<Cycle> {
    fn walk(
        edges: &[Edge],
        base: &'static str,
        current: &'static str,
        amount: u128,
        depth: usize,
        max_hops: usize,
        used: &mut Vec<&'static str>,
        path: &mut Vec<&'static str>,
        amount_in: u128,
        fixed_cost: u128,
        min_net_profit: u128,
        best: &mut Option<Cycle>,
    ) {
        if depth >= max_hops {
            return;
        }

        for edge in edges.iter().filter(|e| e.token_in == current) {
            if used.contains(&edge.pool) {
                continue;
            }
            let Some(out) = quote(edge, amount) else { continue };
            used.push(edge.pool);
            path.push(edge.pool);

            if edge.token_out == base && depth + 1 >= 2 {
                let gross = out as i128 - amount_in as i128;
                let net = gross - fixed_cost as i128;
                if net >= min_net_profit as i128 {
                    let candidate = Cycle {
                        pools: path.clone(),
                        amount_in,
                        amount_out: out,
                        net_profit: net,
                    };
                    if best.as_ref().map(|x| candidate.net_profit > x.net_profit).unwrap_or(true) {
                        *best = Some(candidate);
                    }
                }
            } else {
                walk(
                    edges,
                    base,
                    edge.token_out,
                    out,
                    depth + 1,
                    max_hops,
                    used,
                    path,
                    amount_in,
                    fixed_cost,
                    min_net_profit,
                    best,
                );
            }

            path.pop();
            used.pop();
        }
    }

    if amount_in == 0 || max_hops < 2 {
        return None;
    }

    let mut best = None;
    walk(
        edges,
        base,
        base,
        amount_in,
        0,
        max_hops,
        &mut Vec::new(),
        &mut Vec::new(),
        amount_in,
        fixed_cost,
        min_net_profit,
        &mut best,
    );
    best
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_best_three_hop_cycle_after_costs() {
        let edges = vec![
            Edge { pool: "p1", token_in: "WETH", token_out: "USDC", numerator: 2, denominator: 1 },
            Edge { pool: "p2", token_in: "USDC", token_out: "DAI", numerator: 11, denominator: 10 },
            Edge { pool: "p3", token_in: "DAI", token_out: "WETH", numerator: 1, denominator: 2 },
        ];
        let best = best_cycle(&edges, "WETH", 1_000, 3, 20, 50).unwrap();
        assert_eq!(best.pools, vec!["p1", "p2", "p3"]);
        assert_eq!(best.amount_out, 1_100);
        assert_eq!(best.net_profit, 80);
    }

    #[test]
    fn refuses_below_minimum_net_profit() {
        let edges = vec![
            Edge { pool: "p1", token_in: "WETH", token_out: "USDC", numerator: 2, denominator: 1 },
            Edge { pool: "p2", token_in: "USDC", token_out: "WETH", numerator: 1, denominator: 2 },
        ];
        assert!(best_cycle(&edges, "WETH", 1_000, 3, 10, 1).is_none());
    }
}
