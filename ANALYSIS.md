# Analysis

## Section 1 - Algorithm Behavior

Greedy made decisions in `O(n*m)` time, where `n` is the number of requests and `m` is the number of couriers, but it was still dramatically faster than Hungarian on small datasets because it never builds a full assignment matrix or solves a global optimization problem. The critical insight was that in a time-sensitive courier network, the first good feasible option is often operationally acceptable if it satisfies hard constraints like skill, shift, and capacity. That makes Greedy ideal for urgent arrivals, because the dispatcher can respond immediately and still produce a reasonable assignment.

Hungarian, by contrast, spends more time up front building a cost matrix and finding the global minimum cost matching. That extra work is valuable when the batch is large enough that local decisions can create bad downstream effects. In our tests, Hungarian consistently produced a lower or equal total cost than Greedy on the same input, which is exactly what you expect from a batch optimal method. Simulated Annealing sits between them: it starts from the Greedy solution, then explores the space of alternative assignments, which makes it useful when conditions are changing and the system benefits from a search process that can escape local minima.

## Section 2 - When Each Algorithm Wins

| Scenario | Best Algorithm | Why |
|---|---|---|
| <10 urgent requests | Greedy | Speed critical |
| 20+ scheduled batch | Hungarian | Global optimality |
| Mixed urgency | Hybrid | Best of both |
| Changing conditions | SA | Can escape local optima |

Greedy is strongest when the workload is small or the SLA is tight, because it minimizes decision latency. Hungarian wins when the batch is large enough that a global view can materially reduce total travel and cost. Hybrid is the most practical dispatcher for a real medical courier workflow because it can treat critical requests immediately, then optimize the remainder as a batch. SA is a good secondary optimizer when the environment is unstable, because its stochastic moves can find improvements that deterministic methods miss.

## Section 3 - Production Recommendation

In a real medical courier system, I would use a three-tier approach. First, urgent critical samples would be routed through Greedy so the dispatcher always has a fast answer for life-sensitive arrivals. Second, scheduled non-critical batches would go through Hungarian to maximize global efficiency and reduce wasted travel time. Third, for large or noisy batches, I would run Simulated Annealing as an optional post-optimizer to search for incremental improvements when runtime budget allows it. That gives the system a sensible operational hierarchy: immediate response for emergencies, optimal matching for planned work, and adaptive improvement when the dispatch queue becomes complex.

This is also the safest production pattern because it separates concerns. The dispatcher can preserve service quality for critical requests without forcing every decision through the most expensive algorithm. At the same time, it avoids using Greedy everywhere, which would be too myopic for large batches. In practice, I would expose runtime budgets and service-level objectives to the orchestration layer so the system can decide when to stop at Greedy, when to escalate to Hungarian, and when to invoke SA.

## Section 4 - What I Would Do With More Time

- Real traffic API integration
- ML model trained on historical assignment outcomes
- WebSocket for live courier GPS tracking

I would also add route replay, richer dispatcher audit logs, and post-assignment analytics so the system could learn from missed expiries, late arrivals, and courier utilization patterns over time.
