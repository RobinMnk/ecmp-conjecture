# ECMP Conjecture

A Python 3 framework for checking the correctness of a conjecture about the quality of routings produced by equal-splitting routing (the ECMP protocol) in unit-capacity networks, when compared to an optimal arbitrary-splitting solution. The precise wording of the conjecture we want to test is

**Main Conjecture:**</br>
*In unit-capacity networks with multiple sources and a single target, for every optimal arbitrary-splitting DAG there exists an equal-splitting sub-DAG with performance ratio less than 2.*

The framework offers many great features for analyzing routing problems empirically

- The generation of random routing instances of any size, supporting a distinction between unit and arbitrary demands and limiting the number of incoming/outgoing edges
- A visual output by converting each instance and solution to the DOT-graph format
- Three solvers: An optimal solver, an equal-splitting and an integral-flow solver, each running in exponential time
- A framework for adding/customizing conjectures that can be checked either for every sub-DAG of the optimal flow or just for those where equal-splitting was optimal.
    All output is logged and files for further inspection are generated.
- Support for multiprocessing on multiple threads

## The Framework

The framework tests conjectures by generating a random routing instance and checking whether the assumption holds up. In our simulations, no counterexample for our main conjecture has been found.

### Main Functionality 

After computing a random routing instance, the framework calculates an optimal arbitrary-splitting solution for the instance using Gurobi to solve the LP of the associated Multicommodity flow formulation.  From the resulting optimal forwarding DAG, the framework computes the ECMP DAGs. The framework supports two options: Either the conjecture is checked for the optimal ECMP DAGs only or it is checked whether any sub-DAG exists that satisfies the conjecture (but needs not be optimal). Additionally, it can be specified to produce only single-forwarding DAGs, without traffic splitting.

### Checking Multiple Assumptions

In addition to checking our main conjecture, the framework supports the simple adding/modifying of new conjectures/other assumptions that will all be checked for correctness together. This can be done by simply defining a verification function that specifies whether the assumption holds for the given optimal DAG and the set of ECMP DAGs. A second assumption which the simulation has not produced a counterexample for is the following

**Node Load Assumption:</br>** 
*There is **an** equal-splitting sub-DAG with performance ratio less than 2 **and** all node load factors less than 2.*

A neat extra feature is the simple checking of implications between conjectures. In the framework, we can simply specify

```
LOADS_CONJECTURE.implies(MAIN_CONJECTURE)
```

to denote the new assumption that the loads conjecture implies the main conjecture. This can be checked in the exact same way.

## Usage

Running a test is done in just four simple lines of code!

```python

    ig = InstanceGenerator(max_node=12, arbitrary_demands=True)
    ConjectureManager.setup(CHECK_ON_ALL_SUB_DAGS, ECMP_FORWARDING)
    ConjectureManager.register(MAIN_CONJECTURE,
                               LOADS_CONJECTURE,
                               LOADS_CONJECTURE.implies(MAIN_CONJECTURE),
                               MAIN_CONJECTURE.implies(LOADS_CONJECTURE)
                              )
    run_single_test_suite(ig, 2000)
```

