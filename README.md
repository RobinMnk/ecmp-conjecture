# ECMP Conjecture

A Python 3 framework for checking the correctness of a conjecture about the quality of routings produced by equal-splitting routing (the ECMP protocol) in unit-capacity networks, when compared to an optimal arbitrary-splitting solution. The precise wording of the conjecture we want to test is

**Main Conjecture:**</br>
*In unit-capacity networks with multiple sources and a single target, for every optimal arbitrary-splitting DAG there exists an equal-splitting sub-DAG with performance ratio less than 2.*

The framework offers many great features for analyzing routing problems empirically

- The generation of random routing instances of any size, supporting a distinction between unit and arbitrary demands and limiting the number of incoming/outgoing edges
- A visual output by converting each instance and solution to the DOT-graph format
- Three solvers: An optimal solver, an equal-splitting and an integral-flow solver, each running in exponential time
- A framework for adding/customizing conjectures that can be checked either for every sub-DAG of the optimal flow or just for those where equal-splitting was optimal.
- Complete logging of all processes
- Support for multiprocessing on multiple threads

#### Running a fully multi-threaded test is done in just four simple lines of code!

```python
ConjectureManager.setup(CHECK_ON_ALL_SUB_DAGS, ECMP_FORWARDING)
ConjectureManager.register(MAIN_CONJECTURE,
                           LOADS_CONJECTURE,
                           LOADS_CONJECTURE.implies(MAIN_CONJECTURE),
                           MAIN_CONJECTURE.implies(LOADS_CONJECTURE)
                          )
ig = InstanceGenerator(max_nodes=12, arbitrary_demands=True)
run_multiprocessing_suite(ig, 8, 10000)
```

This will run a test according to the specified parameters on 8 threads, each testing 10000 network instances.

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

As shown above, the tests can be customized and run in just four lines of code. Find those at the end of `main.py`. Instead of the multiprocessing, it is also possible to run a single threaded test with `run_single_test_suite(ig, num_of_tests)`. The checked conjectures and various settings can be adjusted in the `ConjectureManager`.

### Visualization

With a conversion to the DOT-graph format, the framework can output an image for every instance. The picture usually contains the network instance with sources marked in blue. Optionally, we can specify an optimal flow to be highlighted in the same network. It is then shown in green and node and edge loads are also indicated.

The following code produces an image of the given instance with the given name and highlights the DAG of `opt_sol`. This will save the two files `<name>.svg` and `<name>` in the output directory. The latter contains the DOT-graph output.

```python
show_graph(instance, name, opt_sol.dag)
```

See the `output/examples` folder for a demonstration.

![Check out output/examples/ex_1.svg](output/examples/ex_1.svg)

In larger networks in can help to hide the underlying network and only look at the DAG of the optimal flow. See the `_before.svg` and `_after.svg` example in the examples folder for an illustration. Such a trimmed output can also be used to highlight the equal-splitting flow within the optimal DAG.

### Instance Inspection

With the `save_instance` function any instance can be saved as a pickle for further analysis. Try `inspect_instance(1, "examples")` for a demonstration of an exemplary inspection pipeline.
