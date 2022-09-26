# ECMP Conjecture

**Statement Main Conjecture:**
*In unit-capacity Networks with multiple sources and a single target, for every optimal arbitrary-splitting DAG there exists an equal-splitting sub-DAG with performance ratio less than 2.*

- No counterexample found so far!

**Load Assumption:**
*In an optimal equal-splitting sub-DAG: At every node, the equal-splitting load is at most twice the load as in the optimal solution.*

- Quick, small counterexample found!
- Examples with **edges** that have a load ratio larger than 2
  -> Add node within edge -> counterexample!

**First Update on Load Assumption:**
*In an optimal equal-splitting sub-DAG: At every **source**, the equal-splitting load is at most twice the load as in the optimal solution.*

- Simulations show: Second Assumption is still **not always true**
- There are optimal ES-DAGs where a source with load ratio > 2 exists!!!

**Second Update on Load Assumption:**
*There is **an** equal-splitting sub-DAG with performance ratio less than 2 **and** all node load factors less than 2.*

- Note: this DAG is not necessarily ES-optimal w.r.t. congestion
- No counterexample found so far!